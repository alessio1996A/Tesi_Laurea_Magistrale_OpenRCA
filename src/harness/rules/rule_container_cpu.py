"""R01 - ipotesi preliminare di 'container CPU load' (OpenRCA Market).

Prototipo OFFLINE indipendente da A0/A1, Gemini e ground truth.

ATTENZIONE:
- 'container_cpu_usage_seconds' nei dati Market osservati NON e' monotono.
  Viene trattato come serie numerica OSSERVATA, non differenziato, e la sua
  semantica fisica resta da verificare.
- L'intervallo [start_unix, baseline_end_unix) e' un riferimento ESPLICITO:
  chi chiama deve giustificare che sia adeguato; non si presume sia sano.
- La regola genera SOLO un'ipotesi esplorativa, mai una diagnosi causale certa.
"""

from __future__ import annotations

from typing import Any
import math

import pandas as pd

CPU_METRIC = "container_cpu_usage_seconds"
CFS_THROTTLED = "container_cpu_cfs_throttled_periods"
CFS_TOTAL = "container_cpu_cfs_periods"
REQUIRED_COLUMNS = {"timestamp", "cmdb_id", "kpi_name", "value"}


def _serie(df: pd.DataFrame, kpi: str) -> pd.Series:
    """Restituisce una serie temporale numerica ordinata, con duplicati medianati."""
    rows = df.loc[df["kpi_name"] == kpi, ["timestamp", "value"]].copy()
    if rows.empty:
        return pd.Series(dtype="float64", name=kpi)
    rows["timestamp"] = pd.to_numeric(rows["timestamp"], errors="coerce")
    rows["value"] = pd.to_numeric(rows["value"], errors="coerce")
    rows = rows.replace([float("inf"), -float("inf")], float("nan"))
    rows = rows.dropna(subset=["timestamp", "value"])
    if rows.empty:
        return pd.Series(dtype="float64", name=kpi)
    s = rows.groupby("timestamp")["value"].median().sort_index()
    s.name = kpi
    return s


