# Handoff di continuità — OpenRCA RQ2-V2, 13 novembre 2026

**Scopo:** riprendere la tesi in una nuova chat senza perdere
commit, esiti, errori o vincoli sperimentali.

**Repository:** `alessio1996A/Tesi_Laurea_Magistrale_OpenRCA`
**Branch:** `experiment/rq2-provenance-v2-offline-2026-11-13`
**Base congelata V1:** `c0eee134a1219bb1704efb73621cafe3d4f70a1a`
**Consegna tesi:** 1 dicembre 2026.
**Metodo:** lavoro su branch separato tramite connettore GitHub,
utente testa in PyCharm/PowerShell e poi (solo con autorizzazione)
in Colab. Nessuna API di provider senza approvazione preventiva.
Dopo il freeze: refactoring del codice, commenti in italiano e
pulizia file superflui, senza alterare sorgenti/risultati congelati.

## Tesi, benchmark e risultati congelati

Università di Catania, LM Ingegneria Informatica.
Harness Engineering per LLM su RCA con Microsoft OpenRCA.

RQ1 Evaluation20: 20 incidenti × 5 harness × 3 LLM =
300 tentativi, 295 complete e 5 errori provider Gemini.
Scoring Microsoft ufficiale e confronti statistici già
congelati; non cambiare il protocollo RQ1.

RQ2: knowledge transfer, stadi D→C→K, due harness A1/A1_8R,
modelli Gemini/Sonnet/Haiku. Quattro casi discovery già visti:
`cloudbed-1_q032`, `cloudbed-1_q050`,
`cloudbed-2_q026`, `cloudbed-2_q045`.
Undici casi OOD test LOCKED. V1 rimane a 39/72 stage:
28 RECORDED_COMPLETE, 4 INVALID_OUTPUT,
7 BLOCKED_DEPENDENCY; 32 tentativi API reali.
24 record Gemini, 15 Sonnet, 0 Haiku.
Tre D Sonnet invalid per ambiguità fra tool call parallele
omonime, perché il grafo V1 non serializza gli originali
`tool_call_id` nei risultati. Il bundle RQ2 fail-closed
è corretto: **non allentarlo**, non riparare V1 retroattivamente,
non fare retry sui claim V1.

## Codice V2 sul branch

Nuovi file, senza cambiare sorgenti originali:
- `src/agent/rq2_v2_graph_engine.py`: replica minima
  esecutore V1 che aggiunge i `tool_call_id`
  originali alle tool call e tool result; nessun ID inventato.
- `src/evaluation/rq2_v2_isolation_policy.py`:
  validazione allowlist di stage discovery e namespace
  V2, esclusione test OOD.
- `src/evaluation/rq2_v2_artifact_store.py`:
  artifact store **solo sintetico**,
  JSON canonico, hash, create-only O_EXCL, status
  coerenti e parent hash.
- `src/evaluation/rq2_v2_claim_journal.py`:
  claim journal indipendente **solo sintetico**,
  no retry, restart audit e claim senza output preservati.
- `src/evaluation/rq2_evidence_bundle.py`,
  `src/evaluation/rq2_probe_adapter.py`,
  `src/evaluation/experiment_runner.py` rimangono invariati.

La nuova radice `data/rq2_v2_provenance` è disgiunta
da `data/rq2` V1. I moduli attuali richiedono un
marker sintetico e rifiutano Market.zip e directory
del benchmark reale. Sono ancora in stato
`DRAFT_NOT_EXECUTABLE`, NON una release di produzione.

## Test effettivamente eseguiti dall'utente in PyCharm

- 7/7 test tool provenance V2.
- 41/41 regressioni mirate.
- 812/812 suite globale.
- 2/2 runner-LangGraph fake end-to-end.
- 814/814 suite globale.
- 3/3 DCK fake con store V1 *solo in TemporaryDirectory*.
- 817/817 suite globale.
- 8/8 policy isolamento.
- 16/16 nuovo store/journal sintetico V2.
- **841/841 suite globale — 72.153 secondi — OK**.
- **3/3 runner-to-new-V2-ledger fake E2E — 4.434 secondi — OK**,
  dopo correzione dell'import.
- **844/844 suite globale — 80.612 secondi — OK**:
  include il gate completo runner→V2→D/C/K→nuovo ledger,
  più regressioni V1 e gate precedenti.

Sono test software, non 841 diagnosi sul benchmark.
GO solo offline, NO-GO API reali, NO-GO test OOD.
Report principale:
`docs/ood/RQ2_V2_GATE_841_PASS_GO_OFFLINE_NO_LIVE_2026-11-13.md`.
Confronto GitHub sulla base V1: 23 file aggiunti,
0 file preesistenti modificati, prima del gate successivo.

