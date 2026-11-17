"""Raggruppamento di anomalie vicine nel tempo sullo stesso componente.

Se lo stesso componente mostra anomalie su più KPI quasi nello stesso momento (per esempio CPU e
memoria dello stesso container), l'harness le presenta insieme come "pattern candidato". È una
correlazione temporale: non dice quale anomalia sia la causa dell'altra.

Usato da `harness/evidence_builder.py`. Nessun LLM, nessuna ground truth.
"""


def raggruppa_anomalie(
    anomalie: list[dict],
    max_distanza_secondi: int = 180,
    min_kpi: int = 2
) -> list[dict]:
    """
    Raggruppa anomalie dello stesso componente
    che iniziano in momenti temporalmente vicini.

    Produce pattern candidati, non diagnosi causali.
    Non utilizza LLM.

    Argomenti:
      anomalie              lista di dizionari con almeno `componente`, `kpi` e `timestamp_inizio`.
      max_distanza_secondi  due anomalie stanno nello stesso gruppo se la seconda inizia entro questo
                            tempo dalla PRIMA del gruppo (non dall'anomalia precedente).
      min_kpi               numero minimo di KPI distinti che un gruppo deve coinvolgere per diventare
                            un pattern.

    Restituisce i pattern in ordine di istante d'inizio e poi di componente. `causa_verificata` è
    sempre False.
    """

    if max_distanza_secondi < 0 or min_kpi < 1:
        raise ValueError("Parametri non validi.")

    # Separiamo le anomalie in base al componente.
    per_componente = {}

    for anomalia in anomalie:

        componente = anomalia["componente"]

        per_componente.setdefault(
            componente, []
        ).append(anomalia)

    patterns = []

    # Analizziamo ogni nodo/componente separatamente.
    for componente, eventi in per_componente.items():

        # Ordiniamo gli eventi per istante di rilevamento.
        eventi = sorted(
            eventi,
            key=lambda x: x["timestamp_inizio"]
        )

        # Scorriamo gli eventi in ordine di tempo e li accorpiamo in gruppi consecutivi.
        gruppi = []
        gruppo_corrente = []

        for evento in eventi:

            # Il primo evento apre un nuovo gruppo.
            if not gruppo_corrente:
                gruppo_corrente = [evento]
                continue

            # Confrontiamo il nuovo evento con il primo
            # del gruppo, per limitare la durata del cluster.
            primo = gruppo_corrente[0]["timestamp_inizio"]
            corrente = evento["timestamp_inizio"]

            # Abbastanza vicino al primo evento: stesso gruppo. Altrimenti si chiude il gruppo e se ne apre uno nuovo.
            if corrente - primo <= max_distanza_secondi:
                gruppo_corrente.append(evento)

            else:
                gruppi.append(gruppo_corrente)
                gruppo_corrente = [evento]

        # L'ultimo gruppo non viene chiuso dal ciclo: lo aggiungiamo qui.
        if gruppo_corrente:
            gruppi.append(gruppo_corrente)

        # Convertiamo i gruppi in pattern strutturati.
        for gruppo in gruppi:

            # KPI distinti coinvolti nel gruppo (insieme ordinato, senza ripetizioni).
            kpi = sorted({
                evento["kpi"]
                for evento in gruppo
            })

            # Richiediamo almeno `min_kpi` KPI distinti (di default due): più anomalie
            # sullo stesso KPI non bastano a formare un pattern.
            if len(kpi) < min_kpi:
                continue

            timestamps = [
                evento["timestamp_inizio"]
                for evento in gruppo
            ]

            patterns.append({
                "tipo": "anomalie_correlate_temporalmente",
                "componente": componente,
                "numero_anomalie": len(gruppo),
                "numero_kpi": len(kpi),
                "kpi_coinvolti": kpi,
                "timestamp_inizio": min(timestamps),
                "timestamp_fine": max(timestamps),
                "evidenze": gruppo,
                "causa_verificata": False
            })

    # Restituiamo i pattern in ordine temporale.
    return sorted(
        patterns,
        key=lambda p: (
            p["timestamp_inizio"],
            p["componente"]
        )
    )