def valuta_r01_container_cpu(
    telemetria: pd.DataFrame,
    componente: str,
    start_unix: int,
    baseline_end_unix: int,
    end_unix: int,
    *,
    soglia_robusta: float = 3.5,
    incremento_minimo_relativo: float = 0.25,
    consecutivi_minimi: int = 3,
    campioni_baseline_minimi: int = 8,
    massimo_gap_factor: float = 1.5,
) -> dict[str, Any]:
    """Valuta un candidato di CPU load, basandosi solo sulla telemetria fornita.

    Intervalli: baseline [start_unix, baseline_end_unix), ricerca
    [baseline_end_unix, end_unix). Nessuna ricerca oltre la finestra.
    Soglie esplorative NON calibrate su ground truth OpenRCA.
    """
    if not isinstance(telemetria, pd.DataFrame):
        raise TypeError("telemetria deve essere un DataFrame")
    if not REQUIRED_COLUMNS.issubset(telemetria.columns):
        raise ValueError(f"Colonne necessarie: {sorted(REQUIRED_COLUMNS)}")
    if not isinstance(componente, str) or not componente.strip():
        raise ValueError("Componente non valido")
    if not (start_unix < baseline_end_unix < end_unix):
        raise ValueError("Richiesti start_unix < baseline_end_unix < end_unix")
    if soglia_robusta <= 0 or incremento_minimo_relativo <= 0:
        raise ValueError("Soglie non valide")
    if consecutivi_minimi < 2 or campioni_baseline_minimi < 3 or massimo_gap_factor < 1:
        raise ValueError("Parametri campionamento non validi")

    esito: dict[str, Any] = {
        "rule_id": "R01",
        "classe_candidata": "container CPU load",
        "componente_telemetria": componente,
        "status": "evidenza_insufficiente",
        "finestra": {"start_unix": int(start_unix), "baseline_end_unix": int(baseline_end_unix),
                    "end_unix": int(end_unix)},
        "ipotesi": None,
        "evidenze": {},
        "limitazioni": [
            "La semantica fisica di container_cpu_usage_seconds non e' verificata sul dataset Market.",
            "La baseline deve essere giustificata esternamente e potrebbe contenere gia' un guasto.",
            "Un'anomalia CPU non dimostra la root cause e non determina da sola il timestamp del guasto.",
        ],
    }

    scope = telemetria.loc[
        (telemetria["cmdb_id"] == componente)
        & pd.to_numeric(telemetria["timestamp"], errors="coerce").ge(start_unix)
        & pd.to_numeric(telemetria["timestamp"], errors="coerce").lt(end_unix)
    ]
    cpu = _serie(scope, CPU_METRIC)
    base = cpu.loc[(cpu.index >= start_unix) & (cpu.index < baseline_end_unix)]
    osservati = cpu.loc[(cpu.index >= baseline_end_unix) & (cpu.index < end_unix)]
    esito["evidenze"]["campioni_baseline_cpu"] = int(len(base))
    esito["evidenze"]["campioni_ricerca_cpu"] = int(len(osservati))

    if len(base) < campioni_baseline_minimi or len(osservati) < consecutivi_minimi:
        esito["limitazioni"].append("Campioni CPU insufficienti nel riferimento o nella ricerca.")
        return esito

    # Cautela: dispersione zero impedisce di definire una soglia robusta stabile.
    mediana = float(base.median())
    mad = float((base - mediana).abs().median())
    esito["evidenze"]["baseline_mediana_cpu"] = mediana
    esito["evidenze"]["baseline_mad_cpu"] = mad
    if mediana <= 0 or mad <= 1e-12:
        esito["limitazioni"].append("Baseline CPU nulla o senza dispersione utile: astensione.")
        return esito

    soglia = max(
        mediana + soglia_robusta * 1.4826 * mad,
        mediana * (1.0 + incremento_minimo_relativo),
    )
    esito["evidenze"]["soglia_cpu_esplorativa"] = float(soglia)

    # Le osservazioni sono normalmente a 60s, ma non assumiamo questo valore.
    intervalli = cpu.index.to_series().diff().dropna()
    intervalli = intervalli.loc[intervalli > 0]
    if intervalli.empty:
        esito["limitazioni"].append("Cadenza temporale non verificabile.")
        return esito
    cadenza = float(intervalli.median())
    massimo_gap = cadenza * massimo_gap_factor
    esito["evidenze"]["cadenza_mediana_secondi"] = cadenza

    streak_start: float | None = None
    streak_last: float | None = None
    streak_count = 0
    candidato: tuple[float, float, int] | None = None
    for t, v in osservati.items():
        t = float(t)
        if v > soglia:
            if streak_last is None or (t - streak_last) > massimo_gap:
                streak_start, streak_count = t, 1
            else:
                streak_count += 1
            streak_last = t
            if streak_count >= consecutivi_minimi:
                candidato = (streak_start, t, streak_count)
                break
        else:
            streak_start, streak_last, streak_count = None, None, 0

    if candidato is None:
        esito["status"] = "nessun_candidato"
        esito["evidenze"]["campioni_cpu_oltre_soglia"] = int((osservati > soglia).sum())
        return esito

    t_inizio, t_fine, n = candidato
    esito["status"] = "candidato_da_verificare"
    esito["ipotesi"] = {
        "classe": "container CPU load",
        "timestamp_primo_segnale_unix": int(t_inizio),
        "timestamp_ultimo_segnale_unix": int(t_fine),
        "campioni_consecutivi": int(n),
    }
    esito["evidenze"]["massimo_cpu_nel_tratto_ricerca"] = float(osservati.max())

    # CFS: osservazione descrittiva, NON conferma causale automatica.
    throttled = _serie(scope, CFS_THROTTLED)
    total = _serie(scope, CFS_TOTAL)
    paired = pd.concat([throttled, total], axis=1, join="inner").dropna()
    in_period = paired.loc[(paired.index >= t_inizio) & (paired.index <= t_fine)]
    valido = (in_period[CFS_TOTAL] > 0) & (in_period[CFS_THROTTLED] >= 0)
    denominator_valid = in_period.loc[valido]
    ratios = denominator_valid[CFS_THROTTLED] / denominator_valid[CFS_TOTAL]
    ratios = ratios.loc[ratios.map(math.isfinite)]
    valid_ratios = ratios.loc[ratios.between(0, 1)]
    esito["evidenze"]["cfs"] = {
        "coppie_disponibili": int(len(in_period)),
        "coppie_denominatore_valido": int(len(denominator_valid)),
        "rapporti_ammissibili": int(len(valid_ratios)),
        "rapporti_maggiori_di_uno": int((ratios > 1).sum()),
        "rapporti_positivi": int((valid_ratios > 0).sum()),
        "mediana_rapporto_ammissibile": (
            float(valid_ratios.median()) if len(valid_ratios) else None
        ),
    }
    esito["limitazioni"].append(
        "Il rapporto CFS e' riportato come segnale accessorio: non prova la classe di guasto."
    )
    return esito
