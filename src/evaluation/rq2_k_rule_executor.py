"""RQ2-K: esecutore deterministico delle regole candidate (GT-free).

Cosa fa
-------
Applica una regola K GIA' VALIDATA dal contratto (`validate_candidate_rule`) alla
telemetria di nodo o container in una finestra di gruppo, e produce:
  * una decisione di gruppo: positive | negative | abstain;
  * per ogni componente, il PRIMO istante in cui la regola scatta;
  * i conteggi delle celle vere / false / sconosciute, con la causa di ogni
    "sconosciuto".

Cosa NON fa
-----------
  * Non esegue mai il campo `pseudocode` (non lo legge nemmeno) ne' codice del
    modello: usa solo gli insiemi chiusi di operatori e aggregazioni del contratto.
  * Non conosce etichette, classi, componente di riferimento o istante del guasto:
    non riceve nessun parametro che li contenga.
  * Non legge file e non chiama provider: lavora su DataFrame passati dal chiamante.

Semantica (protocollo K, proposta in revisione)
-----------------------------------------------
  * Cella = (componente, istante t) su una griglia regolare in [start, end).
  * Una condizione usa la finestra (t - window_seconds, t]: causale, estremo sinistro
    escluso, destro incluso.
  * Logica a TRE VALORI (vero / falso / sconosciuto, alla Kleene):
      all: falso se una condizione e' falsa; altrimenti sconosciuto se una e'
           sconosciuta; altrimenti vero.
      any: vero se una e' vera; altrimenti sconosciuto se una e' sconosciuta;
           altrimenti falso.
  * Sconosciuto = metrica assente per il componente, finestra senza campioni,
    finestra che parte prima della storia caricata, delta con un solo campione.
    Mai trasformato in "falso" in silenzio.
  * Decisione di gruppo, in modo CONSERVATIVO:
      positive  se almeno una cella e' vera (un sospetto basta);
      negative  solo se nessuna cella e' vera E nessuna e' sconosciuta;
      abstain   altrimenti, con la causa. Una lacuna non e' prova di assenza.
    La quota di celle valutabili si riporta come misura, non decide `negative`.
"""
from __future__ import annotations

import inspect
import math
from collections import Counter
from collections.abc import Mapping

import numpy as np
import pandas as pd

VERSION = "rq2_k_rule_executor_v1"
GRID_SECONDS_DEFAULT = 60

TRUE, FALSE, UNKNOWN = "T", "F", "U"
AGGREGATIONS = frozenset({"mean", "max", "min", "sum", "count", "p95", "last", "delta"})
OPERATORS = frozenset({">", ">=", "<", "<=", "=="})
LEVELS = ("node", "container")

# Cause di "sconosciuto" (restano nel risultato, mai nascoste).
CAUSE_METRIC_MISSING = "metric_missing_for_component"
CAUSE_NO_SAMPLES = "no_samples_in_window"
CAUSE_HISTORY = "window_before_loaded_history"
CAUSE_DELTA_ONE_SAMPLE = "delta_needs_two_samples"


class RuleExecutionError(ValueError):
    """La regola non e' eseguibile con questo esecutore (forma non ammessa)."""


def kleene_all(values: list[str]) -> str:
    if FALSE in values:
        return FALSE
    return UNKNOWN if UNKNOWN in values else TRUE


def kleene_any(values: list[str]) -> str:
    if TRUE in values:
        return TRUE
    return UNKNOWN if UNKNOWN in values else FALSE


def _compare(value: float, operator: str, threshold: float) -> bool:
    if operator == ">":
        return value > threshold
    if operator == ">=":
        return value >= threshold
    if operator == "<":
        return value < threshold
    if operator == "<=":
        return value <= threshold
    return value == threshold          # "=="; gli operatori sono controllati prima


