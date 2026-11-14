# RQ2 — q045: audit reale dei log su development, 14 novembre 2026

**Origine della prova:** output reale Google Colab fornito dall'utente il 14 novembre 2026, dopo gate PyCharm `Ran 20 tests in 2.011s; OK` sul test `test_rq2_q045_development_log_audit.py`. Gate sintetico precedente `Ran 31 tests in 0.018s; OK`. Non confondere 51 test unitari con incidenti diagnosticati.

## Sorgente congelata dell'audit
- Git branch `fix/rq2-q045-development-log-symlink-test-windows-2026-11-14`, HEAD `c2bed47a9f61ac6ac67223c47a9b55e680d6f0ee` riportato dalla cella, checkout nuovo e dipendenze pinned; snapshot Python scientifico verificato.
- Modulo `src/evaluation/rq2_q045_development_log_audit.py`: audit GT-free solo finestre development ricavate dai CSV split e manifest con SHA previsti; ZIP log di servizio letto in sola lettura, filtro sulle finestre development prima del parsing dei messaggi; nessun OOD test o codice K eseguito.
- Candidate K Gemini V1 q045/A1, SHA record `32ddf6815e4216f0a46070950252852cec984f4456a0bb3758c86b16d1296add`, `productcatalogservice_dns_timeout_detector`, KPI derivato proposto `service_log_warnings` con `sum >0` su 60s; stato NON congelato.

## Output reale
```text
STATUS: Q045_DEVELOPMENT_LOG_AUDIT_OK
GIT_HEAD: c2bed47a9f61ac6ac67223c47a9b55e680d6f0ee
DEVELOPMENT_CASES: 92
LOG_FILES_READ: 4
SCOPED_LOG_ROWS: 116
EXPLICIT_WARNING_ROWS: 100
60S_BUCKETS_WITH_WARNINGS: 7
EMPTY_MESSAGE_ROWS: 0
MISSING_LOG_ID_ROWS: 0
CLOUDBED: cloudbed-1
LOG_ROWS: 0
WARNINGS: 0
CLOUDBED: cloudbed-2
LOG_ROWS: 116
WARNINGS: 100
SOURCE_VERIFIED: True
LOG_COMPLETENESS_VERIFIED: FALSE
DNS_CAUSALITY_VERIFIED: FALSE
SCIENTIFIC_FREEZE: FALSE
RULE_EXECUTED: FALSE
API_CALLS: 0
DRIVE_WRITES: 0
GROUND_TRUTH_READ: FALSE
OOD_TEST: LOCKED
```

## Interpretazione corretta
1. Il segnale testuale `severity: warning` e' effettivamente osservabile in un insieme indipendente di finestre **development**, oltre che nell'incidente *discovery* q045. Cio' dimostra disponibilita' del segnale su dati reali ma non ne certifica semantica, completezza, causalita', specificita' DNS o generalizzazione della regola.
2. 100 e' il **conteggio di righe warning**, NON 100 incidenti/fault, e 7 e' il numero di **bucket (cloudbed, minuto)** con uno o piu' warning, NON di incidenti indipendenti. Il codice non esegue de-duplicazione log_id: non interpretare questi numeri come eventi unici verificati. Non e' nota la completezza del log stream.
3. Il report include development 92 casi previsti, ma non significa che tutte le finestre/casi abbiano log del servizio, ne' che cloudbed-1 sia sano. Lo zero in cloudbed-1 indica zero righe del servizio con quel filtro nelle finestre development analizzate, non assenza di guasti.
4. L'estrattore literal regex `severity: warning`, il pooling delle istanze `productcatalogservice-*` e la scelta di bucket UTC nonoverlapping sono decisioni di operationalizzazione **post-hoc**, non un'invariante del modello K. Esistono warning generici non-DNS; non inferire la classe di guasto dalle stringhe o da GT.
5. `false_positive_rate` e `sensitivity` non sono state misurate. Le 11 query OOD test restano chiuse; nessun freeze/autorizzazione di scoring. Non adattare la soglia >0 o regex a risultati OOD.

## Prossima decisione, senza nuovi esperimenti costosi
- Rileggere solo `validated_k.abstain_when`, `counterexamples`, `limitations` della K q045 originaria, e confrontarli con il prototipo sintetico. Questo e' read-only, GT-free e zero provider API.
- Il prototipo attuale fa `abstain` se un flag di completezza sintetico e' false, ma non esiste una prova di completezza dei log reali: NON e' consentito convertirlo in `negative` nel reale solo per assenza di warning.
- Se manca una policy verificabile di completezza/specificita' o la regola K e' intrinsecamente ambigua, registrare l'esito **candidato non validato** e chiudere RQ2-C come esplorativo/non dimostrato; non affrettare uno scoring sui test per consegna.
- Scadenza tesi 1 dicembre 2026: completare eventuale ultima verifica strettamente necessaria, poi refactoring con commenti in italiano e scrittura.
