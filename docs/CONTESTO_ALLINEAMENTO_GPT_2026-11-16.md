# Contesto di allineamento per un secondo assistente (GPT) — 16 novembre 2026

Scopo: dare a un altro assistente lo stesso quadro che ho io, con **solo fatti
verificati** e con i punti non verificati dichiarati. Ogni affermazione sul
repository va controllata nei file, non data per buona.

## 1. Chi, cosa, quando

- Tesi magistrale di Alessio, Università di Catania, ingegneria informatica.
  Relatore: Giovanni Morana.
- Titolo: *Harness Engineering for LLM-based Root Cause Analysis*, benchmark
  OpenRCA, telemetria Market (cloudbed-1 e cloudbed-2, 148 query).
- **Consegna: 5 dicembre 2026.** Un contesto precedente scriveva 1 dicembre:
  era sbagliato. Restano circa 19 giorni dal 16 novembre: ~9 per gli esperimenti
  (fino a ~25 novembre), ~10 per la scrittura.
- Budget API: il relatore ha detto di non preoccuparsene. Non esiste comunque
  un tetto rigido lato provider: se serve un limite di spesa va impostato dal
  pannello del provider.

## 2. Le due domande di ricerca

- **RQ1 — completata e approvata dal relatore (10 novembre).** Un harness
  deterministico (raccolta e selezione delle evidenze, 8 regole R01, R02,
  R06–R11, verifica ispirata a PAVE) migliora accuratezza ed efficienza di un
  agente LLM. Cinque varianti: A0, A1, A1_8R, A1_8R_Planning, A1_PAVE (nomi
  storici A1_V2, A1, A1_VERIFY, A1_VERIFY_ST). Punteggio con lo scorer
  ufficiale Microsoft. Non si tocca.
- **RQ2 — in corso.** Le 8 regole coprono 8 delle 15 classi di guasto. Si
  studia se un agente LLM sappia investigare le **4 classi escluse** (CPU spike
  del nodo, carico di I/O in scrittura del container, terminazione di processo
  del container, packet loss del container) e se la conoscenza ottenuta possa
  diventare, dopo verifica, una **nuova regola deterministica**.
  Ciclo per ogni incidente: **D** (diagnosi, con tool) → **C** (spiegazione
  della causa) → **K** (regola candidata nel contratto `rq2_candidate_rule_v0`).
  Human-in-the-loop e integrazione automatica nell'harness: **solo lavoro
  futuro**, non si implementano.
- Nota di conteggio, da chiarire: le 8 regole (`src/harness/rule_batch.py`:
  container CPU, memoria, read I/O; nodo CPU load, memoria, read I/O, write
  I/O, spazio disco) più le 4 classi escluse fanno 12 su 15. **Restano 3
  classi** né coperte dalle regole né oggetto di RQ2. Non le ho ricostruite;
  `docs/ARCHITETTURA_E_RISULTATI_V3.md` cita casi di rete non coperti
  (`cloudbed-1_q005`, `q027`). La tesi deve dichiarare questo perimetro.
- Il file `2606.27154v2.pdf` del Project è OpenRCA 2.0 (PAVE, altri sistemi),
  **non** il benchmark usato: i dati sono OpenRCA 1.0, sistema Market
  (148 casi, 44 componenti, 15 cause). PAVE serve come fonte dei principi di
  verifica (strutturale, statistico, temporale) dell'harness A1_PAVE.

## 3. Perimetro sperimentale RQ2

- 5 harness × 3 modelli (Gemini `gemini-3.5-flash-lite`, `claude-sonnet-5-5`,
  `claude-haiku-5-5`) × 4 incidenti discovery × 3 stage = **180 stage**.
- Discovery (4): `cloudbed-1_q032`, `cloudbed-1_q050`, `cloudbed-2_q026`,
  `cloudbed-2_q045`.
- Test **sigillati** (11, mai usati in discovery):
  `cloudbed-1_q014, q021, q030, q059`; `cloudbed-2_q014, q021, q040, q041,
  q058, q076, q077`. Per classe: 2 / 2 / 3 / 4; la classe write-I/O compare
  solo in cloudbed-2. Con n così piccolo i risultati sono una **dimostrazione
  di fattibilità**, non una stima statistica.
- Partizione V1: non congelata.

## 4. Il problema che ha originato V5

In V4 le risposte valide di Gemini erano JSON puro; i D di Sonnet e Haiku
avevano un JSON interno valido e conforme al task, ma **avvolto in un blocco
Markdown** (```json ... ```), che il parser strict rifiuta alla posizione 0.
Audit in sola lettura sui record V4 (commit `8b64be7`, esito in
`docs/ood/RQ2_V4_AUDIT_FENCE_CLAUDE_E_POLITICA_FORMATO_V5_2026-11-16.md`):
il difetto è di **formato**, non di contenuto. Confrontare i modelli con il
parser strict puro misurerebbe l'aderenza al formato, non la capacità
diagnostica.

## 5. Politica di formato V5 (unica, senza parametri per modello)

`src/evaluation/rq2_v5_response_normalization.py`, politica
`rq2_v5_single_json_fence_v1`:

- se **l'intera** risposta è esattamente un blocco ```json ... ``` (o ``` senza
  lingua), il contenuto interno passa **inalterato** al parser strict;
- in ogni altro caso (testo fuori dal fence, più fence, altra lingua, fence non
  chiuso) la risposta resta quella originale e il parser la rifiuta;
- nessuna riparazione del JSON, nessuna estrazione da testo libero, nessun retry;
- ogni risposta registra `deviation` (`NONE`, `SINGLE_JSON_FENCE`,
  `REJECTED_WRAPPER`), hash SHA-256 e **testo originale**. Si riportano sempre
  **entrambe** le conformità, strict (nessuna deviazione) e tollerante, per
  tutti i modelli.