def _aggregate(stamps: np.ndarray, values: np.ndarray, t: int, window: int,
               aggregation: str) -> tuple[float | None, str | None]:
    """Aggrega i campioni in (t - window, t]. Restituisce (valore, causa)."""
    lo = int(np.searchsorted(stamps, t - window, side="right"))
    hi = int(np.searchsorted(stamps, t, side="right"))
    count = hi - lo
    if count == 0:
        return None, CAUSE_NO_SAMPLES
    window_values = values[lo:hi]
    if aggregation == "count":
        return float(count), None
    if aggregation == "delta":
        if count < 2:
            return None, CAUSE_DELTA_ONE_SAMPLE
        return float(window_values[-1] - window_values[0]), None
    if aggregation == "last":
        return float(window_values[-1]), None
    if aggregation == "mean":
        return float(window_values.mean()), None
    if aggregation == "max":
        return float(window_values.max()), None
    if aggregation == "min":
        return float(window_values.min()), None
    if aggregation == "sum":
        return float(window_values.sum()), None
    return float(np.percentile(window_values, 95)), None     # "p95", interpolazione lineare


def _check_rule(rule: dict) -> list[dict]:
    """Controlli minimi di forma: l'esecutore non si fida nemmeno di una regola validata."""
    if type(rule) is not dict or rule.get("status") != "candidate":
        raise RuleExecutionError("Serve una regola con status 'candidate'")
    if rule.get("combination") not in ("all", "any"):
        raise RuleExecutionError("combination deve essere 'all' o 'any'")
    conditions = rule.get("conditions")
    if type(conditions) is not list or not conditions:
        raise RuleExecutionError("Condizioni assenti")
    for item in conditions:
        if (item.get("operator") not in OPERATORS
                or item.get("aggregation") not in AGGREGATIONS
                or type(item.get("window_seconds")) is not int
                or not 1 <= item["window_seconds"] <= 86400
                or type(item.get("threshold")) not in (int, float)
                or not math.isfinite(item["threshold"])
                or type(item.get("metric")) is not str):
            raise RuleExecutionError("Condizione fuori dagli insiemi chiusi del contratto")
    return conditions


def rule_level(conditions: list[dict], kpi_levels: Mapping[str, str]) -> tuple[str | None, str | None]:
    """Livello (node/container) della regola, FISSATO dal catalogo dei KPI.

    `kpi_levels` associa ogni nome di KPI al suo livello, ed e' costruito una volta
    sola dal catalogo (un KPI che comparisse in entrambi i livelli e' un errore del
    catalogo, non un caso da risolvere qui). Il livello NON dipende dai dati caricati
    per una finestra: una finestra senza campioni non puo' cambiare il livello di una
    regola, puo' solo rendere i suoi valori sconosciuti.
    Restituisce (livello, None) oppure (None, motivo): metric_absent (almeno un KPI
    non e' nel catalogo node/container) o mixed_levels (KPI di livelli diversi).
    """
    levels = set()
    for cond in conditions:
        level = kpi_levels.get(cond["metric"])
        if level is None:
            return None, "metric_absent"
        levels.add(level)
    if len(levels) != 1:
        return None, "mixed_levels"
    return next(iter(levels)), None


def _series_by_component(frame: pd.DataFrame, metrics: set[str]) -> dict:
    """(componente, KPI) -> (istanti ordinati, valori), scartando valori non finiti."""
    selected = frame.loc[frame["kpi_name"].isin(metrics), ["timestamp", "cmdb_id", "kpi_name", "value"]]
    selected = selected.assign(
        timestamp=pd.to_numeric(selected["timestamp"], errors="coerce"),
        value=pd.to_numeric(selected["value"], errors="coerce"),
    ).dropna(subset=["timestamp", "value"])
    selected = selected[np.isfinite(selected["value"].to_numpy(dtype=float))]
    series = {}
    for (cmdb_id, kpi), group in selected.groupby(["cmdb_id", "kpi_name"], sort=True):
        ordered = group.sort_values("timestamp")
        series[(str(cmdb_id), str(kpi))] = (
            ordered["timestamp"].to_numpy(dtype="int64"),
            ordered["value"].to_numpy(dtype=float),
        )
    return series