## Storico del gate runner→nuovo ledger (ora superato)

**Test eseguito e superato:**
`src/tests/test_rq2_v2_runner_to_ledger_fake_e2e.py`.

Unisce `run_experiment` V1, grafo LangGraph,
fake LLM/tool, esecutore V2 temporaneamente
patchato nel solo test, bundle tool_call_id,
preparazione offline pacchetti C/K e **nuovo**
journal/store V2 in `TemporaryDirectory`.

Identificativo consentito `cloudbed-1_q032` usato
SOLO come chiave fixture; dati, istruzione, C/K,
telemetria e tool sono inventati e nessun benchmark
reale viene aperto. Tre nuovi metodi:
1. triplet D/C/K per A1 e A1_8R; sei record/claim,
   provenienza delle due tool call omonime, parent SHA,
   restart e no retry;
2. ID tool result corrotto ⇒ D INVALID_OUTPUT,
   C/K BLOCKED_DEPENDENCY, nessun claim C/K;
3. C con ID E999 inesistente ⇒ INVALID_OUTPUT,
   K BLOCKED_DEPENDENCY.

**Nuovo esito locale osservato:** la prima esecuzione del gate
ha restituito `Ran 19 tests in 7.788s / OK`.
La differenza rispetto ai tre test progettati dipendeva
dall'import diretto della classe `RQ2OutputContractsTests`:
`unittest` ha raccolto anche i suoi 16 test originali,
oltre ai tre nuovi.
**Quindi i tre nuovi test hanno passato la prima esecuzione**,
ma i 19 non sono 19 nuovi test indipendenti.
Il solo import è stato corretto nel commit
`73eb3fb84652e11c708b00010d1ddcb5abc83fc0`
usando `import test_rq2_output_contracts as contract_fixtures`.
Report:
`docs/ood/RQ2_V2_RUNNER_TO_NEW_LEDGER_19_PASS_IMPORTED_TEST_FIX_2026-11-13.md`.

**Nuovo esito locale confermato dopo il fix:**
`Ran 3 tests in 4.434s / OK`. Il problema dei 16
test raccolti per errore è risolto. Il gate mirato
runner → esecutore V2 → D/C/K → nuovo ledger
sintetico è quindi **3/3 PASS**.
Report: `docs/ood/RQ2_V2_RUNNER_TO_NEW_LEDGER_3_PASS_AFTER_IMPORT_FIX_2026-11-13.md`.

**Stato aggiornato 13 novembre:** l'utente ha eseguito la
suite completa aggiornata:
```text
Ran 844 tests in 80.612s
OK
```
Quindi **844/844 PASS**, gate integrato offline chiuso
con esito positivo. Nuovo rapporto e decisione:
`docs/ood/RQ2_V2_844_844_GATE_TECNICO_CHIUSO_DECISIONE_SCIENTIFICA_2026-11-13.md`.
Non servono ulteriori test generici adesso: la priorità
è la decisione scientifica, la scheda per il relatore
e la preparazione di un eventuale pilot minimo V2,
ma senza autorizzazione a provider.

### Comandi PyCharm eseguiti storicamente (NON ripetere senza motivo)

Solo se branch giusto e working tree pulito:

```powershell
git branch --show-current
git status --short
git fetch origin
git pull --ff-only origin experiment/rq2-provenance-v2-offline-2026-11-13
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_runner_to_ledger_fake_e2e.py" -v
```

Attesi **3** test dopo la correzione dell'import
(il primo run precedente aveva 19 PASS includendo
16 test già esistenti, duplicati).
In caso di errori leggere il traceback e correggere
SOLO nuovi file V2.
Se OK, ripetere
`python -m unittest discover -s src/tests -p "test_*.py" -v`.
Previsti circa **844** test (841+3), da verificare.

## Integrità e decisione al gate 844

Confronto GitHub contro la base V1:
**28 file aggiunti, zero file preesistenti modificati**
prima del rapporto 844. I file di documentazione
aggiunti successivamente non modificano V1.
Gli 844 PASS sono test software, non scoring.
Il codice store/journal V2 attuale è solo
sintetico. Stato **GO_OFFLINE_TECHNICAL_PASSED**
ma **NO_GO_LIVE_API** e **NO_GO_OOD_TEST**.
Le quattro discovery V1 già osservate non forniscono
una replica indipendente di generalizzazione.

