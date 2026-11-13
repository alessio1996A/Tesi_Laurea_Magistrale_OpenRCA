# RQ2 — 852/852 suite globale PASS, audit Gemini V1 in Colab pronto (NO API)

**Data:** 13 novembre 2026. **Branch:** `experiment/rq2-provenance-v2-offline-2026-11-13`.
**Fonte:** stdout della suite `unittest` locale PyCharm riportato dall'utente.

## Evidenza software confermata

```text
Ran 852 tests in 78.413s

OK
```

La regressione precedente era **844/844**; sono stati
aggiunti 8 metodi in `test_rq2_v1_gemini_readonly_audit.py`.
Il gate mirato aveva fallito 1/8 per l'asserzione
sulla sottostringa `ground_truth` presente nel
metadato `read_ground_truth=False`. La verifica
è stata corretta senza alterare il modulo audit,
poi l'utente ha confermato `8/8 OK`; infine
`852/852 OK` nella suite globale.

**Nessuna esecuzione RCA reale è stata prodotta dai
nuovi test**. Non sono state effettuate API o
scritture in V1 da parte di questo lavoro.

## Fonte e stato reale Gemini precedente

I report Colab già archiviati attestano **24/24**
stage Gemini V1 discovery: 22 RECORDED_COMPLETE,
1 INVALID_OUTPUT C `cloudbed-1_q032/A1_8R`,
1 K BLOCKED_DEPENDENCY senza claim. 23 claim
Gemini e 363.753 token osservati. Lo stato
globale V1 osservato era 39 record e 32 claim.
Sono risultati veri, non vanno ritentati.

Le K con `candidate` e `requires_verification`
non sono ancora formalizzate. Non inferire che
Gemini abbia ottenuto accuratezza OOD.

## Prossimo gate: una sola cella Colab read-only

Documento operativo:

`docs/ood/RQ2_GEMINI_V1_COLAB_AUDIT_READONLY_DOPO_852_PASS_2026-11-13.md`

La cella:
- controlla Python 3.13.18, recupera in `/content`
  un checkout separato al commit `489a53467087b8070c8909ceddad1d6aee74d02d`
  (include i test dopo il fix);
- verifica il Git blob `dd36792d8bd64ddfcd24e658d519f2e057b312ac`
  del sorgente read-only;
- riusa solo dipendenze pinned con marker esatto o
  le installa **solo** in `/content`;
- monta Drive senza scrivere ai record della tesi;
- carica il journal V1 in sola lettura verificando
  SHA di sorgenti GT-free, claim, record e dipendenze;
- richiede V1 globale ancora a 39 record / 32 claim,
  0 unresolved, Gemini a 24/24 e 22/1/1;
- stampa soltanto un riepilogo delle decisioni
  C e delle K `candidate/insufficient_evidence`,
  senza risposte raw, etichette GT o dati di telemetria;
- non legge ground truth, non esegue scoring
  e non accede all'OOD test, che rimane LOCKED;
- rimuove dal subprocess variabili con credenziali
  provider/tracing, non invoca API.

**La cella non è stata ancora eseguita dall'utente.**
Se il gate trova drift, STOP e audit manuale, nessuna
riparazione automatica degli archivi V1.

## Roadmap successiva

Dopo il riepilogo K reale, decidere come verificare
la formalizzabilità delle regole solo con fonti
development GT-free. Parallelamente preparare
**nuovo** source-bound store/journal scientifico
V2 e un eventuale pilot Sonnet D, con protocollo
e consenso spesa indipendenti. Il current store
V2 rimane synthetic-only, non utilizzabile
per Market reale.

Nessun nuovo esperimento Gemini proposto ora.
Tesi: chiudere gli esperimenti reali →
freeze → refactoring/commenti italiani/pulizia →
stesura entro il 1 dicembre 2026.
