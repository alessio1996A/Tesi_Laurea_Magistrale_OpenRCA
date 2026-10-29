def costruisci_report_unificato(
    report_v2: dict,
    sintesi: dict,
    max_evidenze_totali: int = 10
) -> dict:
    """
    Unifica le evidenze A1-v1 e quelle multi-risorsa.

    INPUT:
      report_v2: report dell'Evidence Builder A1-v2,
                 contenente anche il report A1-v1.

      sintesi: output di sintetizza_evidenze().

    OUTPUT:
      Un report compatto con:
      - anomalie CPU/load originali;
      - pattern strutturali originali;
      - evidenze multi-risorsa selezionate;
      - provenienza e conteggi delle omissioni.

    Non utilizza ground truth.
    Non identifica la root cause.
    Non chiama l'LLM.
    """

    # =====================================================
    # 1. VALIDAZIONE
    # =====================================================

    if report_v2.get("versione") != "A1-v2":
        raise ValueError(
            "È richiesto un report A1-v2."
        )

    if sintesi.get("versione") != "evidence_summary_v1":
        raise ValueError(
            "Versione del Summarizer non supportata."
        )

    if max_evidenze_totali < 1:
        raise ValueError(
            "max_evidenze_totali deve essere >= 1."
        )

    report_v1 = report_v2["evidenze_v1"]

    if report_v1.get("versione") != "A1-v1":
        raise ValueError(
            "Report A1-v1 non valido."
        )

    # =====================================================
    # 2. EVIDENZE CPU/LOAD ORIGINALI
    # =====================================================

    cpu_load = []

    anomalie_v1 = report_v1["anomalie"]

    for indice, anomalia in enumerate(
        anomalie_v1["segnalazioni"]
    ):

        cpu_load.append({
            "fonte": "A1-v1",
            "categoria": "cpu_load",
            "provenienza": {
                "sezione": "anomalie.segnalazioni",
                "indice": indice
            },
            "componente": anomalia["componente"],
            "kpi": anomalia["kpi"],
            "tipo": anomalia["tipo"],
            "timestamp_inizio": int(
                anomalia["timestamp_inizio"]
            ),
            "mediana": anomalia["mediana"],
            "valore_massimo": anomalia["valore_massimo"],
            "campioni": anomalia["campioni"]
        })

    # Ordinamento indipendente dall'ordine originale.
    cpu_load.sort(
        key=lambda e: (
            e["timestamp_inizio"],
            e["componente"],
            e["kpi"],
            e["provenienza"]["indice"]
        )
    )

    # =====================================================
    # 3. PATTERN STRUTTURALI ORIGINALI
    # =====================================================

    patterns = []

    patterns_v1 = report_v1["patterns"]

    for indice, pattern in enumerate(
        patterns_v1["segnalazioni"]
    ):

        patterns.append({
            "fonte": "A1-v1",
            "categoria": "pattern",
            "provenienza": {
                "sezione": "patterns.segnalazioni",
                "indice": indice
            },
            "componente": pattern["componente"],
            "tipo": pattern["tipo"],
            "timestamp_inizio": int(
                pattern["timestamp_inizio"]
            ),
            "timestamp_fine": int(
                pattern["timestamp_fine"]
            ),
            "numero_anomalie": pattern[
                "numero_anomalie"
            ],
            "kpi_coinvolti": sorted(
                set(pattern["kpi_coinvolti"])
            ),
            "causa_verificata": bool(
                pattern["causa_verificata"]
            )
        })

    patterns.sort(
        key=lambda e: (
            e["timestamp_inizio"],
            e["componente"],
            e["tipo"],
            e["provenienza"]["indice"]
        )
    )

    # =====================================================
    # 4. EVIDENZE MULTI-RISORSA
    # =====================================================

    multi_risorsa = []

    for indice, evidenza in enumerate(
        sintesi["evidenze"]
    ):

        multi_risorsa.append({
            "fonte": "A1-v2",
            "categoria": "multi_risorsa",
            "provenienza": {
                "sezione": "sintesi.evidenze",
                "indice": indice,
                "gruppi_origine": list(
                    evidenza["gruppi_origine"]
                )
            },
            "tipo": evidenza["tipo"],
            "famiglia": evidenza["famiglia"],
            "priorita_indagine": evidenza[
                "priorita_indagine"
            ],
            "componenti": list(
                evidenza["componenti"]
            ),
            "kpi": list(evidenza["kpi"]),
            "timestamp_inizio": int(
                evidenza["inizio_osservato_unix"]
            ),
            "timestamp_fine": int(
                evidenza["fine_osservata_unix"]
            ),
            "variazione_massima_pct": evidenza[
                "variazione_massima_pct"
            ],
            "vicino_inizio_finestra": evidenza[
                "vicino_inizio_finestra"
            ],
            "vicino_fine_finestra": evidenza[
                "vicino_fine_finestra"
            ],
            "repliche_correlate": list(
                evidenza["repliche_correlate"]
            )
        })

    # Conserviamo l'ordine di priorità
    # già prodotto dal Summarizer.

    # =====================================================
    # 5. SELEZIONE CON BUDGET GLOBALE
    # =====================================================

    # Usiamo tre code:
    #  1. Pattern strutturali
    #  2. Anomalie CPU/load
    #  3. Evidenze multi-risorsa
    #
    # Selezioniamo a rotazione, per evitare che
    # una sola categoria occupi tutto il budget.
    #
    # Le categorie non sono prove indipendenti:
    # un pattern può riassumere anomalie già presenti.

    code = [
        patterns,
        cpu_load,
        multi_risorsa
    ]

    posizioni = [0, 0, 0]

    evidenze_finali = []

    while len(evidenze_finali) < max_evidenze_totali:

        aggiunte_nel_giro = 0

        for i, coda in enumerate(code):

            if len(evidenze_finali) >= max_evidenze_totali:
                break

            if posizioni[i] >= len(coda):
                continue

            evidenze_finali.append(
                coda[posizioni[i]]
            )

            posizioni[i] += 1
            aggiunte_nel_giro += 1

        if aggiunte_nel_giro == 0:
            break

    # =====================================================
    # 6. CONTEGGI E OMISSIONI
    # =====================================================

    disponibili = {
        "patterns": len(patterns),
        "cpu_load": len(cpu_load),
        "multi_risorsa": len(multi_risorsa)
    }

    inclusi = {
        "patterns": sum(
            e["categoria"] == "pattern"
            for e in evidenze_finali
        ),
        "cpu_load": sum(
            e["categoria"] == "cpu_load"
            for e in evidenze_finali
        ),
        "multi_risorsa": sum(
            e["categoria"] == "multi_risorsa"
            for e in evidenze_finali
        )
    }

    omessi_budget = {
        categoria: disponibili[categoria]
        - inclusi[categoria]
        for categoria in disponibili
    }

    # Le anomalie omesse da A1-v1 e le unità
    # non selezionate dal Summarizer sono
    # distinte dalle omissioni per budget globale.

    omissioni_precedenti = {
        "anomalie_v1": anomalie_v1[
            "segnalazioni_omesse"
        ],
        "patterns_v1": patterns_v1[
            "segnalazioni_omesse"
        ],
        "unita_multi_risorsa": sintesi[
            "unita_non_selezionate"
        ]
    }

    # =====================================================
    # 7. COSTRUZIONE DEL REPORT FINALE
    # =====================================================

    return {
        "versione": "unified_evidence_v1",

        "caso": dict(report_v1["caso"]),

        "copertura": dict(report_v1["copertura"]),

        "qualita": dict(report_v1["qualita"]),

        "budget_evidenze": max_evidenze_totali,

        "evidenze_totali": len(evidenze_finali),

        "evidenze": evidenze_finali,

        "conteggi": {
            "disponibili": disponibili,
            "inclusi": inclusi,
            "omessi_per_budget": omessi_budget,
            "omessi_precedentemente": omissioni_precedenti
        },

        "limitazioni": [
            "Le evidenze non identificano la root cause.",
            "I pattern possono riassumere anomalie gia riportate.",
            "Le priorita investigative sono euristiche.",
            "Gli episodi al bordo possono essere incompleti.",
            "Alcune evidenze non sono presenti nel riepilogo.",
            "Un KPI anomalo non prova un guasto del componente."
        ]
    }