## Scheda per il relatore pronta — dopo 844 PASS

Il 13 novembre 2026 è stata preparata e pubblicata la
scheda scientifica:

`docs/ood/RQ2_SCHEDA_SCIENTIFICA_RELATORE_POST_844_PASS_2026-11-13.md`

La scheda **non** è un nuovo protocollo, una preregistrazione
firmata o una release e non modifica codice/dati.
Riporta RQ1 reale (300 tentativi, 295 complete);
RQ2 V1 discovery reale (39/72: 28 complete, 4 invalid,
7 blocked; 823.656 token osservati);
RQ2 V2 (844 test **software** passati, 0 run provider V2),
e le tre domande della scientific review preesistente:
RQ2-A fault-type OOD (correct/11, 10 gruppi test),
RQ2-B proposte K e formalizzabilità,
RQ2-C applicazione solo se regole deterministiche
verificate e congelate.

**Raccomandazione attuale:** discutere col relatore
se la tesi possa riportare RQ2 come studio
esplorativo/failure analysis, oppure richieda
un singolo pilot V2 tecnico strettamente preregistrato
(nuovo source-bound store/journal V2 reale ancora
da realizzare). Non avviare automaticamente 72
o 204 stage. Non accedere agli 11 OOD test prima
di freeze scientifico appropriato.

La scheda include un breve discorso orale e
tre decisioni concrete da ottenere dal relatore.
Priorità attuale: **consultazione metodologica e
stesura RQ1**, non nuovi test generici.
Ultima suite globale provata resta **844/844 OK**.

## Ripresa degli esperimenti reali: Gemini e Sonnet (13 novembre)

L'utente ha confermato la priorità personale:
**terminare la sperimentazione RQ2 reale → refactoring,
commenti in italiano e pulizia codice → scrittura tesi**.
È stata verificata la decisione **Gemini V1 NON va rifatto**:
24/24 stage discovery archiviati, 22 `RECORDED_COMPLETE`,
1 `INVALID_OUTPUT` C q032/A1_8R e 1 K
`BLOCKED_DEPENDENCY` conseguente; 23 claim reali,
363.753 token osservati. I record sono utilizzabili come
evidenze tecniche discovery, non attestano accuratezza
delle diagnosi né formalizzabilità delle K.
Un nuovo esperimento Gemini V2 sarebbe una replica
separata e va motivata, non una "riparazione" V1.

Nuovi file aggiunti sul branch:
- `src/evaluation/rq2_v1_gemini_readonly_audit.py`:
  legge l'archivio V1 reale con i verificatori SHA
  GT-free originali; output solo aggregati D/C/K,
  candidate/insufficient_evidence e preflight K;
  **zero API, zero scritture, zero GT**.
- `src/tests/test_rq2_v1_gemini_readonly_audit.py`:
  **8 test offline nuovi: dopo una prima esecuzione 7 PASS / 1 FAIL per una sola asserzione, correzione e RIESCUZIONE 8/8 PASS in 0.011 s (output utente)**. La suite globale nuova 852 è ancora da eseguire.
- `docs/ood/RQ2_DECISIONE_GEMINI_COMPLETATO_E_PERCORSO_REALE_V2_2026-11-13.md`:
  motivazioni e prossimi gate.

Il test `test_exact_24_record_summary_distinguishes_all_outcomes`
falliva per una ricerca di sottostringa `"ground_truth"`
che intercettava il metadato lecito
`"read_ground_truth": False` nel report.
Nel commit `1cbcd88d838cbbeacfb012c8b33f35765641a543`
è stata modificata **solo l'asserzione** per
verificare l'assenza della chiave GT esatta, anche
negli otto summary dei casi. Report:
`docs/ood/RQ2_GEMINI_READONLY_AUDIT_TEST_7PASS_1FAIL_ASSERTION_FIX_2026-11-13.md`.
Non modificare codice audit o risultati V1
per "riparare" la fixture. Nessuna API e nessuna GT.
Il riepilogo 8/8 PASS è documentato in
`docs/ood/RQ2_GEMINI_READONLY_AUDIT_8_8_PASS_2026-11-13.md`.
Il confronto statico con i record/claim V1 non mostra
incompatibilità note, ma la vera lettura degli artefatti
su Drive resta da fare, solo dopo la suite globale.

**Prossimo passo**: suite globale in PyCharm (attesi **852** test = 844+8, non ancora eseguiti).
Solo dopo effettuare audit Gemini V1 su Drive in
Google Colab, senza chiavi/API. Non dichiarare
nessun risultato dell'audit finché non viene eseguito.

