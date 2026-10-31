"""R01/R02/R06/R07/R08/R11: deterministic A1 evidence adapter.

Input: metrics already loaded by the A1 runner for the official incident window.
No file reading, label access, model calls, or changes to the A0 tools.
Only observational hypotheses, never verified root causes.
"""
from __future__ import annotations

from collections import Counter
from importlib import import_module
from typing import Any
import math

import pandas as pd

# Explicit allowlist: held-out Market fault classes are deliberately absent.
RULE_SPECS = (
    ("R01", "container", "harness.rules.rule_container_cpu", "valuta_r01_container_cpu", "container CPU load"),
    ("R02", "container", "harness.rules.rule_container_memory", "valuta_r02_container_memory", "container memory load"),
    ("R06", "container", "harness.rules.rule_container_read_io", "valuta_r06_container_read_io", "container read I/O load"),
    ("R07", "node", "harness.rules.rule_node_cpu_load", "valuta_r07_node_cpu_load", "node CPU load"),
    ("R08", "node", "harness.rules.rule_node_memory", "valuta_r08_node_memory", "node memory consumption"),
    ("R11", "node", "harness.rules.rule_node_disk_space", "valuta_r11_node_disk_space", "node disk space consumption"),
)

STATUSES = ("candidato_da_verificare", "nessun_candidato", "evidenza_insufficiente")
FIELDS = ("timestamp", "cmdb_id", "kpi_name", "value")
# An explicit evidence whitelist makes the prompt small and avoids copying full raw telemetry.
EVIDENCE_KEYS = (
    "kpi_principale", "baseline_mediana", "baseline_mad", "soglia_esplorativa",
    "massimo_ricerca", "campioni_oltre_soglia", "campioni_baseline", "campioni_ricerca",
    "baseline_mediana_cpu", "baseline_mad_cpu", "soglia_cpu_esplorativa",
    "massimo_cpu_nel_tratto_ricerca", "campioni_cpu_oltre_soglia",
    "campioni_baseline_cpu", "campioni_ricerca_cpu",
    "baseline_mediana_working_set_mb", "soglia_working_set_mb",
    "massimo_working_set_nel_tratto_ricerca_mb", "cadenza_mediana_secondi",
    "kpi_accessorio", "cfs", "limite_memoria_accessorio",
)


