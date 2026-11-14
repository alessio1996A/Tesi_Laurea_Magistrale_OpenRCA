# RQ2-V2 unificata — Report GT-free reale completo + G4E 18/18 PASS

Data: 14 novembre 2026. Fonte dei dati: JSON Colab e output unittest condivisi dall'utente. Questo documento è un riscontro **del preflight**, non una release scientifica firmata.

## PyCharm G4E
```text
Ran 18 tests in 0.651s

OK
```
Tutti e 18 i metodi della suite `test_rq2_v2_unified_scientific_release_contract_offline.py` sono PASS **con fixture**, NON equivalenti a una reale autorizzazione alle API.

## Colab G4C source-bound reale — valori riportati integralmente

```json
{
  "C_system_prompt_sha256": "81a5800500b3fafc23af4b7643e79a3d206c3ca6c80f6924514001ec85dc2a42",
  "K_system_prompt_sha256": "0935e2b7232715b623bb174f0a059387659f8d9bc7939804c8a372d8aa27ba71",
  "blueprint_sha256": "a2874e9771eb50899afd15d55cecf239493f44077e16e937b5276f8a07e8fb61",
  "blueprint_status": "DRAFT_ALL_EXECUTION_BLOCKED_NO_API",
  "can_execute_api": false,
  "can_run_ood_test": false,
  "discovery_cases": [
    "cloudbed-1_q032", "cloudbed-1_q050", "cloudbed-2_q026", "cloudbed-2_q045"
  ],
  "ground_truth_read": false,
  "harnesses": ["A0", "A1", "A1_8R", "A1_8R_Planning", "A1_PAVE"],
  "manifest_sha256": "5fabd40123aaa8bb614bb812f2994c776967b9b04ec3bfe477f89c1dde614d13",
  "max_graph_invocations_candidate_not_HTTP": 492,
  "model_ids": {
    "gemini": "gemini-3.5-flash-lite",
    "haiku": "claude-haiku-5-5",
    "sonnet": "claude-sonnet-5-5"
  },
  "model_requests_sent": 0,
  "ood_test_cases_locked": 11,
  "scientific_artifacts_written": 0,
  "scientific_release_frozen": false,
  "source_file_count": 15,
  "source_plan_preview_sha256": "e6f797c4ca01ed422b80e928854469b9f8c7f7cc4215835bf91f9f7305425a00",
  "source_status": "OFFLINE_SOURCE_BOUND_NO_RELEASE_NO_API",
  "split_sha256": "c3e99db3facbca592b13009829280b7402ed3a0b38e5bc687f2d1f8f73f2c724",
  "stage_counts": {"C": 60, "D": 60, "K": 60},
  "status": "RQ2_V2_UNIFIED_REAL_GT_FREE_SOURCE_PREFLIGHT_OK_NO_API"
}
```

Il checkout del test era `33d5d8b28494d5bf41168d0a709854aa3134ea6a`; il branch di sviluppo evolve indipendentemente dopo questa lettura. Le impronte G4C identificano **QUELLA** versione del piano e dei sorgenti. Le fixture G4E non attestano il comportamento effettivo dei trasporti LLM né la disponibilità remota dei modelli.

## Verdetto metodologico

- G4C: PASS read-only su split e manifest reali GT-free, provenienza RQ1, pianificazione e prompt C/K; nessun provider chiamato.
- G4D: 17 test effettivamente PASS, 2 skipped per symlink Windows.
- G4E: 18/18 test PASS con dati sintetici, **reale approvazione API ancora assente**.
- RQ2 V2 discovery: **0/180 stage logici della nuova campagna realizzati via API**.
- OOD: 11 test ancora locked, Opzione B non avviata.
- Resta da implementare il ledger operativo create-only per risultati reali, dispatcher unico D/C/K, metering e garanzie dei trasporti, release congelata e autorizzazione esplicita ad uno o più stage pagati.

**Non riciclare** le SHA/approval fixture nella release reale. Dopo aver integrato un nuovo ledger/dispatcher nel codice, la nuova HEAD dovrà essere fissata e il source inventory rigenerato/esteso, invece di chiamare il G4C precedente un freeze del codice che ancora non esisteva.