Se le K Gemini richiedono ancora verifica, NON
promuoverle automaticamente a detector OOD.
Pilot V2 da preregistrare e autorizzare, candidato:
`cloudbed-1_q050 / Sonnet / A1 / D` con nuova
identità V2, nuovo archivio source-bound e
provenance `tool_call_id` reale. La D V1 corrispondente
resta `INVALID_OUTPUT` e non viene ritentata:
il pilot sarebbe un **nuovo protocollo**.
Attuale store V2 è ancora **synthetic-only**,
non autorizza Market né provider. Undici OOD
test LOCKED. Nessuna API eseguita qui.

## Audit Gemini V1: regressione 852/852 PASS e Colab pronto

L'utente ha riportato `Ran 852 tests in 78.413s / OK`
in PyCharm il 13 novembre 2026, dopo
`Ran 8 tests in 0.011s / OK` dell'audit mirato.
La precedente regressione 844/844 è quindi
superata e il nuovo totale di **852 PASS** è
un'evidenza software (non accuratezza RCA).

Documenti aggiornati:
- `docs/ood/RQ2_GATE_852_852_PASS_GEMINI_READONLY_AUDIT_READY_2026-11-13.md`;
- `docs/ood/RQ2_GEMINI_V1_COLAB_AUDIT_READONLY_DOPO_852_PASS_2026-11-13.md`.

Quest'ultimo contiene una **singola cella Colab**,
non ancora eseguita, con checkout separato
in `/content`, PIN_COMMIT
`489a53467087b8070c8909ceddad1d6aee74d02d`
e AUDIT_BLOB
`dd36792d8bd64ddfcd24e658d519f2e057b312ac`.
Il programma usa esclusivamente le sorgenti
GT-free e i record V1 già congelati, controlla
**39 record/32 claim V1 complessivi** e
**24 Gemini (22 complete, 1 invalid, 1 blocked)**,
raccoglie `candidate`, `insufficient_evidence` e
`requires_verification` reali e stampa un
riepilogo senza raw, GT o segreti.

**Prossimo passo preciso**: l'utente copia
la cella dal documento in un nuovo Colab, la
esegue UNA volta e riporta l'output.
Non lanciare altre API: l'audit non ha bisogno
di chiavi e non autorizza un provider.
Se la cella si ferma a un controllo, ispezionare
il traceback e non scrivere/rifare V1.
Non partire col pilot Sonnet finché non è pronto
lo store/journal V2 scientifico source-bound,
un protocollo firmato, source/runtime pin
e approvazione esplicita alla spesa.

Per la futura migrazione di chat: questo documento
e il report 852 sono il punto di ripartenza corrente.

## Gemini Colab audit REALE completato (13 novembre 2026)

**Output dell'utente:** `STATUS: GEMINI_V1_24_READONLY_AUDIT_OK`.
Cella eseguita con `GIT_HEAD=489a53467087b8070c8909ceddad1d6aee74d02d`,
`AUDIT_SOURCE_BLOB=dd36792d8bd64ddfcd24e658d519f2e057b312ac`,
dipendenze installate solo in `/content`.
`V1_TOTAL_RECORDS_ALL_PROVIDERS=39`,
`V1_TOTAL_CLAIMS_ALL_PROVIDERS=32`,
`UNRESOLVED_CLAIMS=0`,
`GROUND_TRUTH_READ=FALSE`, `API_CALLS=0`,
`V1_WRITES=0`, `OOD_TEST=LOCKED`.

**Risultato Gemini 24/24**:
22 `RECORDED_COMPLETE`, 1 `INVALID_OUTPUT`
(q032/A1_8R/C), 1 `BLOCKED_DEPENDENCY` (K conseguente).
**C: 3 diagnosis, 4 abstain, 1 invalid_output.**
**K: 2 candidate, 5 insufficient_evidence, 1 blocked.**
Le uniche due K `candidate` sono:
`cloudbed-2_q026/A1/K` e `cloudbed-2_q045/A1/K`;
entrambe `requires_verification`, non congelate.
Nessuna K pronta per OOD, nessun scoring GT di C.

Report registrato:
`docs/ood/RQ2_GEMINI_V1_AUDIT_REALE_24_24_K_2_CANDIDATE_2026-11-13.md`.

La cella Gemini read-only è **GIÀ ESEGUITA**
e NON va rilanciata senza un motivo scientifico nuovo.
Gemini V1 **non si ripete/riscrive**.

## Candidato prossimo pilot autentico Sonnet V2

