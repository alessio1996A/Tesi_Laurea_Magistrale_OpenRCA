"""Rilevatore comune, deterministico e offline, di anomalie sulla telemetria dei NODI (OpenRCA Market).

Questo modulo contiene la logica condivisa dalle cinque regole sui nodi di RQ1
(R07 CPU, R08 memoria, R09 lettura disco, R10 scrittura disco, R11 spazio disco).
Ogni regola e' un involucro sottile che sceglie il KPI e le soglie e delega qui il calcolo.

Principi:
- nessuna ground truth, nessuna chiamata a un modello, nessun accesso alla rete:
  a parita' di dati l'esito e' sempre lo stesso (deterministico);
- una variazione rispetto alla baseline e' un'IPOTESI da verificare, non la prova di un
  guasto ne' della sua causa radice;
- la baseline e' scelta da chi chiama e puo' essere gia' contaminata dal guasto.

Idea del metodo (in breve):
1. si prendono due finestre dello stesso KPI: baseline [start, baseline_end) e ricerca [baseline_end, end);
2. dalla baseline si calcola una soglia robusta (mediana + MAD, con minimi relativo e assoluto);
3. si cerca nella finestra di ricerca una sequenza di campioni consecutivi sopra soglia;
4. se la sequenza c'e' si restituisce un "candidato da verificare", altrimenti "nessun candidato".
"""
from __future__ import annotations
import math
from typing import Any
import pandas as pd

# Colonne che la tabella di telemetria deve avere: istante (unix), componente, nome del KPI, valore.
REQUIRED = {"timestamp", "cmdb_id", "kpi_name", "value"}


def get_series(scope: pd.DataFrame, kpi: str) -> pd.Series:
    """Estrae da `scope` la serie temporale di un KPI: indice = timestamp, valori = numeri finiti.

    Passi: seleziona le righe del KPI; converte timestamp e valore in numeri (i non numerici
    diventano NaN); scarta NaN e infiniti; se ci sono piu' valori allo stesso istante ne prende
    la MEDIANA (non la somma); ordina per tempo. Se il KPI non c'e', restituisce una serie vuota.
    """
    # Si tengono solo le righe del KPI richiesto e le due colonne che servono.
    d = scope.loc[scope["kpi_name"].eq(kpi), ["timestamp", "value"]].copy()
    if d.empty:
        return pd.Series(dtype="float64")
    # Conversione numerica "tollerante": i valori non convertibili diventano NaN e poi vengono scartati.
    d["timestamp"] = pd.to_numeric(d["timestamp"], errors="coerce")
    d["value"] = pd.to_numeric(d["value"], errors="coerce")
    d = d.replace([float("inf"), -float("inf")], float("nan")).dropna()
    # Duplicati sullo stesso istante: mediana, cosi' nessun valore viene sommato o gonfiato.
    return d.groupby("timestamp")["value"].median().sort_index()


