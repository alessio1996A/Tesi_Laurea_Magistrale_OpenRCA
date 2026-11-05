# Claude development V2: recupero dopo pilot interrotto (2026-11-05)

## Natura del problema e perche' non e' un fallimento RCA

La campagna Claude V1 e' stata congelata al commit
63a046723165976558840a30efb1b5097ad3fdf7, con piano su Drive:
- protocol: openrca_claude_five_agents_development_v1
- plan SHA-256: fb828dfcd7f2ac9e07b6d916ffd51e61b6a23052c1edbf7a06e965acb5a26158
- prima run: openrca_claude_five_agents_development_v1__sonnet__cloudbed-1_q005__a0__r01

La prima run ha ricevuto un KeyboardInterrupt durante l'elaborazione
di ToolNode di LangGraph. L'audit (solo lettura) del 5 novembre:
- stato: CLAIM_PENDING_NO_AUTO_RETRY;
- claim presente: 442 byte, modificato alle 17:05:12 locali;
- JSON risultato e sidecar SHA-256: assenti;
- altre Sonnet: 39 ready; tutte le Haiku: 40 ready.

Il traceback mostra molte emissioni Pandas da src/agent/tools.py,
riga 293 nel commit V1, causate dal pattern KPI con gruppi regex.
Il numero di warning NON e' il numero di richieste Anthropic ne'
prova un errore della chiamata LLM. L'elaborazione del CSV giornaliero
delle metriche container puo' durare vari secondi.

Audit performance offline:
- Market.zip 2.865 GB; apertura ZIP 0.042 s;
- file metric_container.csv richiesto: 1, 278 MB decompresso;
- lettura primi 256 KiB: 0.002 s;
- singola chiamata al tool container, KPI (cpu|memory):
  10.132 secondi, 2,525 caratteri, 38 warning, nessun errore.
Non e' dimostrato che i warning siano la causa del KeyboardInterrupt;
il benchmark non riproduce tutta la traiettoria e il parallelismo.

Il tentativo V1 puo' aver effettuato chiamate API e prodotto costo,
anche senza token contabilizzati; NON riutilizzarne il run_id.

## Correzione delimitata

Nuovo branch: feature/claude-clean-recovery-v2-2026-11-05,
derivato esattamente dal commit V1 congelato.

Modifica src/agent/tools.py:
- helper _kpi_regex_contains(): stesso Series.astype(str).str.contains,
  stesso pattern compilato, na=False, nessuna conversione arbitraria
  dei gruppi di cattura;
- warnings.catch_warnings filtra SOLO lo specifico UserWarning Pandas
  che segnala la presenza di gruppi regex;
- usato per le metriche container e node dove compare il medesimo
  controllo; nessuna modifica ai cinque schemi dei tool, al contratto
  output, alle regole, al prompt o alla finestra temporale.

Il warning suppression non e' un'ottimizzazione prestazionale;
i tempi per processare l'input rimangono da misurare.
Il test test_pandas_kpi_warning_suppression.py verifica che gli output
siano identici con gruppi, backreference e pattern senza gruppi.

Verificare inoltre l'identita' SHA-256 di output completi della
vecchia e della nuova implementazione su identici input, senza API.
Se differenti: STOP e indagare prima di creare un piano V2.

## Protocollo nuovo, senza sovrascritture

Il modulo claude_development_campaign.py ora dichiara
openrca_claude_five_agents_development_v2 (non V1).
Build del piano da piano V3 originale GT-free, 8 casi development,
5 varianti canonical, 2 modelli, totale 80 run:
40 Sonnet + 40 Haiku. Planning e PAVE 4+2 storico. Ogni
run_id contiene "development_v2" e non collide con V1.

Il piano create-only e' distinto:
data/protocols/v2/openrca_claude_five_agents_development_v2_plan_v1.json
Output create-only:
data/results/v2/openrca_claude_five_agents_development_v2/.

Il nuovo piano include "recovery_provenance" con nome e SHA del
vecchio piano, primo run_id interrotto, causa e politica di zero
riutilizzo di risultati. La V1 non viene modificata, copiata come
risultati completati ne' integrata con le nuove predizioni.

Usare una NUOVA directory di checkout Colab:
  /content/Tesi_OpenRCA_Claude_V2

Non aggiornare tramite git pull la directory congelata V1
/content/Tesi_OpenRCA_Claude.
Non cancellare claim, output o piano V1.

## Validazione e avvio controllato

1. Aprire il notebook Fase2_Claude_Recovery_V2_OFFLINE.ipynb
   sul nuovo branch; montare Drive e clonare repo V2 separatamente.
2. Eseguire intera suite di test in offline.
3. Confrontare SHA dell'output completo del container tool,
   V1 contro V2, con medesimo (cpu|memory), stessa finestra, max_rows;
   registrare i tempi. Nessuna API.
4. Verificare V1 claim e SHA piano, preservando dati.
5. Solo quando test e output coincidono, creare il nuovo piano
   V2 in modalita' create-only.
6. Leggere Secret ANTHROPIC_API_KEY da Colab Secrets; mai stamparlo.
7. Eseguire una sola nuova run A0 Sonnet con il nuovo run_id V2
   e nuova autorizzazione esplicita; zero retry automatici, claim prima
   dell'API, JSON e SHA create-only, controllo di integrita'.
8. Se valida: campagne graduate, stato/preflight prima di ogni batch.
   Se fallisce: STOP e conservare i dati per audit.

L'esperimento Claude V1 interrotto resta evidenza di un problema
operativo, non una diagnosi errata: NON si usa come valore zero di
accuratezza A0. Lo scorer ufficiale su query.csv deve essere eseguito
SOLO DOPO freeze completo delle nuove predizioni V2, con risultati
archiviati separatamente da V3 e da V1.

Non e' stato autorizzato alcun retry automatico di V1 o trasferimento
di risultati fra protocolli. Il budget di riferimento non e' hard cap.
