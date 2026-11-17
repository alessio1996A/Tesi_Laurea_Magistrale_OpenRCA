"""Report unificato delle evidenze: un unico elenco compatto, con un budget globale, da dare all'agente.

Due funzioni, una per versione del report:
- `costruisci_report_unificato` (`unified_evidence_v1`): unisce le anomalie CPU/load e i pattern strutturali
  del report A1-v1 con le evidenze multi-risorsa già riassunte, scegliendo a rotazione tra le tre categorie;
- `costruisci_report_unificato_v2` (`unified_evidence_v2`): parte dal precedente e aggiunge le unità Mesh e le
  evidenze Runtime, scegliendo con criteri investigativi (correlazioni multi-replica, conferma sul nodo
  ospitante, varietà di categorie e famiglie).

La selezione è euristica e non causale: tiene traccia della provenienza di ogni evidenza e di quante ne ha
omesse. Nessun LLM e nessuna ground truth.
"""


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

    Argomenti:
      report_v2            report A1-v2 (versione "A1-v2"); contiene il report A1-v1 in `evidenze_v1`.
      sintesi              riepilogo multi-risorsa ("evidence_summary_v1").
      max_evidenze_totali  budget globale: numero massimo di evidenze nel report finale (>= 1).

    Restituisce un report "unified_evidence_v1" con le evidenze scelte, i conteggi (disponibili, inclusi,
    omessi per budget, omessi in precedenza) e le limitazioni da riportare all'agente.

    Passi: (1) validazione; (2) anomalie CPU/load; (3) pattern strutturali; (4) evidenze multi-risorsa;
    (5) selezione a rotazione entro il budget; (6) conteggi e omissioni; (7) report finale.
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

    # Il report A1-v1 è annidato dentro l'A1-v2: ne controlliamo la versione prima di leggerne i campi.
    report_v1 = report_v2["evidenze_v1"]

    if report_v1.get("versione") != "A1-v1":
        raise ValueError(
            "Report A1-v1 non valido."
        )

    # =====================================================
    # 2. EVIDENZE CPU/LOAD ORIGINALI
    # =====================================================

    # Ogni anomalia A1-v1 diventa un'evidenza di categoria "cpu_load"; `provenienza` registra da quale
    # posizione del report originale proviene.
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

    # Stessa trasformazione per i pattern strutturali (anomalie vicine nel tempo sullo stesso componente).
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

    # Le unità già selezionate dal riepilogo multi-risorsa diventano evidenze di categoria "multi_risorsa".
    # `gruppi_origine` permette di risalire ai gruppi del report A1-v2 da cui derivano.
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

    # `posizioni[i]` = prossima evidenza ancora da prendere dalla coda i.
    posizioni = [0, 0, 0]

    evidenze_finali = []

    # A ogni giro si prende al più un'evidenza da ciascuna coda, finché c'è budget.
    while len(evidenze_finali) < max_evidenze_totali:

        aggiunte_nel_giro = 0

        for i, coda in enumerate(code):

            if len(evidenze_finali) >= max_evidenze_totali:
                break

            # Coda esaurita: si passa alla successiva.
            if posizioni[i] >= len(coda):
                continue

            evidenze_finali.append(
                coda[posizioni[i]]
            )

            posizioni[i] += 1
            aggiunte_nel_giro += 1

        # Un giro senza aggiunte significa che tutte le code sono finite: ci si ferma anche se resta budget.
        if aggiunte_nel_giro == 0:
            break

    # =====================================================
    # 6. CONTEGGI E OMISSIONI
    # =====================================================

    # Quante evidenze esistono per categoria, quante ne sono entrate e quante sono rimaste fuori per budget.
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


