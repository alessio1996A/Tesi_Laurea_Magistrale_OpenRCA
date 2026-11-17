"""Riepilogo compatto delle evidenze annotate: aggregazione e selezione con un budget massimo.

Riceve il report `quality_annotations_v1` (prodotto da `harness/evidence_selector.py`) e lo riduce a poche
"unità investigative" da mostrare all'agente: prima aggrega i gruppi che descrivono lo stesso fenomeno
(repliche sincronizzate, avvisi sulla capacità disco dello stesso nodo), poi ne sceglie al massimo
`max_evidenze` con criteri deterministici (correlazioni multi-replica, conferma sul nodo ospitante,
varietà di famiglie di metriche e di componenti).

Le priorità sono euristiche per decidere cosa guardare per prime, non una stima di causalità. Le unità non
selezionate restano tracciabili nel report. Nessun LLM e nessuna ground truth.
"""

from collections import Counter


# Ordine di priorità investigativa: numero più basso = da guardare per prima. Sono etichette provvisorie.
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

    Argomenti:
      annotazioni         report `quality_annotations_v1` (gruppi già annotati con priorità e repliche).
      max_evidenze        numero massimo di unità da selezionare (è un tetto: può non essere raggiunto).
      tolleranza_secondi  distanza massima tra gli inizi di due unità per aggregarle o corroborarle.

    Restituisce un report `evidence_summary_v1` con le unità selezionate, le metainformazioni di quelle
    non selezionate, i conteggi e la distribuzione delle priorità.

    Passi: (1) ogni gruppo diventa un'unità investigativa; (2) si cerca un'unità con cui aggregarlo;
    (3) si aggrega; (4) si selezionano le unità per il riepilogo (4A–4F); (5) si registrano quelle
    omesse; (6) si costruisce il report.
    """

    if annotazioni.get("versione") != "quality_annotations_v1":
        raise ValueError("Versione annotazioni non supportata.")

    if max_evidenze < 1:
        raise ValueError("max_evidenze deve essere >= 1.")

    if tolleranza_secondi < 0:
        raise ValueError("Tolleranza non valida.")

    gruppi = annotazioni["gruppi"]

    # Elenco delle unità investigative (gruppi eventualmente già aggregati tra loro).
    unita = []

    # =====================================================
    # 1. TRASFORMAZIONE IN UNITÀ INVESTIGATIVE
    # =====================================================

    for indice, gruppo in enumerate(gruppi):

        priorita = gruppo["priorita_indagine"]

        if priorita not in PRIORITA:
            raise ValueError(f"Priorità sconosciuta: {priorita}")

        repliche = gruppo["repliche_sincronizzate"]

        # Tipo dell'unità: anomalia che coinvolge almeno due repliche, avviso di coerenza della misura
        # del disco, oppure anomalia singola.
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

        # Nuova unità costruita da un solo gruppo; `gruppi_origine` conserva l'indice del gruppo
        # originale per poter risalire al report completo.
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

        # `destinazione` sarà la prima unità già presente con cui la nuova può fondersi (None = nessuna).
        # Condizioni comuni: stesso tipo, stessa sorgente, stessa famiglia, inizi vicini nel tempo.
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

        # Nessuna unità compatibile: la nuova unità resta separata.
        if destinazione is None:
            unita.append(nuova)
            continue

        # Fusione: si uniscono gli elenchi (senza duplicati), si estende l'intervallo osservato e si tiene
        # la variazione percentuale massima.
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
    # 4. SELEZIONE DELLE EVIDENZE
    # =====================================================
    #
    # Obiettivi:
    # - mantenere le correlazioni multi-replica;
    # - cercare conferme sul nodo ospitante;
    # - rappresentare famiglie diverse;
    # - evitare molte piccole variazioni ridondanti.
    #
    # Nessuna evidenza viene cancellata dal report
    # originale. Le unità non selezionate rimangono
    # tracciabili tramite gruppi_origine.
    # =====================================================

    unita.sort(
        key=lambda e: (
            PRIORITA[e["priorita_indagine"]],
            e["inizio_osservato_unix"],
            e["sorgente"],
            e["componenti"][0]
        )
    )

    selezionate = []

    # Massimo due unità di variazione relativa modesta
    # nel riepilogo. È una regola sperimentale.
    max_modeste = min(2, max_evidenze)

    def gia_selezionata(evidenza):
        """True se questa stessa unità (confronto per identità, non per valore) è già tra le selezionate."""
        return any(
            evidenza is scelta
            for scelta in selezionate
        )

    def aggiungi(evidenza):
        """
        Aggiunge una unità se il budget e i vincoli
        di selezione lo permettono.

        Restituisce True se l'unità è stata aggiunta, False se il tetto `max_evidenze` è raggiunto,
        se è già presente o se supererebbe il limite delle unità a variazione modesta.
        """

        if len(selezionate) >= max_evidenze:
            return False

        if gia_selezionata(evidenza):
            return False

        if (
            evidenza["priorita_indagine"]
            == "variazione_relativa_modesta"
        ):
            modeste_attuali = sum(
                e["priorita_indagine"]
                == "variazione_relativa_modesta"
                for e in selezionate
            )

            if modeste_attuali >= max_modeste:
                return False

        selezionate.append(evidenza)
        return True

    # =====================================================
    # 4A. CORRELAZIONI MULTI-REPLICA
    # =====================================================

    # Queste evidenze sono particolarmente utili
    # perché rappresentano più componenti che
    # mostrano un comportamento temporalmente simile.

    multi_replica = [
        e for e in unita
        if e["tipo"] == "anomalia_multi_replica"
    ]

    for evidenza in multi_replica:
        aggiungi(evidenza)

    # =====================================================
    # 4B. CORROBORAZIONE SUL NODO OSPITANTE
    # =====================================================

    # Se un'anomalia multi-replica coinvolge container
    # sullo stesso nodo, cerchiamo una evidenza della
    # stessa famiglia sul nodo, in un intervallo vicino.
    #
    # Non assumiamo causalità: si tratta soltanto
    # di una corroborazione temporale.

    for evidenza in multi_replica:

        if not gia_selezionata(evidenza):
            continue

        nodi_coinvolti = {
            componente.split(".", 1)[0]
            for componente in evidenza["componenti"]
            if "." in componente
        }

        candidati_nodo = []

        for candidata in unita:

            if candidata["sorgente"] != "node_metrics":
                continue

            if candidata["famiglia"] != evidenza["famiglia"]:
                continue

            if not any(
                componente in nodi_coinvolti
                for componente in candidata["componenti"]
            ):
                continue

            distanza = abs(
                candidata["inizio_osservato_unix"]
                - evidenza["inizio_osservato_unix"]
            )

            if distanza > tolleranza_secondi:
                continue

            candidati_nodo.append(
                (distanza, candidata)
            )

        candidati_nodo.sort(
            key=lambda elemento: (
                elemento[0],
                PRIORITA[
                    elemento[1]["priorita_indagine"]
                ],
                elemento[1]["componenti"][0]
            )
        )

        if candidati_nodo:
            aggiungi(candidati_nodo[0][1])

    # =====================================================
    # 4C. DIVERSITÀ TRA FAMIGLIE DI METRICHE
    # =====================================================

    # Se esistono anomalie di memoria, disco e I/O,
    # cerchiamo di includere almeno una unità per
    # ciascuna famiglia, rispettando il budget.

    famiglie_presenti = sorted({
        e["famiglia"] for e in unita
    })

    for famiglia in famiglie_presenti:

        gia_rappresentata = any(
            e["famiglia"] == famiglia
            for e in selezionate
        )

        if gia_rappresentata:
            continue

        candidati = [
            e for e in unita
            if e["famiglia"] == famiglia
            and not gia_selezionata(e)
        ]

        if candidati:
            aggiungi(candidati[0])

    # =====================================================
    # 4D. PRIORITÀ E DIVERSITÀ DEI COMPONENTI
    # =====================================================

    # Prima selezioniamo altre evidenze non modeste,
    # preferendo combinazioni componente/famiglia
    # che non sono ancora rappresentate.

    def firma_componente(evidenza):
        """Chiave "famiglia + componenti" di un'unità: due unità con la stessa chiave sono considerate ridondanti."""
        return (
            evidenza["famiglia"],
            tuple(evidenza["componenti"])
        )

    for evidenza in unita:

        if len(selezionate) >= max_evidenze:
            break

        if gia_selezionata(evidenza):
            continue

        if (
            evidenza["priorita_indagine"]
            == "variazione_relativa_modesta"
        ):
            continue

        firma = firma_componente(evidenza)

        gia_rappresentata = any(
            firma_componente(e) == firma
            for e in selezionate
        )

        if not gia_rappresentata:
            aggiungi(evidenza)

    # =====================================================
    # 4E. COMPLETAMENTO CON ALTRE EVIDENZE
    # =====================================================

    # Completiamo prima con eventuali altre evidenze
    # non modeste, poi con poche variazioni modeste.
    #
    # max_evidenze è un tetto massimo:
    # non è obbligatorio raggiungerlo.

    for evidenza in unita:

        if (
            evidenza["priorita_indagine"]
            != "variazione_relativa_modesta"
        ):
            aggiungi(evidenza)

    for evidenza in unita:

        if (
            evidenza["priorita_indagine"]
            == "variazione_relativa_modesta"
        ):
            aggiungi(evidenza)

    # =====================================================
    # 4F. ORDINAMENTO FINALE
    # =====================================================

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