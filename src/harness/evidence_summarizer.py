from collections import Counter


PRIORITA = {
    "correlazione_multi_replica": 0,
    "da_approfondire": 1,
    "verificare_coerenza_telemetria": 2,
    "variazione_relativa_modesta": 3,
}


def sintetizza_evidenze(
    annotazioni: dict,
    max_evidenze: int = 8,
    tolleranza_secondi: int = 60
) -> dict:
    """
    Costruisce un riepilogo compatto delle evidenze.

    - Aggrega le segnalazioni sincronizzate delle repliche.
    - Aggrega gli avvisi relativi alla capacità del disco
      sullo stesso nodo e nello stesso intervallo.
    - Ordina secondo priorità investigative provvisorie.
    - Mantiene il riferimento ai gruppi originali.
    - Non identifica la root cause.

    Le evidenze escluse dal riepilogo restano disponibili
    nel report originale.
    """

    if annotazioni.get("versione") != "quality_annotations_v1":
        raise ValueError("Versione annotazioni non supportata.")

    if max_evidenze < 1:
        raise ValueError("max_evidenze deve essere >= 1.")

    if tolleranza_secondi < 0:
        raise ValueError("Tolleranza non valida.")

    gruppi = annotazioni["gruppi"]

    unita = []

    # =====================================================
    # 1. TRASFORMAZIONE IN UNITÀ INVESTIGATIVE
    # =====================================================

    for indice, gruppo in enumerate(gruppi):

        priorita = gruppo["priorita_indagine"]

        if priorita not in PRIORITA:
            raise ValueError(f"Priorità sconosciuta: {priorita}")

        repliche = gruppo["repliche_sincronizzate"]

        multi_replica = (
            priorita == "correlazione_multi_replica"
            and len(repliche) >= 2
        )

        avviso_disco = (
            priorita == "verificare_coerenza_telemetria"
            and gruppo["capacita_disco_da_verificare"]
        )

        if multi_replica:
            tipo = "anomalia_multi_replica"
        elif avviso_disco:
            tipo = "verifica_telemetria_disco"
        else:
            tipo = "anomalia_singola"

        nuova = {
            "tipo": tipo,
            "sorgente": gruppo["sorgente"],
            "famiglia": gruppo["famiglia"],
            "priorita_indagine": priorita,
            "componenti": [gruppo["componente"]],
            "direzioni": [gruppo["direzione"]],
            "kpi": sorted(set(gruppo["kpi"])),
            "inizio_osservato_unix":
                int(gruppo["inizio_osservato_unix"]),
            "fine_osservata_unix":
                int(gruppo["fine_osservata_unix"]),
            "variazione_massima_pct":
                gruppo["variazione_massima_pct"],
            "vicino_inizio_finestra":
                bool(gruppo["vicino_inizio_finestra"]),
            "vicino_fine_finestra":
                bool(gruppo["vicino_fine_finestra"]),
            "repliche_correlate": (
                sorted(set(repliche))
                if multi_replica else []
            ),
            "gruppi_origine": [indice]
        }

        # =================================================
        # 2. RICERCA DI EVIDENZE DA AGGREGARE
        # =================================================

        destinazione = None

        for esistente in unita:

            if esistente["tipo"] != tipo:
                continue

            if esistente["sorgente"] != nuova["sorgente"]:
                continue

            if esistente["famiglia"] != nuova["famiglia"]:
                continue

            distanza = abs(
                esistente["inizio_osservato_unix"]
                - nuova["inizio_osservato_unix"]
            )

            if distanza > tolleranza_secondi:
                continue

            if tipo == "anomalia_multi_replica":

                # Le repliche devono appartenere allo
                # stesso insieme di correlazione.
                stesso_insieme = (
                    esistente["repliche_correlate"]
                    == nuova["repliche_correlate"]
                )

                stessa_direzione = (
                    esistente["direzioni"]
                    == nuova["direzioni"]
                )

                if stesso_insieme and stessa_direzione:
                    destinazione = esistente
                    break

            elif tipo == "verifica_telemetria_disco":

                # Due KPI del disco relativi allo stesso
                # nodo possono descrivere un unico problema
                # di coerenza della misura.
                stesso_nodo = (
                    esistente["componenti"][0]
                    == nuova["componenti"][0]
                )

                if stesso_nodo:
                    destinazione = esistente
                    break

        # =================================================
        # 3. AGGREGAZIONE
        # =================================================

        if destinazione is None:
            unita.append(nuova)
            continue

        for campo in ("componenti", "direzioni", "kpi"):
            destinazione[campo] = sorted(
                set(destinazione[campo])
                | set(nuova[campo])
            )

        destinazione["gruppi_origine"] = sorted(
            set(destinazione["gruppi_origine"])
            | set(nuova["gruppi_origine"])
        )

        destinazione["fine_osservata_unix"] = max(
            destinazione["fine_osservata_unix"],
            nuova["fine_osservata_unix"]
        )

        destinazione["vicino_inizio_finestra"] |= (
            nuova["vicino_inizio_finestra"]
        )

        destinazione["vicino_fine_finestra"] |= (
            nuova["vicino_fine_finestra"]
        )

        valori = [
            v for v in (
                destinazione["variazione_massima_pct"],
                nuova["variazione_massima_pct"]
            )
            if v is not None
        ]

        destinazione["variazione_massima_pct"] = (
            max(valori) if valori else None
        )

    # =====================================================
    # 4. ORDINAMENTO INVESTIGATIVO
    # =====================================================

    unita.sort(
        key=lambda e: (
            PRIORITA[e["priorita_indagine"]],
            e["inizio_osservato_unix"],
            e["sorgente"],
            e["componenti"][0]
        )
    )

    # Manteniamo almeno un esempio di ogni categoria
    # presente, quando il budget lo permette.
    selezionate = []
    categorie_incluse = set()

    for evidenza in unita:

        categoria = evidenza["priorita_indagine"]

        if categoria not in categorie_incluse:
            selezionate.append(evidenza)
            categorie_incluse.add(categoria)

        if len(selezionate) >= max_evidenze:
            break

    # Completiamo il budget secondo l'ordine
    # investigativo, senza ripetere le unità.
    for evidenza in unita:

        if len(selezionate) >= max_evidenze:
            break

        if not any(
            evidenza is scelta
            for scelta in selezionate
        ):
            selezionate.append(evidenza)

    selezionate.sort(
        key=lambda e: (
            PRIORITA[e["priorita_indagine"]],
            e["inizio_osservato_unix"],
            e["componenti"][0]
        )
    )

    # =====================================================
    # 5. METADATI DELLE EVIDENZE NON SELEZIONATE
    # =====================================================

    omesse = [
        evidenza
        for evidenza in unita
        if not any(
            evidenza is scelta
            for scelta in selezionate
        )
    ]

    distribuzione = Counter(
        e["priorita_indagine"]
        for e in unita
    )

    # =====================================================
    # 6. REPORT FINALE
    # =====================================================

    return {
        "versione": "evidence_summary_v1",
        "gruppi_originali": len(gruppi),
        "unita_dopo_aggregazione": len(unita),
        "unita_selezionate": len(selezionate),
        "unita_non_selezionate": len(omesse),
        "distribuzione_priorita": dict(
            sorted(distribuzione.items())
        ),
        "evidenze": selezionate,
        "non_selezionate": [
            {
                "tipo": e["tipo"],
                "componenti": e["componenti"],
                "famiglia": e["famiglia"],
                "gruppi_origine": e["gruppi_origine"]
            }
            for e in omesse
        ],
        "nota": (
            "Le priorita sono euristiche investigative. "
            "Le evidenze non dimostrano causalita. "
            "Le unita non selezionate restano disponibili "
            "nel report originale."
        )
    }