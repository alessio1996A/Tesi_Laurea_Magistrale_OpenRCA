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

        gruppi = []
        gruppo_corrente = []

        for evento in eventi:

            if not gruppo_corrente:
                gruppo_corrente = [evento]
                continue

            # Confrontiamo il nuovo evento con il primo
            # del gruppo, per limitare la durata del cluster.
            primo = gruppo_corrente[0]["timestamp_inizio"]
            corrente = evento["timestamp_inizio"]

            if corrente - primo <= max_distanza_secondi:
                gruppo_corrente.append(evento)

            else:
                gruppi.append(gruppo_corrente)
                gruppo_corrente = [evento]

        if gruppo_corrente:
            gruppi.append(gruppo_corrente)

        # Convertiamo i gruppi in pattern strutturati.
        for gruppo in gruppi:

            kpi = sorted({
                evento["kpi"]
                for evento in gruppo
            })

            # Richiediamo almeno due KPI distinti.
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