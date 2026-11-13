# RQ2 — Gemini V1 utilizzabile; percorso verso gli esperimenti reali V2

**Data:** 13 novembre 2026  
**Branch di lavoro V2:** `experiment/rq2-provenance-v2-offline-2026-11-13`  
**Stato:** piano di lavoro e audit GT-free, non release V2 e non permesso API.

## Decisione sui risultati Gemini

Dai rapporti verificati del 13/11:
- **Gemini V1 discovery 24/24** stage registrati su 4 casi × A1/A1_8R × D/C/K.
- **22 RECORDED_COMPLETE**, **1 INVALID_OUTPUT** e
  **1 BLOCKED_DEPENDENCY**. Non correggere/ripetere gli stage V1.
- Stage invalid: `cloudbed-1_q032 / gemini / A1_8R / C`,
  errore di contratto C. K bloccata correttamente offline.
- **23 claim reali**, nessuno irrisolto all'ultimo audit riportato.
- **363.753 token osservati** (non costo fatturato).
- `RECORDED_COMPLETE` significa esito tecnico;
  una diagnosi C non è ancora confrontata con la GT.
- K con `candidate` e `requires_verification`
  non è detector pronto. K con `insufficient_evidence`
  è un risultato legittimo di astensione. Al momento
  **nessuna regola Gemini K può essere promossa all'OOD**.
- **Non modificare prompt/parser di Gemini a posteriori**, perché
  ciò renderebbe il protocollo incompatibile con V1 congelato.

### Gate immediato: audit Gemini V1 REALI, senza costi

Nuovo modulo `src/evaluation/rq2_v1_gemini_readonly_audit.py`.
Legge gli artefatti V1 dal loro archivio reale, controllato dai
verificatori SHA e schema originali, e riporta **soltanto**
gli otto arm Gemini discovery, status D/C/K,
decisione C `diagnosis|abstain`, tipo K
`candidate|insufficient_evidence`, preflight K
`requires_verification|insufficient_evidence`.
Rifiuta status alterati, claim mancanti e qualunque
`scientific_freeze=true` sulle K non confermate.

Non stampa raw response, fault class suggerite, prompt,
dati di telemetria, metriche o campi GT. Non scrive file.
I test `test_rq2_v1_gemini_readonly_audit.py`
sono **8 nuovi metodi ancora da eseguire localmente**.
Se superati, una cella Colab dedicata avvierà SOLO
il summary audit su Drive (senza API).

## Decisione sui modelli restanti

Sonnet V1: 15/24 stage, tre D invalid per
`AMBIGUOUS_TOOL_RESULT` (mancanza di `tool_call_id`
nel runner originale). Haiku V1: 0/24 stage.

**NON proseguire V1 alla cieca con altri modelli:**
il problema è strutturale e può produrre nuovamente invalid.
Non riavviare i tre tentativi Sonnet invalid, che rimangono
immutable come record V1.

**V2 è un protocollo distinto** che conserva
`tool_call_id`, con nuova radice, nuovi ID e
nuovo claim journal. Lo store/journal già testati
con 844/844 sono **sintetici** e rifiutano Market
reale: prima di live serve implementare e verificare
una release V2 source-bound con hash e preflight reali.

### Primo pilot reale candidato (NON ancora autorizzato)

- Provider: **Claude Sonnet 5.5**;
- Caso discovery: `cloudbed-1_q050`;
- Harness: **A1**; stage iniziale: **D**;
- Scopo: verificare il passaggio dei reali
  `tool_call_id` dal provider fino al bundle osservativo.
- Motivazione: la corrispondente D **V1** aveva
  `AMBIGUOUS_TOOL_RESULT`; la nuova esecuzione
  deve essere un **nuovo stage V2**, NON un retry V1.
- Successo tecnico: claim/record V2 validi e
  riconciliazione univoca delle risposte tool,
  in presenza di tool call omonime effettivamente
  osservate. Se il provider non produce tale pattern,
  il pilot dimostra solo il flusso standard, non
  l'eliminazione empirica dell'ambiguità.
- Esito fallito: `INVALID_OUTPUT` o `PROVIDER_ERROR`
  registrato senza retry; non falsificare un successo.
- D è multi-round: una sola D può inviare più richieste
  HTTP; stimare e approvare costi, token e stop prima.
- C/K dell'arm SOLO se autorizzati con un nuovo gate
  e se la D è `RECORDED_COMPLETE`.

Non avviare API fino a:
1. protocollo V2 preregistrato su coorte/scopo/denominatori;
2. nuovo store/journal **reale** con SHA di release,
   SHA source, modello, timeout, tool/JSON/prompt e
   salvataggio create-only testato;
3. snapshot esatto dei package/runtime e prova di
   lettura SHA dei GT-free source; OOD test chiuso;
4. prova fake con il nuovo store V2 reale;
5. approvazione esplicita del numero di stage e spesa.

## Come completare scientificamente RQ2 senza ripetizioni inutili

Obiettivo dell'utente: **concludere gli esperimenti reali,
poi refactoring/commenti in italiano e pulizia, infine
stesura tesi**. Preservare questo ordine, considerando
la scadenza 1 dicembre.

Sequenza di decisioni:
1. **Ora:** audit read-only delle 24 Gemini V1 (stati K).
2. **Poi:** build e audit source-bound di release/store
   V2 indipendenti; un solo pilot Sonnet D come gate.
3. **Se pilot OK:** decidere PRIMA della campagna
   quali discovery Sonnet/Haiku V2 sono necessarie
   e come contabilizzare Gemini V1:
   - Gemini V1 non va rieseguito solo per comodità.
   - Confronti **Gemini V1 vs Anthropic V2**
     hanno confondimento di versione di harness;
     descriverli come osservazioni, NON affermare
     parità sperimentale o causalità cross-model.
   - Per confronto strettamente a parità di protocollo,
     occorrerebbe una campagna V2 anche Gemini, con
     nuova preregistrazione, costo e rischio di
     duplicazione. Non assumerla necessaria.
4. **Prima del test OOD:** verificare K formalizzabili
   su sole sorgenti development GT-free; congelare
   eventuali regole deterministiche, baselines,
   scorer, arm, outcome e denominator; consentire
   anche 0 regole formalizzabili.
5. **Soltanto dopo freeze** decidere se sbloccare
   gli 11 OOD test per RQ2-A e/o RQ2-C. La
   valutazione primary `correct/11` per arm,
   i 10 gruppi temporali e lo scoring separato
   sono documentati nella preregistrazione originaria.
6. **Infine:** freeze campagne e report,
   refactoring senza toccare protocolli/sorgenti
   referenziati, commenti italiani, pulizia
   e stesura della tesi.

Nessun passaggio successivo è avviato automaticamente.
**NON** utilizzare codice synthetic-only per Market reale.

## Provenienza dei dati

- `RQ2_GEMINI_DISCOVERY24_ESITO_REALE_CONSOLIDATO_2026-11-13.md`;
- `RQ2_GEMINI_BATCH01_INVALID_C_ARCHIVIO_2026-11-12.md`;
- `RQ2_DECISION_GATE_AFTER_39_DISCOVERY_RECORDS_2026-11-13.md`;
- `RQ2_DISCOVERY_PREREG_V1_CANDIDATE_2026-11-12.md`;
- `RQ2_REVIEW_SCIENTIFICO_PRIMA_RELEASE_2026-11-12.md`;
- `RQ2_V2_844_844_GATE_TECNICO_CHIUSO_DECISIONE_SCIENTIFICA_2026-11-13.md`.

**Nessun dato reale, GT o API consultato dal nuovo modulo
durante la creazione del presente documento.**
