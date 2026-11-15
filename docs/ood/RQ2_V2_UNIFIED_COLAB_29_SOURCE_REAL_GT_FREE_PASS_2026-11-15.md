# RQ2-V2 — Colab source preflight reale: 29/29 PASS, 0 API

Data: 2026-11-15. Report JSON *effettivamente riportato dall'utente*
dopo recupero esplicito dell'output del sottoprocesso Python di
`preview_unified_source_bound` + `build_unified_release_blueprint`
+ `preview_scientific_ledger_gate`.

```json
{
  "status": "RQ2_V2_29_SOURCE_REAL_GT_FREE_PREFLIGHT_OK_NO_API",
  "commit": "601dc7c2f971b919962ff190e6feb192c4dd237a",
  "source_file_count": 29,
  "source_inventory_sha256": "32457ec256e0fc430580f6d2205a50983811784f5ce87917ca3d2f79ea0fbe9e",
  "source_plan_sha256": "e6f797c4ca01ed422b80e928854469b9f8c7f7cc4215835bf91f9f7305425a00",
  "blueprint_sha256": "d5bfe9872b2497bea19b3aec7f4c93635f3444679e11856b9a5975c8a2a929da",
  "split_sha256": "c3e99db3facbca592b13009829280b7402ed3a0b38e5bc687f2d1f8f73f2c724",
  "manifest_sha256": "5fabd40123aaa8bb614bb812f2994c776967b9b04ec3bfe477f89c1dde614d13",
  "C_system_prompt_sha256": "81a5800500b3fafc23af4b7643e79a3d206c3ca6c80f6924514001ec85dc2a42",
  "K_system_prompt_sha256": "0935e2b7232715b623bb174f0a059387659f8d9bc7939804c8a372d8aa27ba71",
  "model_ids": {
    "gemini": "gemini-3.5-flash-lite",
    "haiku": "claude-haiku-5-5",
    "sonnet": "claude-sonnet-5-5"
  },
  "logical_stages": 180,
  "stage_counts": {"C": 60, "D": 60, "K": 60},
  "ood_locked": 11,
  "ledger_namespace_absent": true,
  "ground_truth_read": false,
  "scientific_release_frozen": false,
  "can_execute_api": false,
  "model_requests_sent": 0
}
```

Esecuzione Colab riferita dall'utente:
```text
Mounted at /content/drive
=== 1/4: INPUT GT-FREE ===
OK: split_market_v1.csv
OK: benchmark_inputs_market.csv
=== 2/4: CHECKOUT PINNATO ===
HEAD: 601dc7c2f971b919962ff190e6feb192c4dd237a
=== 3/4: AUDIT REALE DELLE 29 SORGENTI ===
=== 4/4: PREFLIGHT COMPLETATO — 0 API ===
```
Seconda cella di recupero ha ristampato il JSON precedente con
`json.loads`; `check=True` e assert su SHA Git, numero source,
180 stage e API disabilitate sono terminati senza eccezioni.

**Significato preciso**: preflight reale read-only su
`/content/drive/MyDrive/Tesi_OpenRCA/data/processed/split_market_v1.csv`
e `benchmark_inputs_market.csv`, 29 sorgenti del commit PINNATO;
RQ1 identity verified nel preflight; quattro casi discovery, cinque
harness e tre provider, D/C/K 60 ciascuno. Non esistono
in questo gate risultati RQ2-V2 live o una release autorizzata.
11 casi OOD rimangono locked. Nessun benchmark GT, scorer o
`Market.zip` letto da questo controllo.

**Non dichiarare release frozen**. Il commit 601dc7... e' il
commit effettivamente verificato; l'aggiornamento di documenti GitHub
dopo questo report fa avanzare il branch e non estende retroattivamente
il pin. Prima di generare una release, audit sul commit release finale,
lock Drive/FUSE e runtime/verifica spesa, approvazione specifica stage.

## Prossimo controllo suggerito

Google Colab: sonda scratch separata SOLO sotto
`/content/drive/MyDrive/` per semantica POSIX
`fcntl.flock(LOCK_EX|LOCK_NB)` fra processi indipendenti e
`os.open(O_CREAT|O_EXCL)` concorrente, senza mai modificare
`Tesi_OpenRCA`, RQ1, RQ2 V1 o namespace scientifico G4F.
Il test puo' provare esclusivita' tra processi nello stesso runtime
Colab, non sicurezza cross-VM o transazioni Drive garantite.
Se LOCK non affidabile -> FAIL CLOSED, progettare ledger locale con
sincronizzazione verificata, non usare il ledger su FUSE senza prova.
Nessun SDK, provider, modello, GT o API.

Stato: test offline G4F/G4G/G4H/G4I/G4J/G4K e G4A PASS,
145 metodi complessivi nelle sette suite recenti; questo report
AGGIUNGE una verifica ambiente reale NO-API, non una run RCA.
