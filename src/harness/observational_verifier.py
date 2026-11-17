"""Primo gate osservativo per la verifica PAVE-inspired.

Confronta una RootCause gia' formulata con i candidati delle otto regole.
Non interpreta un'anomalia come dimostrazione causale, non corregge predizioni,
non chiama LLM e non accede alla ground truth.

Questo modulo e' intenzionalmente separato dal runner: prima test offline e
verifica del contratto, poi un esperimento di ablazione versionato.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from output.openrca_contract import DATETIME_FORMAT, RootCause


# Versioni dei report accettate: una versione diversa significa che il formato non è quello atteso.
_RULE_REPORT_VERSION = "rule_based_A1_R_v1"
_UNIFIED_REPORT_VERSION = "unified_evidence_v2"
# Fuso orario in cui OpenRCA Market scrive gli istanti dei guasti.
_LOCAL_TZ = ZoneInfo("Asia/Shanghai")


def _timestamp_unix(root_cause: RootCause) -> int:
    """OpenRCA Market usa timestamp in ora locale Asia/Shanghai.

    Converte la data/ora scritta nella causa radice predetta in secondi unix (UTC).
    """
    # Si legge la stringa con il formato del contratto e si dichiara il fuso locale, poi si converte.
    observed = datetime.strptime(
        root_cause.occurrence_datetime, DATETIME_FORMAT
    )
    return int(observed.replace(tzinfo=_LOCAL_TZ).timestamp())


def _componente_equivalente(predetto: str, candidato: str) -> bool:
    """Accetta il suffisso del container, MAI il nodo come alias del container.

    node-5.frontend-0 puo' identificare il container frontend-0.
    node-5 NON e' equivalente a node-5.frontend-0.
    """
    # Stesso nome esatto.
    if predetto == candidato:
        return True
    # Altrimenti il candidato deve essere un container (`nodo.nome`) e il predetto coincidere col suo suffisso.
    return "." in candidato and predetto == candidato.split(".", 1)[1]


def _classe_equivalente(predetta: str, candidata: str) -> bool:
    """Confronto lessicale conservativo: non indovina sinonimi tecnici."""
    return " ".join(predetta.split()).casefold() == (
        " ".join(candidata.split()).casefold()
    )


def verifica_coerenza_osservativa(
    root_cause: RootCause,
    evidence_report: dict | None,
    *,
    start_unix: int,
    end_unix: int,
    tolleranza_secondi: int = 60,
) -> dict:
    """Verifica componente, classe e prossimita' temporale del segnale.

    Stati:
      - non_valutabile: dati o sezione regole assenti.
      - fuori_finestra: predizione esterna alla finestra investigativa.
      - nessuna_corrispondenza: nessun candidato R01-R11 della stessa
        classe e componente e' stato *riportato*.
      - tempo_non_corroborato: componente e classe coincidono, ma non
        la finestra del segnale osservato.
      - coerente_con_segnale: coincidenza osservativa; NON prova causale.

    Nessuno di questi stati certifica la root cause o ne dimostra l'assenza.
    L'assenza di candidati puo' dipendere da classi non coperte o da budget.

    Argomenti:
      root_cause          causa radice predetta dal modello (componente, classe, istante).
      evidence_report     report unificato ("unified_evidence_v2") oppure None se non disponibile.
      start_unix, end_unix  finestra del caso, in secondi unix; deve coincidere con quella dei report.
      tolleranza_secondi  margine in secondi attorno al periodo del segnale entro cui l'istante predetto
                          si considera vicino.

    Restituisce un dizionario con lo stato, i candidati corrispondenti (`matches`), i conteggi e una nota.
    `causa_verificata` è sempre False.

    Passi: (1) controllo degli argomenti; (2) l'istante predetto è nella finestra?; (3) il report c'è
    ed è coerente con il caso?; (4) esame dei candidati (componente, classe, vicinanza nel tempo);
    (5) scelta dello stato finale.
    """
    # --- 1. Controllo degli argomenti.
    if not isinstance(root_cause, RootCause):
        raise TypeError("RootCause richiesto")
    if (
        type(start_unix) is not int or type(end_unix) is not int
        or start_unix >= end_unix
    ):
        raise ValueError("Finestra del caso non valida")
    if type(tolleranza_secondi) is not int or tolleranza_secondi < 0:
        raise ValueError("Tolleranza temporale non valida")

    # Istante predetto in secondi unix e parte comune di tutte le risposte (`base`): ogni esito la
    # riprende e vi aggiunge stato, nota ed eventuali candidati.
    predicted_time = _timestamp_unix(root_cause)
    base = {
        "versione": "observational_verification_v0",
        "componente_predetto": root_cause.component,
        "classe_predetta": root_cause.reason,
        "timestamp_predetto_unix": predicted_time,
        "intervallo_analizzato_unix": [start_unix, end_unix],
        "tolleranza_secondi": tolleranza_secondi,
        "matches": [],
        "causa_verificata": False,
    }

    # --- 2. Un istante predetto fuori dalla finestra osservabile non si può verificare.
    if not start_unix <= predicted_time < end_unix:
        return {
            **base,
            "stato": "fuori_finestra",
            "nota": "Timestamp fuori dalla finestra osservabile; nessuna conclusione causale.",
        }

    # --- 3. Il report: se manca non si può valutare; se esiste deve avere la versione e la finestra
    # del caso, altrimenti si solleva un errore (dati incoerenti, non un semplice "non valutabile").
    if evidence_report is None:
        return {
            **base,
            "stato": "non_valutabile",
            "nota": "Nessun report disponibile: non significa assenza di guasto.",
        }
    if not isinstance(evidence_report, dict):
        raise TypeError("Report evidenze non valido")
    if evidence_report.get("versione") != _UNIFIED_REPORT_VERSION:
        raise ValueError("Versione del report evidenze non supportata")

    case = evidence_report.get("caso")
    if not isinstance(case, dict):
        raise ValueError("Metadati caso mancanti nel report")
    if (case.get("start_unix") != start_unix or
            case.get("end_unix") != end_unix):
        raise ValueError("Finestra del report non coincide con il caso")

    # Sezione delle regole: assente = variante dell'esperimento senza regole (non valutabile).
    rules = evidence_report.get("regole_diagnostiche_v0")
    if rules is None:
        return {
            **base,
            "stato": "non_valutabile",
            "nota": "La variante non contiene regole diagnostiche.",
        }
    if not isinstance(rules, dict) or rules.get("versione") != _RULE_REPORT_VERSION:
        raise ValueError("Report regole non valido")
    rule_window = rules.get("finestra")
    if not isinstance(rule_window, dict) or (
        rule_window.get("start_unix") != start_unix
        or rule_window.get("end_unix") != end_unix
    ):
        raise ValueError("Finestra del report regole incoerente")

    candidates = rules.get("candidati_riportati")
    omitted = rules.get("candidati_omessi_per_budget")
    if (
        not isinstance(candidates, list) or
        type(omitted) is not int or omitted < 0
    ):
        raise ValueError("Conteggi o lista candidati non validi")

    # --- 4. Esame dei candidati riportati. `components_matching` conta quelli con lo stesso componente
    # predetto; `matches` raccoglie quelli che hanno anche la stessa classe.
    matches = []
    components_matching = 0
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            raise ValueError("Candidato non valido")
        first = candidate.get("timestamp_primo_segnale_unix")
        last = candidate.get("timestamp_ultimo_segnale_unix")
        component = candidate.get("componente_telemetria")
        category = candidate.get("classe_candidata")
        rule_id = candidate.get("regola")
        if (
            type(first) is not int or type(last) is not int or
            not start_unix <= first <= last < end_unix or
            not isinstance(component, str) or not component or
            not isinstance(category, str) or not category or
            not isinstance(rule_id, str) or not rule_id
        ):
            raise ValueError(f"Candidato {index} malformato o fuori finestra")

        if not _componente_equivalente(root_cause.component, component):
            continue
        components_matching += 1
        if not _classe_equivalente(root_cause.reason, category):
            continue

        # Vicinanza temporale: l'istante predetto cade nel periodo del segnale, allargato della tolleranza.
        temporal_match = (
            first - tolleranza_secondi <= predicted_time <=
            last + tolleranza_secondi
        )
        matches.append({
            "regola": rule_id,
            "componente_telemetria": component,
            "classe_candidata": category,
            "primo_segnale_unix": first,
            "ultimo_segnale_unix": last,
            "vicinanza_temporale": temporal_match,
            "provenienza": f"regole_diagnostiche_v0.candidati_riportati[{index}]",
        })

    # --- 5. Stato finale: coerente se almeno un candidato corrisponde anche nel tempo; altrimenti
    # "tempo non corroborato" se corrisponde solo per componente e classe; altrimenti nessuna corrispondenza.
    if matches and any(item["vicinanza_temporale"] for item in matches):
        status = "coerente_con_segnale"
    elif matches:
        status = "tempo_non_corroborato"
    else:
        status = "nessuna_corrispondenza"

    return {
        **base,
        "stato": status,
        "matches": matches,
        "componenti_con_candidati": components_matching,
        "candidati_omessi_per_budget": omitted,
        "copertura_candidati_completa": omitted == 0,
        "nota": (
            "Un accordo con un candidato e' solo coerenza osservativa; "
            "non prova causa radice, meccanismo o propagazione. "
            "Nessuna corrispondenza non prova assenza di guasto."
        ),
    }
