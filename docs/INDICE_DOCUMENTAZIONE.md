# Indice della documentazione — OpenRCA V3 (3 novembre 2026)

Questo indice separa **la documentazione corrente per il relatore** dai
documenti che testimoniano le iterazioni precedenti.

## Documenti correnti — da mostrare

1. [README principale](../README.md): obiettivo, varianti, risultati e istruzioni.
2. [Architettura e interpretazione V3](ARCHITETTURA_E_RISULTATI_V3.md):
   pipeline, tool, planner, verifica e risultati osservati.
3. [Piano di pulizia sicura](PULIZIA_CODICE_V3.md):
   inventario, cosa mantenere e cosa non eliminare.
4. **Notebook su Google Drive**: `Tesi_OpenRCA/demo_relatore/Demo_Relatore_OpenRCA_V3.ipynb`.
   È una demo di **replay**, senza chiamate Gemini.

## Documenti storici — conservati per tracciabilità

- `HARNESS_V2_PLAN_2026-11-03.md`;
- `V2_3_REAL_FROZEN_AUDIT_2026-11-03.md`;
- `V2_4_TASK_AWARE_RUNNER_2026-11-03.md`;
- `V2_5_COHORT_PROPOSAL_2026-11-03.md`;
- `V2_6A_A0_SHA_REVISION_2026-11-03.md`;
- `V2_6B_DEPENDENCY_RECOVERY_2026-11-03.md`;
- `V2_6_PREREGISTRATION_RUNBOOK_2026-11-03.md`;
- i protocolli `a1_verify_*.md`, il piano refactoring del 1 novembre,
  e `PRESENTAZIONE_RELATORE.md` del 2 novembre.

I documenti storici riportano lo stato **alla data in cui furono scritti**;
non sono la fonte aggiornata dei risultati della campagna V3.

## Conservazione dei dati sperimentali

- Commit sperimentale congelato:
  `6747eecc77c1b2fff7d581c7284578b5c574b4f7`.
- Piano del protocollo V3 e 40 JSON/claim: su Google Drive.
- Scoring ufficiale V3: 40 output già valutati su development,
  senza alcuna ripetizione dell'inferenza.
- Ogni successivo commit sul branch di presentazione modifica **il progetto
  mostrato**, non retroattivamente il codice con cui furono prodotte le run.