- La politica è motivata dall'osservazione V4 e dichiarata **prima** di
  qualsiasi stage V5. Va descritta così nella tesi, non come scelta a priori.
- Applicata allo stesso modo a D (dentro il ponte V3 del testo finale), C e K.
  I contratti strict V2 e `rq2_output_contracts` non sono stati modificati.

## 6. Cosa è stato costruito (branch `feature/rq2-v5-format-fairness-2026-11-16`)

Repository: `https://github.com/alessio1996A/Tesi_Laurea_Magistrale_OpenRCA`.
Commit: `b8eccb6` (politica), `8b64be7` (audit), `0294ed7` (doc),
`bccb246` (runner), `ec56837` (namespace pilota, test CLI).

- `rq2_v5_matrix_runner.py` — runner a matrice, solo libreria standard.
  Claim create-only **prima** di ogni chiamata a pagamento, record create-only
  con SHA, nessuna riesecuzione automatica, claim orfani segnalati e mai
  rieseguiti, dipendenze D→C→K con `BLOCKED_DEPENDENCY`, riepilogo.
  Stato aggiunto rispetto a V4: `RECEIPT_REJECTED` (il modello ha risposto ma
  la ricevuta V4 è stata rifiutata; l'output grezzo resta salvato).
  `StageStore.release_orphan` sblocca un orfano solo su chiamata esplicita con
  motivazione e log: il runner non la chiama mai.
- `rq2_v5_stage_executor.py` — D, C, K reali, riusando senza modifiche le parti
  pure V4 (ExperimentConfig, run_experiment, ponte V3, pacchetti C/K, chiamata
  unica C/K, normalizzatori di ricevuta). Lascia fuori solo i cancelli di
  release/attestazione del ledger V4 (scelta "opzione B", runner magro).
- `rq2_v5_run_cli.py` — `check` (nessuna API), `run`, `summary`; manifest con
  invarianti tra lotti (piano, politica, hash dei prompt C/K, budget D).
  Un pilota usa un archivio separato (`--namespace`).
- Test: `test_rq2_v5_*_offline.py`.
  `PYTHONPATH=src:src/tests python3 -m unittest discover -s src/tests -p "test_rq2_v5_*_offline.py"`
  Nella sandbox senza LangChain: 70 test passano, 11 (esecutore reale) sono
  saltati; vanno eseguiti dove LangChain è installato.

## 7. Cosa è verificato e cosa no (alle 10:30 del 16 novembre)

Verificato:
- 70 test offline (sandbox), incluso il confronto con i **veri** contratti C/K.
- Riferito da Alessio: test PyCharm ok; in Colab `check` ok sul commit
  `ec56837` (snapshot SDK ok, 6 stage D preparati, checkout pulito, chiavi
  presenti).

**Non** verificato:
- Nessuna chiamata reale a un provider è ancora stata fatta con il runner V5.
  Il pilota (3 modelli × {A0, A1_PAVE} × `cloudbed-1_q032` = 18 stage) è il
  passo successivo.
- Che Sonnet e Haiku ora superino il contratto in tutti e tre gli stage.
- La causa del `PROVIDER_ERROR` di Gemini in un K di V4 (messaggio sanitizzato).
- Il conteggio dei token tra provider non è confrontabile alla pari: Claude ha
  `max_tokens=4096` condiviso con l'eventuale ragionamento esteso.

## 8. Cosa manca per chiudere RQ2

1. Pilota, poi run completo in lotti riprendibili (D ~3–4 min a stage in Colab).
2. Esecutore offline delle regole K candidate sui 11 incidenti sigillati più
   controlli negativi, con criteri di successo **preregistrati**. Non è ancora
   stato verificato se esista codice riusabile (`rq2_rule_group_scorer.py`,
   `rq2_v2_k_quality_rubric.py`, `rq2_kpi_formalizability_preflight.py`).
3. Scoring ufficiale di D sui 4 casi discovery dopo il congelamento.
4. Decisione su retry: oggi nessuno. Proposta in valutazione: al più un retry
   preregistrato solo per errori di trasporto senza output del modello, mai per
   output invalidi.
5. Limite di spesa lato provider.
6. Poi: refactoring (cartelle, file superflui, commenti in italiano), scrittura.

## 9. Regole di lavoro condivise

- **Un solo agente scrive su un branch.** Su
  `feature/rq2-v5-format-fairness-2026-11-16` scrive Claude. Chi altro vuole
  proporre codice usa un branch proprio (`gpt/<tema>`) e lo dice ad Alessio.
- Non modificare i file V4/V3/V2 congelati né i risultati RQ1.
- Mai leggere ground truth, scorer o i 11 casi sigillati durante la discovery.
- Nessun retry nascosto, nessuna riparazione del JSON del modello.
- Ogni numero porta la sua fonte (file, commit, record). Se non è verificato,
  scrivere "non verificato".
- Un solo documento di stato breve, aggiornato a ogni tappa, invece di handoff
  lunghi.

## 10. Dove un revisore indipendente aiuta di più

1. **Equità della politica V5**: è una tolleranza difendibile e dichiarata
   prima? Può favorire o penalizzare un modello? Il doppio report strict e
   tollerante basta?
2. **Criteri di successo preregistrati** per le regole K sui 11 incidenti
   (cosa conta come regola "verificata", quali controlli negativi, quale
   prudenza sulle affermazioni con n piccolo).
3. **Revisione di sola lettura** di `rq2_v5_matrix_runner.py` e
   `rq2_v5_stage_executor.py`: bug, condizioni di corsa, casi limite.
4. **Struttura del capitolo RQ2** e linguaggio delle limitazioni.