def _clean(value: Any) -> Any:
    """Convert pandas/numpy numeric scalars to portable, strict JSON primitives."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if hasattr(value, "item"):
        return _clean(value.item())
    raise TypeError(f"Tipo non serializzabile nel report regole: {type(value).__name__}")


def _components(df: pd.DataFrame, start: int, end: int) -> list[str]:
    if not set(FIELDS).issubset(df.columns):
        raise ValueError(f"Telemetria mancante colonne: {set(FIELDS) - set(df.columns)}")
    timestamps = pd.to_numeric(df["timestamp"], errors="coerce")
    scope = df.loc[timestamps.ge(start) & timestamps.lt(end), "cmdb_id"]
    return sorted({v for v in scope.dropna().tolist() if isinstance(v, str) and v.strip()})


def costruisci_evidenze_regole(
    df_nodi: pd.DataFrame,
    df_container: pd.DataFrame,
    start_unix: int,
    end_unix: int,
    *,
    quota_baseline: float = 0.4,
    max_candidati_report: int = 16,
) -> dict[str, Any]:
    """Evaluate exactly six predeclared rule classes on current-window telemetry.

    Returns a compact, deterministic and strict-JSON-safe report. No use of
    benchmark answers. `max_candidati_report` limits display only: all
    available components are evaluated and counts stay complete.
    """
    if not isinstance(df_nodi, pd.DataFrame) or not isinstance(df_container, pd.DataFrame):
        raise TypeError("df_nodi e df_container devono essere DataFrame")
    if not (isinstance(start_unix, int) and isinstance(end_unix, int)
            and start_unix < end_unix):
        raise ValueError("Intervallo Unix non valido")
    if not (0.0 < quota_baseline < 1.0):
        raise ValueError("quota_baseline deve essere in (0,1)")
    if not isinstance(max_candidati_report, int) or max_candidati_report < 1:
        raise ValueError("max_candidati_report deve essere un intero positivo")

    baseline_end = start_unix + int((end_unix - start_unix) * quota_baseline)
    if not start_unix < baseline_end < end_unix:
        raise ValueError("Finestra troppo corta per la baseline")

    datasets = {"node": df_nodi, "container": df_container}
    comp = {kind: _components(df, start_unix, end_unix) for kind, df in datasets.items()}
    candidates: list[dict[str, Any]] = []
    per_rule: list[dict[str, Any]] = []

    for rule_id, kind, module_name, func_name, expected_class in RULE_SPECS:
        function = getattr(import_module(module_name), func_name)
        counters = Counter()
        for component in comp[kind]:
            result = function(
                telemetria=datasets[kind],
                componente=component,
                start_unix=start_unix,
                baseline_end_unix=baseline_end,
                end_unix=end_unix,
            )
            if not isinstance(result, dict):
                raise ValueError(f"{rule_id}: il detector non ha restituito un dizionario")
            status = result.get("status")
            if status not in STATUSES:
                raise ValueError(f"{rule_id}: stato non valido {status!r}")
            if (result.get("rule_id") != rule_id or
                    result.get("classe_candidata") != expected_class or
                    result.get("componente_telemetria") != component):
                raise ValueError(f"{rule_id}: identita' della regola o del componente incoerente")
            counters[status] += 1
            if status == "candidato_da_verificare":
                hypothesis = result.get("ipotesi")
                if not isinstance(hypothesis, dict) or hypothesis.get("classe") != expected_class:
                    raise ValueError(f"{rule_id}: ipotesi non valida")
                first = hypothesis.get("timestamp_primo_segnale_unix")
                last = hypothesis.get("timestamp_ultimo_segnale_unix")
                if not (isinstance(first, int) and isinstance(last, int)
                        and baseline_end <= first <= last < end_unix):
                    raise ValueError(f"{rule_id}: timestamp non valido")
                evidence = result.get("evidenze", {})
                candidates.append({
                    "regola": rule_id,
                    "classe_candidata": expected_class,
                    "componente_telemetria": component,
                    "timestamp_primo_segnale_unix": first,
                    "timestamp_ultimo_segnale_unix": last,
                    "campioni_consecutivi": hypothesis.get("campioni_consecutivi"),
                    "evidenze": {key: evidence[key] for key in EVIDENCE_KEYS if key in evidence},
                })
        per_rule.append({
            "regola": rule_id,
            "classe": expected_class,
            "ambito": kind,
            "componenti_valutati": len(comp[kind]),
            "candidati": counters["candidato_da_verificare"],
            "nessun_candidato": counters["nessun_candidato"],
            "evidenza_insufficiente": counters["evidenza_insufficiente"],
        })

    # Stable ordering; no implied causal ranking, no time-based preference.
    candidates.sort(key=lambda c: (c["regola"], c["componente_telemetria"]))
    output = {
        "versione": "rule_based_A1_R_v0",
        "tipo": "ipotesi_osservative_non_causali",
        "finestra": {
            "start_unix": start_unix,
            "baseline_end_unix": baseline_end,
            "end_unix": end_unix,
            "baseline": f"primo_{quota_baseline:.0%}_della_finestra_caso_non_necessariamente_pre_guasto"
        },
        "conteggi_per_regola": per_rule,
        "totale_candidati": len(candidates),
        "candidati_riportati": candidates[:max_candidati_report],
        "candidati_omessi_per_budget": max(0, len(candidates) - max_candidati_report),
        "avvertenze": [
            "I candidati sono anomalie/possibili cause da verificare: NON sono ground truth.",
            "Non attribuire causalita' o priorita' al semplice ordine temporale delle anomalie.",
            "La baseline e' interna al caso e potrebbe includere gia' il guasto.",
            "Le regole coprono solo sei classi autorizzate; assenza di candidato non esclude un guasto.",
            "Nessuna verifica topologica o causale PAVE e' stata ancora applicata in questa variante.",
        ],
    }
    return _clean(output)
