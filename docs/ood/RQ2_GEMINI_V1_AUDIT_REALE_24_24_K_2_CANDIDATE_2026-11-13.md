# RQ2 — Audit reale Gemini V1: 24/24 stage, 2 K candidate, 5 K insufficient

**Data:** 13 novembre 2026.
**Branch documentale V2:** `experiment/rq2-provenance-v2-offline-2026-11-13`.
**Fonte primaria:** output Google Colab dell'audit read-only
`evaluation.rq2_v1_gemini_readonly_audit` comunicato dall'utente.
**Questa è un'analisi di artefatti V1 già esistenti, NON una nuova campagna.**

## 1. Provenienza verificata

```text
Mounted at /content/drive
DRIVE_V1_SOURCE_PATHS: PRESENT (not modified)
GIT_HEAD: 489a53467087b8070c8909ceddad1d6aee74d02d
AUDIT_SOURCE_BLOB: dd36792d8bd64ddfcd24e658d519f2e057b312ac
DEPS: INSTALLED_IN_TEMP_PATH
STATUS: GEMINI_V1_24_READONLY_AUDIT_OK
V1_TOTAL_RECORDS_ALL_PROVIDERS: 39
V1_TOTAL_CLAIMS_ALL_PROVIDERS: 32
UNRESOLVED_CLAIMS: 0
GROUND_TRUTH_READ: FALSE | API_CALLS: 0 | V1_WRITES: 0 | OOD_TEST: LOCKED
```

I controlli source-bound del journal V1 hanno confermato
39 record, 32 claim, nessun claim irrisolto.
Nessuna API, nessuna nuova lettura di GT/score/test OOD,
nessuna modifica agli archivi.

## 2. Stato tecnico Gemini

```text
COUNTS_BY_STATUS: {"BLOCKED_DEPENDENCY": 1, "INVALID_OUTPUT": 1, "RECORDED_COMPLETE": 22}
C_DECISIONS: {"abstain": 4, "diagnosis": 3, "invalid_output": 1}
K_CONTRACT: {"blocked_dependency": 1, "candidate": 2, "insufficient_evidence": 5}
K_PREFLIGHT: {"insufficient_evidence": 5, "requires_verification": 2}
```

| Metrica | Conteggio | Denominatore |
|---|---:|---:|
| Stage discovery Gemini archiviati | 24 | 24 previsti |
| RECORDED_COMPLETE | 22 | 24 |
| INVALID_OUTPUT | 1 | 24 |
| BLOCKED_DEPENDENCY | 1 | 24 |
| C `diagnosis` | 3 | 8 arm |
| C `abstain` | 4 | 8 arm |
| C `invalid_output` | 1 | 8 arm |
| K `candidate` | 2 | 8 arm |
| K `insufficient_evidence` | 5 | 8 arm |
| K `blocked_dependency` | 1 | 8 arm |
| K `requires_verification` | 2 | 8 arm |
| K scientificamente congelate e pronte per OOD | 0 | 8 arm |

**Nota:** le `diagnosis` di C sono output di
classificazione GT-free, non tre diagnosi corrette.
Le due `candidate` non sono due regole operative:
richiedono verifica indipendente di segnali, unità,
aggregazioni, soglie, gestione di missing e astensione.

## 3. Dettaglio per caso e harness (solo metadati)

| Caso discovery | Harness | D | C | Decisione C | K | Tipo K | Preflight K |
|---|---|---|---|---|---|---|---|
| cloudbed-1_q032 | A1 | complete | complete | abstain | complete | insufficient_evidence | insufficient_evidence |
| cloudbed-1_q032 | A1_8R | complete | INVALID_OUTPUT | — | BLOCKED_DEPENDENCY | — | — |
| cloudbed-1_q050 | A1 | complete | complete | abstain | complete | insufficient_evidence | insufficient_evidence |
| cloudbed-1_q050 | A1_8R | complete | complete | abstain | complete | insufficient_evidence | insufficient_evidence |
| cloudbed-2_q026 | A1 | complete | complete | diagnosis | complete | candidate | requires_verification |
| cloudbed-2_q026 | A1_8R | complete | complete | abstain | complete | insufficient_evidence | insufficient_evidence |
| cloudbed-2_q045 | A1 | complete | complete | diagnosis | complete | candidate | requires_verification |
| cloudbed-2_q045 | A1_8R | complete | complete | diagnosis | complete | insufficient_evidence | insufficient_evidence |

Le astensioni non sono automaticamente errori: se manca
un'osservazione sufficiente, la pipeline deve astenersi.
La C invalida q032/A1_8R è conservata senza retry;
la K bloccata non ha generato un tentativo API.

## 4. Decisioni metodologiche

1. **Gemini V1 discovery è completo e immutabile.**
   Non modificare prompt, parser, status o record per
   migliorare i conteggi ex post. Non spendere nuovi
   token Gemini sulla medesima V1.
2. **Non promuovere ora le due K candidate al test OOD.**
   Occorre controllare struttura, realizzabilità delle
   metriche, unità e soglie su fonti development GT-free
   e poi congelare regole deterministiche verificabili.
   Al momento freeze scientifico = falso.
3. **Non dedurre da 2/8 K candidate un tasso di accuracy.**
   Sono indici di generazione di proposta, non
   correctness, causalità o trasferimento su holdout.
4. **Per Sonnet/Haiku la V1 ha una limitazione tecnica
   specifica** (`AMBIGUOUS_TOOL_RESULT` in tre D Sonnet).
   Conservare V1 e progettare una versione V2 separata
   con `tool_call_id` reale e nuovo archivio GT-free.
   Un eventuale confronto Gemini V1 vs Anthropic V2
   non è un confronto a parità di esecutore.
5. **Pilot V2 candidato:** Sonnet / cloudbed-1_q050 /
   A1 / D, già noto come incidente con tool call
   omonime ambiguamente attribuite nella V1.
   Il pilot sarebbe nuovo stage/protocollo;
   non replay/riqualificazione del vecchio claim V1.
   Successo tecnico da misurare sulla provenance
   reale; qualunque risultato provider fallito
   permane e non si ritenta automaticamente.
6. **Aperture indispensabili prima di una chiamata API:**
   protocollo preregistrato, store/journal V2
   *reale* separato (attuale è synthetic-only),
   source/commit/version pin, permesso/limitazioni di
   tentativi e costo, prova fake, autorizzazione
   esplicita del pilot e OOD ancora bloccato.

## 5. Conseguenza per la tesi

La discovery Gemini fornisce un risultato
interessante, **anche se non positivo in senso forte**:
solo due proposte di regola su otto arm, cinque
astensioni K e nessuna formalizzazione verificata.
Questo può essere discusso come limite empirico
dell'harness nel convertire osservazioni in
conoscenza operativa, senza confondere prova tecnica
e generalizzazione.

La priorità operativa desiderata dall'utente è:
**terminare esperimenti reali → refactoring/commenti
in italiano e pulizia file → stesura tesi**.
Preservare 1 dicembre 2026 come scadenza e non
moltiplicare esperimenti non preregistrati.

**Nessuna nuova API o modifica V1 eseguita in questo gate.**
