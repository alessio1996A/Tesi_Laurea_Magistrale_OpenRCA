# RQ2-V2 — Colab Google Drive scratch lock + create-only PASS (15/11/2026)

## Evidenza effettiva ricevuta

In Colab, dopo aver montato Google Drive, l'utente ha eseguito
la sonda di concorrenza su una cartella TEMPORANEA separata da
`/content/drive/MyDrive/Tesi_OpenRCA`:

```text
SCRATCH: /content/drive/MyDrive/rq2_v2_lock_probe_vxgwo2a8
=== 1/2: LOCK TRA PROCESSI ===
LOCK: PASS
=== 2/2: CREAZIONE ESCLUSIVA ===
CREATE-ONLY: PASS
=== REPORT DRIVE ===
{
  "status": "DRIVE_SAME_RUNTIME_SINGLE_WRITER_SCRATCH_PASS_NO_API",
  "concurrent_processes": 8,
  "exclusive_file_creators": 1,
  "lock_second_process_denied": true,
  "lock_released_and_reacquired": true,
  "other_colab_sessions_or_vms_verified": false,
  "model_requests_sent": 0,
  "data_root_modified": false
}
SCRATCH_REMOVED: True
```

**Risultato**: prova positiva di `fcntl.flock(LOCK_EX | LOCK_NB)`
su due processi separati nello STESSO runtime e prova concorrente
di `os.open(O_CREAT | O_EXCL)` con 8 writer: un creatore, 7
`FileExistsError`. Il lock è riacquisibile dopo il rilascio.
Cartella scratch eliminata; nessun file sperimentale storico toccato;
nessun provider o API LLM chiamato.

## Cosa NON dimostra

- NON è verifica di atomicità/visibilità tra runtime Colab, VM o
  sessioni separate; `other_colab_sessions_or_vms_verified=false`.
- NON garantisce persistenza remota sincrona, durata completa del
  singolo stage, assenza di crash o sincronizzazione Drive fra host.
- NON convalida costi, disponibilità dei modelli, enforcement timeout,
  retry sottostanti agli SDK né la release scientifica.
- NON prova che si possano lanciare writer multipli sulla stessa
  radice: **vietare esplicitamente sessioni concorrenti**.
- NON trasforma il source commit già verificato
  `601dc7c2f971b919962ff190e6feb192c4dd237a` in una
  release firmata. Il branch GitHub è avanzato per la documentazione
  ma gli SHA del source preflight fanno riferimento al commit
  effettivamente controllato in Colab.

## Decisione operativa

Usare, qualora il pilot venga approvato, una sola sessione Colab
con writer seriale, un solo stage per volta e claim create-only G4F
prima del provider. Prima di qualsiasi retry dopo crash, audit
manuale sugli orphan; non sbloccare API su base del solo scratch PASS.
Ulteriori controlli da completare: snapshot sorgenti/versioni SDK
effettivamente installate nel runtime, verifica policy retry/timeout,
tariffe aggiornate, budget operativo e release SHA esterna con
approvazione esplicita del singolo stage. Gli 11 OOD restano LOCKED.

**Contesto**: preflight reale Colab GT-free 29 sorgenti PASS, report
`docs/ood/RQ2_V2_UNIFIED_COLAB_29_SOURCE_REAL_GT_FREE_PASS_2026-11-15.md`.
Le sette suite locali G4A/G4F/G4G/G4H/G4I/G4J/G4K sono
tutte PASS (145 test complessivi), ma non sono una campagna API.