def execute_rule(rule: dict, telemetry: dict[str, pd.DataFrame], *, start_unix: int,
                 end_unix: int, history_start_unix: int, kpi_levels: Mapping[str, str],
                 grid_seconds: int = GRID_SECONDS_DEFAULT) -> dict:
    """Valuta una regola K validata su un gruppo di finestra [start_unix, end_unix).

    `telemetry` = {"node": DataFrame, "container": DataFrame} con colonne
    timestamp, cmdb_id, kpi_name, value, che devono includere la storia utile alle
    finestre (almeno da `history_start_unix`). `kpi_levels` fissa il livello di ogni KPI
    (dal catalogo). Nessuna etichetta e' accettata.
    """
    conditions = _check_rule(rule)
    if not (type(start_unix) is int and type(end_unix) is int and start_unix < end_unix):
        raise RuleExecutionError("Finestra di gruppo non valida")
    if type(grid_seconds) is not int or grid_seconds < 1:
        raise RuleExecutionError("Passo della griglia non valido")

    base = {"executor_version": VERSION, "level": None, "combination": rule["combination"]}
    if not all(v in LEVELS for v in kpi_levels.values()):
        raise RuleExecutionError("Livello di KPI non valido")
    level, reason = rule_level(conditions, kpi_levels)
    if level is None:
        return {**base, "decision": "abstain", "reason": {"code": reason},
                "components_total": 0, "components_missing_metric": [],
                "cells": {"total": 0, "true": 0, "false": 0, "unknown": 0},
                "evaluable_fraction": None, "unknown_by_cause": {},
                "first_fire_unix_by_component": {}}

    frame = telemetry.get(level)
    if frame is None or frame.empty:
        frame = pd.DataFrame(columns=["timestamp", "cmdb_id", "kpi_name", "value"])
    components = sorted(str(c) for c in frame["cmdb_id"].unique())
    metrics = {c["metric"] for c in conditions}
    series = _series_by_component(frame, metrics)
    missing_metric = sorted(
        c for c in components if any((c, m) not in series for m in metrics))

    combine = kleene_all if rule["combination"] == "all" else kleene_any
    instants = list(range(start_unix, end_unix, grid_seconds))
    counts = Counter()
    unknown_by_cause: Counter = Counter()
    first_fire: dict[str, int] = {}

    for component in components:
        for t in instants:
            truths, causes = [], []
            for cond in conditions:
                key = (component, cond["metric"])
                window = cond["window_seconds"]
                if key not in series:
                    truths.append(UNKNOWN)
                    causes.append(CAUSE_METRIC_MISSING)
                    continue
                if t - window < history_start_unix:
                    truths.append(UNKNOWN)
                    causes.append(CAUSE_HISTORY)
                    continue
                value, cause = _aggregate(*series[key], t, window, cond["aggregation"])
                if value is None:
                    truths.append(UNKNOWN)
                    causes.append(cause)
                else:
                    truths.append(TRUE if _compare(value, cond["operator"], cond["threshold"]) else FALSE)
                    causes.append(None)
            cell = combine(truths)
            counts[cell] += 1
            if cell == UNKNOWN:
                # Causa della prima condizione sconosciuta (ordine del contratto).
                unknown_by_cause[next(c for tr, c in zip(truths, causes) if tr == UNKNOWN)] += 1
            if cell == TRUE and component not in first_fire:
                first_fire[component] = t

    total = sum(counts.values())
    if counts[TRUE] > 0:
        decision = "positive"
    elif total > 0 and counts[UNKNOWN] == 0:
        decision = "negative"
    else:
        decision = "abstain"
    reason_code = (None if decision != "abstain"
                   else ("no_cells" if total == 0 else "unknown_cells"))
    return {
        **base, "level": level, "decision": decision,
        "reason": {"code": reason_code} if reason_code else {},
        "components_total": len(components),
        "components_missing_metric": missing_metric,
        "cells": {"total": total, "true": counts[TRUE], "false": counts[FALSE],
                  "unknown": counts[UNKNOWN]},
        "evaluable_fraction": ((counts[TRUE] + counts[FALSE]) / total) if total else None,
        "unknown_by_cause": dict(sorted(unknown_by_cause.items())),
        "first_fire_unix_by_component": dict(sorted(first_fire.items())),
    }


# Garanzia strutturale, verificata dai test: nessun parametro puo' portare etichette.
FORBIDDEN_PARAMETER_HINTS = ("gt", "label", "truth", "reference", "fault", "class", "case")


def _assert_no_label_parameters() -> None:
    for name in inspect.signature(execute_rule).parameters:
        if any(hint in name.lower() for hint in FORBIDDEN_PARAMETER_HINTS):
            raise AssertionError(f"Parametro sospetto nell'esecutore: {name}")


_assert_no_label_parameters()