def evaluate_node_signal(
    telemetry: pd.DataFrame, component: str,
    start_unix: int, baseline_end_unix: int, end_unix: int,
    *, rule_id: str, cls: str, metric: str, extra_metric: str | None = None,
    relative_increase: float = .20, absolute_increase: float = 5.,
    robust_factor: float = 3.5, consecutive: int = 3,
    min_baseline: int = 8, max_gap_factor: float = 1.5,
) -> dict[str, Any]:
    """Cerca un aumento persistente di un KPI di un nodo rispetto alla sua baseline.

    Finestre (in secondi unix): baseline = [start_unix, baseline_end_unix), ricerca =
    [baseline_end_unix, end_unix). Non si guarda mai oltre `end_unix`.

    Parametri della regola (li passa il chiamante):
      rule_id, cls   identificativo (es. "R07") e nome della classe candidata (es. "node CPU load");
      metric         KPI principale su cui si decide;
      extra_metric   KPI accessorio, riportato come informazione ma MAI usato per decidere.

    Parametri della soglia (valori di default esplorativi, NON calibrati sulla ground truth):
      relative_increase  aumento minimo relativo sulla mediana di baseline (0.20 = +20%);
      absolute_increase  aumento minimo assoluto, nell'unita' del KPI (serve se la baseline e' piatta);
      robust_factor      moltiplicatore della MAD "scalata" (1.4826 * MAD ~ deviazione standard);
      consecutive        quanti campioni consecutivi sopra soglia servono;
      min_baseline       campioni minimi richiesti nella baseline;
      max_gap_factor     due campioni sono "consecutivi" se distano al piu' cadenza * questo fattore.

    Restituisce un dizionario con `status` pari a uno di:
      "evidenza_insufficiente"   dati non sufficienti o non interpretabili: la regola si astiene;
      "nessun_candidato"         dati sufficienti, ma nessuna sequenza persistente sopra soglia;
      "candidato_da_verificare"  trovata una sequenza: `ipotesi` contiene primo/ultimo istante e conteggio.
    Solleva TypeError/ValueError se gli argomenti non sono validi (errori di uso, non di dati).
    """
    # --- 1. Controllo degli argomenti: un uso scorretto solleva un errore, non produce un esito.
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

    # --- 2. Esito iniziale: parte "evidenza_insufficiente" e viene aggiornato solo se i controlli passano.
    #        Le limitazioni elencano cio' che l'esito NON puo' affermare.
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

    # --- 3. Selezione dei dati: solo il componente richiesto, solo l'intervallo [start, end).
    t = pd.to_numeric(telemetry["timestamp"], errors="coerce")
    scope = telemetry.loc[telemetry["cmdb_id"].eq(component) & t.ge(start_unix) & t.lt(end_unix)]
    series = get_series(scope, metric)
    # Si separa la serie in baseline (riferimento) e ricerca (dove cercare l'anomalia).
    base = series.loc[(series.index >= start_unix) & (series.index < baseline_end_unix)]
    search = series.loc[(series.index >= baseline_end_unix) & (series.index < end_unix)]
    ev = out["evidenze"]
    ev["kpi_principale"] = metric
    ev["campioni_baseline"] = int(len(base))
    ev["campioni_ricerca"] = int(len(search))

    # --- 4. Astensioni: troppo pochi campioni, oppure valori negativi (semantica del KPI incerta).
    if len(base) < min_baseline or len(search) < consecutive:
        out["limitazioni"].append("Campioni insufficienti nella baseline o nella ricerca.")
        return out
    if (base < 0).any() or (search < 0).any():
        out["limitazioni"].append("Valori KPI negativi: semantica incerta.")
        return out

    # --- 5. Soglia robusta. Mediana e MAD (mediana delle distanze dalla mediana) resistono ai picchi
    #        nella baseline. 1.4826 rende la MAD confrontabile con una deviazione standard.
    #        La soglia e' il MASSIMO di tre criteri: statistico, aumento relativo e aumento assoluto
    #        (gli ultimi due evitano soglie troppo basse quando la baseline e' costante, MAD = 0).
    med = float(base.median())
    mad = float((base - med).abs().median())
    threshold = max(med + robust_factor * 1.4826 * mad,
                    med * (1 + relative_increase), med + absolute_increase)
    ev.update({"baseline_mediana": med, "baseline_mad": mad,
               "soglia_esplorativa": float(threshold),
               "massimo_ricerca": float(search.max()),
               "campioni_oltre_soglia": int((search > threshold).sum())})

    # --- 6. Cadenza di campionamento: mediana delle distanze tra istanti consecutivi (di solito 60 s,
    #        ma non lo si assume). Serve a riconoscere i "buchi" nei dati.
    intervals = series.index.to_series().diff().dropna()
    intervals = intervals.loc[intervals > 0]
    if intervals.empty:
        out["limitazioni"].append("Cadenza non stimabile.")
        return out
    cadence = float(intervals.median())
    ev["cadenza_mediana_secondi"] = cadence
    max_gap = cadence * max_gap_factor

    # --- 7. Ricerca della prima sequenza di `consecutive` campioni sopra soglia, senza buchi piu' grandi di
    #        `max_gap`. `first`/`last` = primo e ultimo istante della sequenza in corso, `count` = sua lunghezza.
    first = last = None
    count = 0
    candidate = None
    for ts, value in search.items():
        ts = float(ts)
        if value > threshold:
            # Sopra soglia: si ricomincia la sequenza se e' la prima o se c'e' un buco, altrimenti la si allunga.
            if last is None or ts - last > max_gap:
                first, count = ts, 1
            else:
                count += 1
            last = ts
            if count >= consecutive:
                # Sequenza abbastanza lunga: si prende la PRIMA trovata e ci si ferma.
                candidate = (first, last, count)
                break
        else:
            # Un campione sotto soglia interrompe la sequenza.
            first = last = None
            count = 0
    if candidate is None:
        out["status"] = "nessun_candidato"
        return out

    # --- 8. Candidato trovato: e' un'ipotesi da verificare (non una diagnosi).
    first, last, count = candidate
    out["status"] = "candidato_da_verificare"
    out["ipotesi"] = {"classe": cls,
                       "timestamp_primo_segnale_unix": int(first),
                       "timestamp_ultimo_segnale_unix": int(last),
                       "campioni_consecutivi": int(count)}

    # --- 9. KPI accessorio (se previsto): solo informazione descrittiva sull'evento, non conferma nulla.
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
