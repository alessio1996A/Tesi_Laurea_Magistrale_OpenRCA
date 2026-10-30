"""R02 - ipotesi esplorativa di 'container memory load' (OpenRCA Market).

Modulo offline indipendente da Gemini e dalla ground truth.
Non integra automaticamente il sistema A0/A1. La baseline e' scelta dal chiamante
ed e' una finestra di riferimento, NON necessariamente sana.

Il segnale principale e' container_memory_working_set_MB, trattato come livello
osservato in MB; container_memory_usage_MB e il limite sono indizi accessori.
RSS e failcnt non vengono usati come attivatori: semantica/unita' o storico
non sono ancora validati per il benchmark. Una anomalia NON prova causalita'.
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

WORKING_SET = "container_memory_working_set_MB"
MEMORY_USAGE = "container_memory_usage_MB"
MEMORY_LIMIT = "container_spec_memory_limit_MB"
REQUIRED_COLUMNS = {"timestamp", "cmdb_id", "kpi_name", "value"}


def _serie(df: pd.DataFrame, kpi: str) -> pd.Series:
    """Serie ordinata per timestamp, valori non finiti esclusi, duplicati medianati."""
    dati = df.loc[df["kpi_name"] == kpi, ["timestamp", "value"]].copy()
    if dati.empty:
        return pd.Series(dtype="float64", name=kpi)
    dati["timestamp"] = pd.to_numeric(dati["timestamp"], errors="coerce")
    dati["value"] = pd.to_numeric(dati["value"], errors="coerce")
    dati = dati.replace([float("inf"), -float("inf")], float("nan"))
    dati = dati.dropna(subset=["timestamp", "value"])
    if dati.empty:
        return pd.Series(dtype="float64", name=kpi)
    serie = dati.groupby("timestamp")["value"].median().sort_index()
    serie.name = kpi
    return serie


def valuta_r02_container_memory(
    telemetria: pd.DataFrame,
    componente: str,
    start_unix: int,
    baseline_end_unix: int,
    end_unix: int,
    *,
    soglia_robusta: float = 3.5,
    incremento_minimo_relativo: float = 0.25,
    incremento_minimo_mb: float = 8.0,
    consecutivi_minimi: int = 3,
    campioni_baseline_minimi: int = 8,
    massimo_gap_factor: float = 1.5,
) -> dict[str, Any]:
    """Propone un'ipotesi R02 se il working set aumenta in modo persistente.

    Baseline [start_unix, baseline_end_unix); osservazioni successive
    [baseline_end_unix, end_unix). Non usa etichette dei casi ne' classificazioni
    delle quattro categorie riservate.

    Le soglie sono euristiche esplorative, NON validate sul benchmark.
    """
    if not isinstance(telemetria, pd.DataFrame):
        raise TypeError("telemetria deve essere un DataFrame")
    if not REQUIRED_COLUMNS.issubset(telemetria.columns):
        raise ValueError(f"Colonne necessarie: {sorted(REQUIRED_COLUMNS)}")
    if not isinstance(componente, str) or not componente.strip():
        raise ValueError("Componente non valido")
    if not (start_unix < baseline_end_unix < end_unix):
        raise ValueError("Intervallo temporale non valido")
    if any(not math.isfinite(float(v)) or float(v) <= 0 for v in (
        soglia_robusta, incremento_minimo_relativo, incremento_minimo_mb,
        massimo_gap_factor
    )):
        raise ValueError("Soglie o fattori non validi")
    if consecutivi_minimi < 2 or campioni_baseline_minimi < 3 or massimo_gap_factor < 1:
        raise ValueError("Parametri campionamento non validi")

    esito: dict[str, Any] = {
        "rule_id": "R02",
        "classe_candidata": "container memory load",
        "componente_telemetria": componente,
        "status": "evidenza_insufficiente",
        "finestra": {
            "start_unix": int(start_unix),
            "baseline_end_unix": int(baseline_end_unix),
            "end_unix": int(end_unix),
        },
        "ipotesi": None,
        "evidenze": {},
        "limitazioni": [
            "La baseline deve essere giustificata; puo' contenere gia' un guasto.",
            "Le soglie di R02 sono esplorative e non calibrate su ground truth.",
            "Un aumento del working set e' un segnale, non una prova di root cause.",
        ],
    }

    timestamp = pd.to_numeric(telemetria["timestamp"], errors="coerce")
    scope = telemetria.loc[
        telemetria["cmdb_id"].eq(componente)
        & timestamp.ge(start_unix)
        & timestamp.lt(end_unix)
    ]

    ws = _serie(scope, WORKING_SET)
    base = ws.loc[(ws.index >= start_unix) & (ws.index < baseline_end_unix)]
    ricerca = ws.loc[(ws.index >= baseline_end_unix) & (ws.index < end_unix)]
    evidenze = esito["evidenze"]
    evidenze["campioni_baseline_working_set"] = int(len(base))
    evidenze["campioni_ricerca_working_set"] = int(len(ricerca))

    if len(base) < campioni_baseline_minimi or len(ricerca) < consecutivi_minimi:
        esito["limitazioni"].append("Campioni working set insufficienti.")
        return esito
    if (base < 0).any() or (ricerca < 0).any():
        esito["limitazioni"].append("Valori working set negativi non interpretabili.")
        return esito

    mediana = float(base.median())
    mad = float((base - mediana).abs().median())
    evidenze["baseline_mediana_working_set_mb"] = mediana
    evidenze["baseline_mad_working_set_mb"] = mad
    if mediana <= 0:
        esito["limitazioni"].append("Baseline working set nulla o non positiva.")
        return esito

    # La soglia minima assoluta evita di classificare fluttuazioni minuscole;
    # gestisce anche baseline costanti (MAD==0). Parametri da validare.
    soglia = max(
        mediana + soglia_robusta * 1.4826 * mad,
        mediana * (1 + incremento_minimo_relativo),
        mediana + incremento_minimo_mb,
    )
    evidenze["soglia_working_set_mb_esplorativa"] = float(soglia)

    intervalli = ws.index.to_series().diff().dropna()
    intervalli = intervalli.loc[intervalli > 0]
    if intervalli.empty:
        esito["limitazioni"].append("Cadenza campionamento non verificabile.")
        return esito
    cadenza = float(intervalli.median())
    evidenze["cadenza_mediana_secondi"] = cadenza
    max_gap = cadenza * massimo_gap_factor

    streak_start = None
    streak_last = None
    streak_count = 0
    candidato = None
    for t, v in ricerca.items():
        t = float(t)
        if v > soglia:
            if streak_last is None or t - streak_last > max_gap:
                streak_start, streak_count = t, 1
            else:
                streak_count += 1
            streak_last = t
            if streak_count >= consecutivi_minimi:
                candidato = (streak_start, t, streak_count)
                break
        else:
            streak_start, streak_last, streak_count = None, None, 0

    evidenze["campioni_working_set_oltre_soglia"] = int((ricerca > soglia).sum())
    if candidato is None:
        esito["status"] = "nessun_candidato"
        return esito

    t_inizio, t_fine, n = candidato
    esito["status"] = "candidato_da_verificare"
    esito["ipotesi"] = {
        "classe": "container memory load",
        "timestamp_primo_segnale_unix": int(t_inizio),
        "timestamp_ultimo_segnale_unix": int(t_fine),
        "campioni_consecutivi": int(n),
    }
    evidenze["massimo_working_set_mb_ricerca"] = float(ricerca.max())

    # Evidenze accessorie, non condizioni necessarie per la classificazione.
    usage = _serie(scope, MEMORY_USAGE)
    ubase = usage.loc[(usage.index >= start_unix) & (usage.index < baseline_end_unix)]
    uevent = usage.loc[(usage.index >= t_inizio) & (usage.index <= t_fine)]
    ubase_med = float(ubase.median()) if len(ubase) else None
    evidenze["uso_memoria_accessorio"] = {
        "campioni_baseline": int(len(ubase)),
        "campioni_evento": int(len(uevent)),
        "mediana_baseline_mb": ubase_med,
        "massimo_evento_mb": float(uevent.max()) if len(uevent) else None,
        "aumento_rispetto_baseline": (
            bool(uevent.max() > ubase_med) if len(uevent) and ubase_med is not None else None
        ),
    }

    lim = _serie(scope, MEMORY_LIMIT)
    levent = lim.loc[(lim.index >= t_inizio) & (lim.index <= t_fine)]
    # Non assumiamo che il limite sia una soglia di guasto; controlliamo solo
    # la coerenza e il rapporto descrittivo.
    positive = levent.loc[levent > 0]
    med_limit = float(positive.median()) if len(positive) else None
    emax = float(ricerca.loc[(ricerca.index >= t_inizio) & (ricerca.index <= t_fine)].max())
    rapporto = (emax / med_limit) if med_limit is not None else None
    evidenze["limite_memoria_accessorio"] = {
        "campioni_limite_positivi": int(len(positive)),
        "limite_mediano_mb": med_limit,
        "massimo_working_set_su_limite": float(rapporto) if rapporto is not None else None,
        "rapporto_maggiore_di_uno": bool(rapporto > 1) if rapporto is not None else None,
    }
    if rapporto is not None and rapporto > 1:
        esito["limitazioni"].append(
            "Working set maggiore del limite dichiarato: verificare unita' e semantica."
        )
    if not len(uevent):
        esito["limitazioni"].append("Nessuna metrica usage_MB per corroborare l'evento.")
    return esito
