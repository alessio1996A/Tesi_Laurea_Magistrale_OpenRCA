# RQ2-V2 — 844/844 test PASS; gate tecnico offline chiuso, decisione scientifica da preregistrare

**Data:** 13 novembre 2026
**Branch:** `experiment/rq2-provenance-v2-offline-2026-11-13`
**Base V1 congelata:** `c0eee134a1219bb1704efb73621cafe3d4f70a1a`
**Stato:** `OFFLINE_TECHNICAL_GATE_PASSED` / `NO_LIVE_API_AUTHORITY` / `OOD_TEST_LOCKED`
**Fonte del PASS:** output PowerShell/PyCharm comunicato dall'utente, non un run eseguito da GitHub CI.

## Esito confermato

```text
Ran 844 tests in 80.612s

OK
```

La suite globale precedente era **841/841**.
Dopo l'aggiunta dei **3** test
`test_rq2_v2_runner_to_ledger_fake_e2e.py`
(e la correzione dell'import della classe di fixture),
il nuovo totale osservato è **844/844**.
Il primo gate mirato aveva riportato `Ran 19 tests`
perché importava direttamente una classe TestCase contenente
16 test già presenti. L'import è stato corretto ed il gate
è stato rieseguito: `Ran 3 tests in 4.434s / OK`.
Non confondere il conteggio temporaneo 19 con 19 nuovi test.

I test coprono la catena sintetica:
`run_experiment` (V1 invariato, `salva=False`)
→ LangGraph/ToolNode reale con LLM e tool FAKE
→ esecutore RQ2-V2 che preserva `tool_call_id`
→ evidence bundle fail-closed
→ preparazione C/K offline con risposte fixture
→ nuovo claim journal e artifact store V2
in TemporaryDirectory, per A1 e A1_8R.

Casi negativi testati: `tool_result` con ID incongruente,
riferimento C a `E999` inesistente, stage blocked e assenza
di claim per stage bloccati, no retry, restart e digest
parent. Lo store/journal V2 richiede un marker sintetico
e vieta i path reali del benchmark.

## Verifica integrità del repository

Confronto del branch sperimentale contro
`c0eee134a1219bb1704efb73621cafe3d4f70a1a`
effettuato dopo la prova: **28 file aggiunti, zero file
preesistenti modificati**. La V1 non viene alterata
dal branch e il bundle originario rimane fail-closed.

Questa verifica Git non certifica i file fuori repository
eventualmente presenti in Colab/Drive: non attribuire al
confronto Git un audit remoto dei record V1 su Drive.

## Cosa dimostrano i 844 PASS

**Dimostrano**: compatibilità software nei casi
automatizzati; serializzazione della tool provenance;
comportamento coerente nei percorsi sintetici
D→C→K e registrazione create-only; rispetto del
confine di isolamento fra moduli V1 e V2.

**NON dimostrano**:
- maggiore accuratezza diagnostica su OpenRCA reale;
- qualità causale di una regola K prodotta da un modello;
- generalizzazione a classi di guasto escluse;
- supporto di un provider remoto alle chiamate e
  conseguente token usage/costo reale;
- reale source pin, autorizzazione, ripartenza e budget
  di una campagna V2 scientifica;
- indipendenza statistica dei quattro discovery già
  visti nella campagna RQ2-V1.

Gli 11 casi OOD test restano **LOCKED**.

## Decisione GO/NO-GO, separando le domande

| Attività | Stato | Motivazione |
|---|---|---|
| Gate integrato offline V2 | CHIUSO / PASS | 844/844 test |
| Esecutore provenance V2 nel ramo sperimentale | VERIFICATO OFFLINE | Matching tool call/result nelle fixture |
| Store/journal V2 per dati sintetici | VERIFICATO OFFLINE | Audit, create-only, blocco duplicati |
| Store scientifico GT-free V2 su dati reali | NON PRONTO | Manca release/source-pin e autorizzazione |
| Pilot provider API V2 | NO-GO ORA | Mancano protocollo freeze, budget, gate reale e autorizzazione |
| Test OOD/GT | LOCKED | Non usarli per sviluppo o tuning |
| Claim che knowledge transfer generalizza | NON SUPPORTATO | Nessuna valutazione indipendente OOD |

## Proposta scientifica minima, NON ancora preregistrata

**RQ2 tecnica (verificabile):**
«La preservazione degli ID di invocazione dei tool permette
di ricostruire in modo univoco l'evidenza di esecuzioni
con tool call omonime parallele, senza rilassare il validatore
e senza alterare output/prompt/budget dell'esecutore V1».
L'evidenza attuale è **sintetica**, non una replica di provider.
Questo va presentato come contributo di engineering,
non come miglioramento provato dell'accuratezza RCA.

**RQ2 scientifica (ancora aperta):**
«Regole candidate ottenute in discovery possono essere
riusate per diagnosi su guasti/classi non visti?».
Servono una procedura di generazione, congelamento,
selezione ex ante, applicazione senza labels, e confronto
appaiato su holdout mai usato per sviluppo; non basta
archiviare `RECORDED_COMPLETE` o ottenere JSON validi.

Prossima sequenza raccomandata:
1. **Fermare espansione di test generici**: il gate tecnico
   offline è sufficiente per la copertura attualmente
   progettata; conservare le 844 prove come baseline.
2. **Preparare una scheda RQ2 per il relatore** che
   distingua: RQ1 già valutata ufficialmente,
   V1 discovery osservata (39/72), problema di provenance,
   correzione V2 offline, valore aggiunto ed evidenze
   mancanti per la generalizzazione.
3. **Scegliere una sola ipotesi di pilot**:
   su caso discovery già visto, al più dimostrazione
   mirata della robustezza tecnica con esecutore V2.
   Non chiamarla replica indipendente; nessun replay
   di claim V1 e nessuna correzione retroattiva
   del relativo record.
4. **Preregistrare un eventuale pilot V2** con nuovo
   archivio scientifico effettivamente separato:
   release ID/SHA, sorgenti GT-free/source pin,
   esatto caso/harness/modello, versione provider,
   prompt/contract, numeri di tentativi, handling
   error/invalid/blocked, KPI provenance, token,
   costo, stop, no-retry, denominatore e
   autorizzazione finanziaria separata.
5. **Solo dopo approvazione esplicita** valutare
   l'esecuzione di un singolo pilot su provider.
   Prima di accedere all'OOD test serve un freeze
   metodologico distinto che impedisca leak/tuning.
6. **Preservare tempo per la tesi**: scadenza
   1 dicembre 2026; iniziare ora stesura RQ1,
   metodo, limiti e RQ2 esplorativa. Refactoring
   e commenti italiani dopo il freeze dei risultati.

**Trade-off ineliminabile**: se non resta tempo
o non esiste una coorte OOD scientificamente
testabile con un freeze credibile, non inventare
conclusioni di knowledge transfer. La tesi può
descrivere la pipeline e gli esiti RQ2 come
studio esplorativo/di fattibilità, non come
generalizzazione sperimentalmente dimostrata.

## Nessuna attività automatica successiva

Questo documento non costituisce autorizzazione
a effettuare API né a leggere ground truth o
sbloccare gli 11 casi test. Non cambiare il
protocollo sperimentale V1, i 39 record o lo
score ufficiale RQ1. Non implementare
human-in-the-loop (decisione relatore).
