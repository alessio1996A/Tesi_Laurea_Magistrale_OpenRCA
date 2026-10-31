"""Common deterministic, offline node telemetry anomaly detector for OpenRCA Market.

No ground truth, model calls, or network access. Relative changes are hypotheses,
not proof of an incident or of its root cause. The baseline may be contaminated.
"""
from __future__ import annotations
import math
from typing import Any
import pandas as pd

REQUIRED = {"timestamp", "cmdb_id", "kpi_name", "value"}


def get_series(scope: pd.DataFrame, kpi: str) -> pd.Series:
    d = scope.loc[scope["kpi_name"].eq(kpi), ["timestamp", "value"]].copy()
    if d.empty:
        return pd.Series(dtype="float64")
    d["timestamp"] = pd.to_numeric(d["timestamp"], errors="coerce")
    d["value"] = pd.to_numeric(d["value"], errors="coerce")
    d = d.replace([float("inf"), -float("inf")], float("nan")).dropna()
    return d.groupby("timestamp")["value"].median().sort_index()


def evaluate_node_signal(
    telemetry: pd.DataFrame, component: str,
    start_unix: int, baseline_end_unix: int, end_unix: int,
    *, rule_id: str, cls: str, metric: str, extra_metric: str | None = None,
    relative_increase: float = .20, absolute_increase: float = 5.,
    robust_factor: float = 3.5, consecutive: int = 3,
    min_baseline: int = 8, max_gap_factor: float = 1.5,
) -> dict[str, Any]:
    if not isinstance(telemetry, pd.DataFrame):
        raise TypeError("telemetria deve essere un DataFrame")
    if not REQUIRED.issubset(telemetry.columns):
        raise ValueError(f"Colonne necessarie: {sorted(REQUIRED)}")
    if not isinstance(component, str) or not component.strip():
        raise ValueError("Componente non valido")
    if not (start_unix < baseline_end_unix < end_unix):
        raise ValueError("Intervallo temporale non valido")
    if (consecutive < 2 or min_baseline < 3 or max_gap_factor < 1
        or any(not math.isfinite(float(v)) or v <= 0 for v in
               (relative_increase, absolute_increase, robust_factor))):
        raise ValueError("Parametri detector non validi")

    out: dict[str, Any] = {
        "rule_id": rule_id, "classe_candidata": cls,
        "componente_telemetria": component, "status": "evidenza_insufficiente",
        "finestra": {"start_unix": int(start_unix),
                    "baseline_end_unix": int(baseline_end_unix), "end_unix": int(end_unix)},
        "ipotesi": None, "evidenze": {},
        "limitazioni": [
            "Baseline di riferimento non necessariamente sana.",
            "Soglie esplorative non calibrate con la ground truth.",
            "Anomalia osservata non equivale a root cause.",
            "La semantica fisica/unita' del KPI richiede verifica prima della valutazione finale.",
        ],
    }
    t = pd.to_numeric(telemetry["timestamp"], errors="coerce")
    scope = telemetry.loc[telemetry["cmdb_id"].eq(component) & t.ge(start_unix) & t.lt(end_unix)]
    series = get_series(scope, metric)
    base = series.loc[(series.index >= start_unix) & (series.index < baseline_end_unix)]
    search = series.loc[(series.index >= baseline_end_unix) & (series.index < end_unix)]
    ev = out["evidenze"]
    ev["kpi_principale"] = metric
    ev["campioni_baseline"] = int(len(base))
    ev["campioni_ricerca"] = int(len(search))
    if len(base) < min_baseline or len(search) < consecutive:
        out["limitazioni"].append("Campioni insufficienti nella baseline o nella ricerca.")
        return out
    if (base < 0).any() or (search < 0).any():
        out["limitazioni"].append("Valori KPI negativi: semantica incerta.")
        return out
    med = float(base.median())
    mad = float((base - med).abs().median())
    threshold = max(med + robust_factor * 1.4826 * mad,
                    med * (1 + relative_increase), med + absolute_increase)
    ev.update({"baseline_mediana": med, "baseline_mad": mad,
               "soglia_esplorativa": float(threshold),
               "massimo_ricerca": float(search.max()),
               "campioni_oltre_soglia": int((search > threshold).sum())})
    intervals = series.index.to_series().diff().dropna()
    intervals = intervals.loc[intervals > 0]
    if intervals.empty:
        out["limitazioni"].append("Cadenza non stimabile.")
        return out
    cadence = float(intervals.median())
    ev["cadenza_mediana_secondi"] = cadence
    max_gap = cadence * max_gap_factor
    first = last = None
    count = 0
    candidate = None
    for ts, value in search.items():
        ts = float(ts)
        if value > threshold:
            if last is None or ts - last > max_gap:
                first, count = ts, 1
            else:
                count += 1
            last = ts
            if count >= consecutive:
                candidate = (first, last, count)
                break
        else:
            first = last = None
            count = 0
    if candidate is None:
        out["status"] = "nessun_candidato"
        return out
    first, last, count = candidate
    out["status"] = "candidato_da_verificare"
    out["ipotesi"] = {"classe": cls,
                       "timestamp_primo_segnale_unix": int(first),
                       "timestamp_ultimo_segnale_unix": int(last),
                       "campioni_consecutivi": int(count)}
    if extra_metric:
        aux = get_series(scope, extra_metric)
        aux_baseline = aux.loc[(aux.index >= start_unix) & (aux.index < baseline_end_unix)]
        aux_event = aux.loc[(aux.index >= first) & (aux.index <= last)]
        ev["kpi_accessorio"] = {"nome": extra_metric,
                                "campioni_baseline": int(len(aux_baseline)),
                                "campioni_evento": int(len(aux_event)),
                                "mediana_baseline": float(aux_baseline.median()) if len(aux_baseline) else None,
                                "massimo_evento": float(aux_event.max()) if len(aux_event) else None}
    return out