def costruisci_report_unificato_v2(
    report_v2: dict,
    sintesi: dict,
    aggregazione_mesh: dict,
    report_mesh_runtime: dict,
    max_evidenze_totali: int = 10
) -> dict:
    """
    Report unificato A1 con Node, Container, Mesh e Runtime.

    Obiettivi:
    - Conservare le evidenze CPU/load e i pattern A1-v1.
    - Includere la sintesi Node/Container.
    - Includere le unità Mesh aggregate.
    - Includere eventuali evidenze Runtime.
    - Preservare la corroborazione host/container.
    - Rispettare un budget globale.

    La selezione è euristica, non causale.
    Non usa ground truth e non chiama Gemini.

    Argomenti:
      report_v2            report A1-v2 ("A1-v2") con il report A1-v1 annidato.
      sintesi              riepilogo multi-risorsa ("evidence_summary_v1").
      aggregazione_mesh    unità Mesh aggregate ("mesh_aggregation_v1").
      report_mesh_runtime  evidenze Mesh/Runtime ("mesh_runtime_evidence_v1"), NON ancora troncate.
      max_evidenze_totali  budget globale: numero massimo di evidenze nel report finale (>= 1).

    Restituisce un report "unified_evidence_v2" con le evidenze scelte, i conteggi per categoria
    (pattern, cpu_load, multi_risorsa, mesh, runtime), le omissioni precedenti e le limitazioni.

    Passi: (1) validazione; (2) recupero di tutte le evidenze originali; (3) unità Mesh; (4) evidenze
    Runtime; (5) controllo che siano nella finestra del caso; (6) selezione investigativa in quattro
    fasi (6A–6D); (7) conteggi; (8) report finale.
    """

    from collections import Counter

    # =====================================================
    # 1. VALIDAZIONE
    # =====================================================

    if max_evidenze_totali < 1:
        raise ValueError("Budget globale non valido.")

    if report_v2.get("versione") != "A1-v2":
        raise ValueError("Report A1-v2 non valido.")

    if sintesi.get("versione") != "evidence_summary_v1":
        raise ValueError("Sintesi non valida.")

    if aggregazione_mesh.get("versione") != "mesh_aggregation_v1":
        raise ValueError("Aggregazione Mesh non valida.")

    if (
        report_mesh_runtime.get("versione")
        != "mesh_runtime_evidence_v1"
    ):
        raise ValueError("Report Mesh/Runtime non valido.")

    # Non accettiamo un report diagnostico
    # già troncato: altrimenti perderemmo
    # evidenze prima della selezione globale.
    conteggi_mr = report_mesh_runtime["conteggi"]

    # Per ciascuna sorgente le evidenze rilevate devono coincidere con quelle selezionate.
    for sorgente in ("mesh", "runtime"):
        if (
            conteggi_mr[f"{sorgente}_rilevate"]
            != conteggi_mr[f"{sorgente}_selezionate"]
        ):
            raise ValueError(
                f"Report {sorgente} già troncato."
            )

    # =====================================================
    # 2. RECUPERO DI TUTTE LE EVIDENZE ORIGINALI
    # =====================================================

    report_v1 = report_v2["evidenze_v1"]

    caso = report_v1["caso"]

    # Finestra del caso: tutte le evidenze devono cadere in [start, end).
    start = int(caso["start_unix"])
    end = int(caso["end_unix"])

    # Il report Mesh/Runtime deve riferirsi alla stessa finestra del caso.
    finestra_mr = report_mesh_runtime["finestra"]

    if (
        int(finestra_mr["start_unix"]) != start
        or int(finestra_mr["end_unix"]) != end
    ):
        raise ValueError(
            "Finestre temporali non coincidenti."
        )

    # Riutilizziamo la trasformazione A1-v1
    # già verificata, senza perdere evidenze
    # a causa del precedente limite globale.
    # Come budget si usa il numero totale di evidenze originali: così `base` le contiene tutte
    # (anomalie CPU/load, pattern, multi-risorsa) e la scelta vera avviene più sotto, nella sezione 6.
    numero_originali = (
        len(report_v1["anomalie"]["segnalazioni"])
        + len(report_v1["patterns"]["segnalazioni"])
        + len(sintesi["evidenze"])
    )

    base = costruisci_report_unificato(
        report_v2=report_v2,
        sintesi=sintesi,
        max_evidenze_totali=max(1, numero_originali)
    )

    # `candidati` è l'insieme di tutte le evidenze tra cui scegliere; a quelle di `base` si aggiungono sotto
    # le unità Mesh e le evidenze Runtime.
    candidati = list(base["evidenze"])

    # =====================================================
    # 3. AGGIUNTA DELLE UNITÀ MESH
    # =====================================================

    # Ogni unità Mesh aggregata (più repliche dello stesso servizio) diventa un'evidenza di categoria "mesh".
    for indice, unita in enumerate(
        aggregazione_mesh["unita"]
    ):

        candidati.append({
            "fonte": "Mesh",
            "categoria": "mesh",
            "tipo": unita["tipo"],
            "famiglia": unita["famiglia"],
            "servizio": unita["servizio"],
            "comunicazione": unita["comunicazione"],
            "kpi": unita["kpi"],
            "componenti": list(unita["componenti"]),
            "numero_repliche": unita["numero_repliche"],
            "timestamp_inizio": unita[
                "timestamp_inizio"
            ],
            "timestamp_fine": unita[
                "timestamp_fine"
            ],
            "incremento_massimo_assoluto": unita[
                "incremento_massimo_assoluto"
            ],
            "provenienza": {
                "sezione": "aggregazione_mesh.unita",
                "indice": indice,
                "indici_origine": list(
                    unita["indici_origine"]
                )
            },
            "causa_verificata": False
        })

    # =====================================================
    # 4. AGGIUNTA DELLE EVIDENZE RUNTIME
    # =====================================================

    for indice, evidenza in enumerate(
        report_mesh_runtime["evidenze"]
    ):

        # Qui si prendono solo le evidenze Runtime: quelle Mesh entrano già come unità aggregate (sezione 3).
        if evidenza["sorgente"] != "runtime":
            continue

        episodio = evidenza["evidenza"]

        candidati.append({
            "fonte": "Runtime",
            "categoria": "runtime",
            "tipo": evidenza["tipo"],
            "famiglia": evidenza["famiglia"],
            "componente": evidenza["componente"],
            "kpi": evidenza["kpi"],
            "trasformazione": evidenza[
                "trasformazione"
            ],
            "timestamp_inizio": episodio[
                "timestamp_inizio"
            ],
            "timestamp_fine": episodio[
                "timestamp_fine"
            ],
            "mediana_riferimento": episodio[
                "mediana_riferimento"
            ],
            "valore_massimo": episodio[
                "valore_massimo"
            ],
            "aumento_pct": episodio["aumento_pct"],
            "provenienza": {
                "sezione": "report_mesh_runtime.evidenze",
                "indice": indice
            },
            "causa_verificata": False
        })

    # =====================================================
    # 5. CONTROLLO TEMPORALE
    # =====================================================

    # Ogni candidato deve iniziare dentro la finestra del caso; altrimenti i dati sono incoerenti
    # e il report non viene costruito.
    for evidenza in candidati:

        timestamp = int(evidenza["timestamp_inizio"])

        if not start <= timestamp < end:
            raise ValueError(
                "Evidenza fuori dalla finestra del caso."
            )

    # =====================================================
    # 6. SELEZIONE INVESTIGATIVA
    # =====================================================

    # `identita_selezionate` contiene gli `id()` degli oggetti già scelti: si confronta l'identità, non il
    # contenuto, perché due evidenze diverse potrebbero avere gli stessi valori.
    selezionate = []
    identita_selezionate = set()

    def aggiungi(evidenza):
        """
        Aggiunge un'evidenza una sola volta
        rispettando il budget globale.

        Restituisce True se l'evidenza è stata aggiunta, False se il budget è esaurito o è già presente.
        """

        if len(selezionate) >= max_evidenze_totali:
            return False

        identita = id(evidenza)

        if identita in identita_selezionate:
            return False

        selezionate.append(evidenza)
        identita_selezionate.add(identita)

        return True

    # -----------------------------------------------------
    # 6A. CORRELAZIONI NODE/CONTAINER
    # -----------------------------------------------------

    # Candidate: le unità multi-risorsa in cui più repliche mostrano l'anomalia quasi insieme.
    correlazioni_container = [
        e for e in candidati
        if (
            e["categoria"] == "multi_risorsa"
            and e["tipo"] == "anomalia_multi_replica"
        )
    ]

    # Ordine deterministico: prima le più precoci, a parità il nome dei componenti.
    correlazioni_container.sort(
        key=lambda e: (
            e["timestamp_inizio"],
            str(e["componenti"])
        )
    )

    # Prima preserviamo fino a due correlazioni
    # multi-replica e le eventuali evidenze host
    # della stessa famiglia entro 60 secondi.
    for correlazione in correlazioni_container[:2]:

        aggiungi(correlazione)

        componenti = correlazione["componenti"]

        # Nodi che ospitano i container della correlazione: la parte prima del punto in "node-6.servizio-2".
        nodi_ospitanti = {
            componente.split(".")[0]
            for componente in componenti
            if "." in componente
        }

        # Corroborazione: evidenze multi-risorsa non multi-replica (cioè sul nodo), della stessa famiglia
        # di metriche, che coinvolgono uno dei nodi ospitanti e iniziano entro 60 secondi.
        corroborazioni = [
            e for e in candidati
            if (
                e["categoria"] == "multi_risorsa"
                and e["tipo"] != "anomalia_multi_replica"
                and e["famiglia"]
                    == correlazione["famiglia"]
                and any(
                    nodo in e["componenti"]
                    for nodo in nodi_ospitanti
                )
                and abs(
                    e["timestamp_inizio"]
                    - correlazione["timestamp_inizio"]
                ) <= 60
            )
        ]

        # Si tiene la corroborazione più vicina nel tempo (a parità: componenti e KPI in ordine alfabetico).
        corroborazioni.sort(
            key=lambda e: (
                abs(
                    e["timestamp_inizio"]
                    - correlazione["timestamp_inizio"]
                ),
                str(e["componenti"]),
                str(e["kpi"])
            )
        )

        if corroborazioni:
            aggiungi(corroborazioni[0])

    # -----------------------------------------------------
    # 6B. CORRELAZIONI MESH
    # -----------------------------------------------------

    # Privilegiamo fino a tre gruppi multi-replica.
    # Il numero è un limite euristico iniziale.
    correlazioni_mesh = [
        e for e in candidati
        if (
            e["categoria"] == "mesh"
            and e["tipo"] == "mesh_multi_replica"
        )
    ]

    # Ordine: più repliche coinvolte, poi incremento massimo più alto (il segno meno inverte l'ordine
    # crescente), poi più precoce, poi nome del servizio.
    correlazioni_mesh.sort(
        key=lambda e: (
            -e["numero_repliche"],
            -e["incremento_massimo_assoluto"],
            e["timestamp_inizio"],
            str(e["servizio"])
        )
    )

    for evidenza in correlazioni_mesh[:3]:
        aggiungi(evidenza)

    # -----------------------------------------------------
    # 6C. PATTERN E CPU/LOAD
    # -----------------------------------------------------

    # Garantiamo rappresentanza alle evidenze
    # infrastrutturali originali, se presenti.
    # Per ciascuna categoria si sceglie l'evidenza più precoce (a parità: componente e KPI).
    for categoria in ("pattern", "cpu_load"):

        categoria_candidati = [
            e for e in candidati
            if e["categoria"] == categoria
        ]

        categoria_candidati.sort(
            key=lambda e: (
                e["timestamp_inizio"],
                str(e.get("componente", "")),
                str(e.get("kpi", ""))
            )
        )

        if categoria_candidati:
            aggiungi(categoria_candidati[0])

    # -----------------------------------------------------
    # 6D. RAPPRESENTANZA DELLE ALTRE FAMIGLIE
    # -----------------------------------------------------

    def chiave_famiglia(evidenza):
        """Chiave (categoria, famiglia) di un'evidenza; se la famiglia manca si usa il tipo."""
        return (
            evidenza["categoria"],
            evidenza.get(
                "famiglia",
                evidenza["tipo"]
            )
        )

    # Combinazioni (categoria, famiglia) già presenti tra le evidenze scelte nelle fasi 6A–6C.
    famiglie_rappresentate = {
        chiave_famiglia(e)
        for e in selezionate
    }

    # Se esiste un'anomalia Runtime, proviamo
    # a conservarne almeno una entro il budget.
    # Priorità tra categorie (numero più basso = prima); una categoria sconosciuta va in fondo (99).
    priorita_categorie = {
        "runtime": 0,
        "multi_risorsa": 1,
        "cpu_load": 2,
        "mesh": 3,
        "pattern": 4
    }

    # Tutti i candidati in ordine deterministico: priorità della categoria, istante d'inizio, componente, tipo.
    rimanenti = sorted(
        candidati,
        key=lambda e: (
            priorita_categorie.get(
                e["categoria"], 99
            ),
            e["timestamp_inizio"],
            str(
                e.get(
                    "componente",
                    e.get("componenti", "")
                )
            ),
            str(e["tipo"])
        )
    )

    # Prima introduciamo famiglie non ancora
    # rappresentate.
    for evidenza in rimanenti:

        famiglia = chiave_famiglia(evidenza)

        if famiglia in famiglie_rappresentate:
            continue

        if aggiungi(evidenza):
            famiglie_rappresentate.add(famiglia)

    # Infine utilizziamo gli eventuali slot liberi.
    for evidenza in rimanenti:
        aggiungi(evidenza)

    # =====================================================
    # 7. CONTEGGI E OMISSIONI
    # =====================================================

    # Conteggi per categoria: candidate, scelte e rimaste fuori per il budget globale.
    disponibili = Counter(
        e["categoria"]
        for e in candidati
    )

    inclusi = Counter(
        e["categoria"]
        for e in selezionate
    )

    categorie = (
        "pattern",
        "cpu_load",
        "multi_risorsa",
        "mesh",
        "runtime"
    )

    conteggi = {
        "disponibili": {
            c: disponibili[c] for c in categorie
        },
        "inclusi": {
            c: inclusi[c] for c in categorie
        },
        "omessi_per_budget": {
            c: disponibili[c] - inclusi[c]
            for c in categorie
        }
    }

    # =====================================================
    # 8. REPORT FINALE
    # =====================================================

    return {
        "versione": "unified_evidence_v2",

        "caso": dict(caso),

        "copertura": {
            "infrastruttura": dict(
                report_v1["copertura"]
            ),
            "mesh_runtime": dict(
                report_mesh_runtime["copertura"]
            )
        },

        "qualita_infrastruttura": dict(
            report_v1["qualita"]
        ),

        "budget_evidenze": max_evidenze_totali,

        "evidenze_totali": len(selezionate),

        "evidenze": selezionate,

        "conteggi": conteggi,

        "omissioni_precedenti": {
            "anomalie_v1": report_v1[
                "anomalie"
            ]["segnalazioni_omesse"],
            "patterns_v1": report_v1[
                "patterns"
            ]["segnalazioni_omesse"],
            "unita_multi_risorsa": sintesi[
                "unita_non_selezionate"
            ],
            "baseline_zero_mesh": (
                report_mesh_runtime["copertura"]
                ["baseline_zero_mesh_escluse"]
            )
        },

        "limitazioni": [
            "Le evidenze non identificano la root cause.",
            "Le priorita investigative sono euristiche.",
            "La correlazione temporale non prova causalita.",
            "Le durate Mesh hanno semantica preliminare.",
            "I contatori GC hanno semantica preliminare.",
            "La selezione globale puo omettere evidenze.",
            "Le anomalie al bordo possono essere incomplete.",
            "L'assenza di anomalie non dimostra assenza di guasti."
        ]
    }