Specifiche dettagliate:
`docs/ood/RQ2_V2_SONNET_PILOT_D_SOURCE_BOUND_SPEC_CANDIDATE_2026-11-13.md`.

È stato scelto ex ante come candidato
`cloudbed-1_q050 / sonnet / A1 / D` soltanto
(è già nota una D V1 con ambiguous same-name
tool calls, ma il record V1 resta immutabile).
Il pilot sarebbe un **nuovo protocollo V2**,
non retry/repair di V1 né test di generalizzazione.

**STATO: NO_API, NON ESEGUIBILE**. Mancano:
nuovo source-bound release/store/journal V2
per Market reale con SHA GT-free e claims,
integrazione live source-pin dell'esecutore
V2, test fake fail-closed, runtime/budget
congelato e consenso esplicito a una sola
D con costo provider. Lo store V2 attuale
richiede il marker `synthetic-only`: NON
aggirarlo, non copiarlo su Drive.

L'utente vuole finire gli esperimenti reali,
poi refactoring con commenti italiani e pulizia,
infine scrivere tesi. Scadenza 1 dicembre.
La prossima fase di codice deve puntare
direttamente alla release source-bound
V2 e non ad altri test generici.

## Decisioni ancora aperte

Senza nuovi esperimenti reali NON è dimostrata
la generalizzazione a nuove classi. Prima di
un pilot V2, il nuovo store reale richiederà:
source pin, release SHA, coorte/comparatori,
JSON/prompt e policy errori, journal/claim
create-only, budget stop e autorizzazione.
Una replica sui 4 discovery già analizzati
proverebbe robustezza tecnica, non generalizzazione
indipendente. Undici test OOD restano LOCKED.
Non implementare human-in-the-loop, per decisione
del relatore. Non accumulare nuove campagne se
compromettono la scrittura RQ1 e la scadenza tesi.

Nella ripresa, leggere anzitutto anche
`docs/ood/RQ2_SCHEDA_SCIENTIFICA_RELATORE_POST_844_PASS_2026-11-13.md`,
preparata dopo il gate 844. La prossima attività è
confrontarsi sulle decisioni della scheda, non
rilanciare il runner finto.

## Prompt di ripresa in una nuova chat

> Riprendiamo la tesi OpenRCA. Con connettore GitHub
> leggi per intero
> `docs/ood/HANDOFF_RQ2_V2_CONTINUITA_2026-11-13.md`
> sul branch
> `experiment/rq2-provenance-v2-offline-2026-11-13`,
> verifica HEAD/ultimo commit e report.
> Non modificare V1 né inventare risultati.
> L'ultima suite globale confermata è **852/852**
> (13 novembre, 78.413 s, OK); l'integrazione
> fake runner→V2→D/C/K→nuovo ledger era 3/3 PASS.
> L'audit Gemini V1 READ-ONLY è stato eseguito
> con successo in Colab: 24/24 stage, 22 complete,
> 1 invalid, 1 blocked; C 3 diagnosis/4 abstain/1 invalid;
> K 2 candidate/5 insufficient/1 blocked,
> nessuna K frozen. No API, no GT, no V1 writes.
> Leggi
> `docs/ood/RQ2_GEMINI_V1_AUDIT_REALE_24_24_K_2_CANDIDATE_2026-11-13.md`
> e
> `docs/ood/RQ2_V2_SONNET_PILOT_D_SOURCE_BOUND_SPEC_CANDIDATE_2026-11-13.md`.
> Leggi anche
> `docs/ood/RQ2_V2_844_844_GATE_TECNICO_CHIUSO_DECISIONE_SCIENTIFICA_2026-11-13.md`.
> Il gate tecnico offline è chiuso. L'utente vuole
> concludere esperimenti reali, poi fare refactoring
> con commenti italiani/pulizia, poi scrivere la tesi.
> Gemini V1 read-only Colab già completato;
> ora implementare e validare pilot Sonnet V2
> con nuovo store reale e autorizzazione. La scheda
> scientifica per il relatore è stata pubblicata:
> `docs/ood/RQ2_SCHEDA_SCIENTIFICA_RELATORE_POST_844_PASS_2026-11-13.md`.
> Procedi alla decisione metodologica fra studio
> esplorativo e un singolo pilot reale preregistrato,
> solo se giustificato e autorizzato,
> senza API adesso, senza OOD e senza modificare V1.
> Continua con commit GitHub e PyCharm/PowerShell.

In una chat successiva verificare HEAD perché
nuovi commit/test potrebbero aver aggiornato lo stato.
