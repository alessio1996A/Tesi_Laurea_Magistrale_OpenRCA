# Mappa del codice

Generata da `tools/refactoring/genera_mappa_codice.py` a partire dall'Appendice A del documento di consolidamento
(`docs/CONSOLIDAMENTO_SCIENTIFICO_E_OPERATIVO_2026-11-16.md`). Non modificare a mano: si rigenera con lo stesso comando.

## Come leggere questa mappa

- I moduli sono divisi in **gruppi** secondo il grafo degli import dai punti d'ingresso che hanno prodotto i risultati.
  "Fuori dal nucleo" significa "non necessario al codice finale", **non** "eliminabile": i percorsi compaiono nei record,
  negli addendum e negli hash, quindi nessun modulo viene spostato, rinominato o cancellato prima della consegna.
- **Protezione**: alcuni file sono verificati da un hash (SHA-256 del consolidamento, sez. 7.2; hash git dei sorgenti RQ1 in
  `evaluation/rq2_protocol_identity_preflight.py`). Cambiare anche un solo carattere, commenti compresi, fa fallire quei controlli:
  restano com'erano, anche se i loro commenti sono in inglese o in italiano misto.
- **Commenti**: "completo" = commenti e docstring in italiano e nessuna funzione senza docstring; "da fare" = c'e' ancora
  almeno un blocco probabilmente inglese o una funzione senza docstring (la lingua e' stimata con un'euristica).
  Le classi Pydantic e le funzioni `@tool` non hanno docstring di proposito: la docstring verrebbe inviata al modello.
- Verifica del refactoring: `python tools/refactoring/controlla_solo_commenti.py --base <riferimento git>` dimostra che, rispetto
  al riferimento, sono cambiati solo commenti e docstring (albero sintattico identico) e che nessun file protetto e' stato toccato.

## Riepilogo

| Gruppo | Moduli | Bloccati da hash | Commenti completi | Da fare |
|---|---:|---:|---:|---:|
| A. Nucleo del codice finale | 98 | 25 | 40 | 33 |
| B1. Campagne e audit RQ1 storici | 9 | 0 | 1 | 8 |
| B2. Audit e preflight in sola lettura | 12 | 0 | 0 | 12 |
| C1. Script manuali una tantum | 5 | 0 | 1 | 4 |
| C2. RQ2 pre-V5: ledger, dispatcher, pilot, sonde, prototipi | 32 | 0 | 3 | 29 |

## A. Nucleo del codice finale (da mantenere e documentare)

**Agente (grafi, prompt, tool)**

| Modulo | Righe | Scopo (prima riga della docstring) | Protezione | Commenti |
|---|---:|---|---|---|
| `agent/graph_engine.py` | 411 | Grafo LangGraph ReAct-style per A0 e varianti con harness senza planner. | hash git RQ1 | bloccato |
| `agent/model_factory.py` | 70 | Factory isolata dei provider LLM per OpenRCA. | hash git RQ1 | bloccato |
| `agent/prompts.py` | 170 | (nessuna docstring di modulo) | hash git RQ1 | bloccato |
| `agent/rq2_v2_graph_engine.py` | 183 | Esecutore diagnostico sperimentale RQ2-V2: sola provenance dei tool. | - | completo |
| `agent/tool_factory.py` | 207 | (nessuna docstring di modulo) | hash git RQ1 | bloccato |
| `agent/tools.py` | 918 | (nessuna docstring di modulo) | SHA-256 consolidamento + hash git RQ1 | bloccato |
| `agent/variant_names.py` | 103 | Nomenclatura delle varianti OpenRCA e lettura degli esperimenti storici. | - | completo |
| `agent/verify_graph.py` | 560 | Variante LangGraph A1_VERIFY: esplorazione, verifiche mirate, finale. | - | completo |

**Contratti di output**

| Modulo | Righe | Scopo (prima riga della docstring) | Protezione | Commenti |
|---|---:|---|---|---|
| `output/openrca_contract.py` | 193 | Contratto canonico di diagnosi RCA, indipendente dal provider LLM. | - | completo |
| `output/structured_finalizer.py` | 287 | Finalizzazione OpenRCA strutturata, indipendente dal provider. | - | completo |
| `output/v2_contract.py` | 210 | Contratto di output OpenRCA V2 — SOLO validazione, mai riparazione. | - | completo |
| `output/v2_task_contract.py` | 235 | Validazione OpenRCA V2.4 task-aware, SENZA lettura di etichette. | hash git RQ1 | bloccato |

**Harness (evidenze, regole, planner, verificatori)**

| Modulo | Righe | Scopo (prima riga della docstring) | Protezione | Commenti |
|---|---:|---|---|---|
| `harness/anomaly_detector.py` | 426 | Rilevatori deterministici di anomalie sulle serie temporali delle metriche (mediana e MAD). | - | completo |
| `harness/evidence_builder.py` | 803 | (nessuna docstring di modulo) | hash git RQ1 | bloccato |
| `harness/evidence_selector.py` | 387 | Annotazione della qualità delle evidenze A1-v2 (passo intermedio tra rilevatori e riepilogo). | - | completo |
| `harness/evidence_summarizer.py` | 536 | Riepilogo compatto delle evidenze annotate: aggregazione e selezione con un budget massimo. | - | completo |
| `harness/investigation_planner.py` | 294 | Pianificatore deterministico delle verifiche mirate prima della diagnosi. | - | completo |
| `harness/mesh_runtime_detector.py` | 1115 | Rilevatore preliminare di evidenze Mesh/Runtime per A1. | - | completo |
| `harness/metric_quality.py` | 109 | Controllo di qualità delle serie temporali (metriche) di OpenRCA. | - | completo |
| `harness/observational_verifier.py` | 236 | Primo gate osservativo per la verifica PAVE-inspired. | - | completo |
| `harness/preprocessor.py` | 123 | Statistiche descrittive delle metriche OpenRCA in una finestra temporale. | - | completo |
| `harness/rule_batch.py` | 239 | Adattatore delle otto regole diagnostiche deterministiche R01–R11. | - | completo |
| `harness/rules/_node_rule_common.py` | 199 | Rilevatore comune, deterministico e offline, di anomalie sulla telemetria dei NODI (OpenRCA Market). | - | completo |
| `harness/rules/rule_container_cpu.py` | 188 | R01 - ipotesi preliminare di 'container CPU load' (OpenRCA Market). | hash git RQ1 | bloccato |
| `harness/rules/rule_container_memory.py` | 253 | R02 - ipotesi esplorativa di 'container memory load' (OpenRCA Market). | - | completo |
| `harness/rules/rule_container_read_io.py` | 231 | R06 - candidato 'container read I/O load' per OpenRCA Market. | - | completo |
| `harness/rules/rule_node_cpu_load.py` | 31 | R07 - carico di CPU del nodo (classe candidata "node CPU load"). | - | completo |
| `harness/rules/rule_node_disk_space.py` | 28 | R11 - consumo di SPAZIO su disco del nodo (classe "node disk space consumption"), NON I/O di lettura/scrittur... | - | completo |
| `harness/rules/rule_node_memory.py` | 27 | R08 - consumo di memoria del nodo (classe candidata "node memory consumption"). | - | completo |
| `harness/rules/rule_node_read_io.py` | 64 | R09 - Consumo di I/O di lettura del disco di un nodo (classe "node disk read I/O consumption"). | - | completo |
| `harness/rules/rule_node_write_io.py` | 61 | R10 - Consumo di I/O di scrittura del disco di un nodo (classe "node disk write I/O consumption"). | - | completo |
| `harness/signal_catalog.py` | 522 | (nessuna docstring di modulo) | hash git RQ1 | bloccato |
| `harness/structural_patterns.py` | 125 | Raggruppamento di anomalie vicine nel tempo sullo stesso componente. | - | completo |
| `harness/structural_temporal_verifier.py` | 406 | Controlli strutturali e temporali sulle evidenze RCA (PAVE-inspired v1). | - | completo |
| `harness/topology.py` | 89 | Topologia nodo -> container ricavata dai nomi dei componenti ('cmdb_id') di OpenRCA. | - | completo |
| `harness/unified_report.py` | 887 | Report unificato delle evidenze: un unico elenco compatto, con un budget globale, da dare all'agente. | - | completo |

**RQ1 e EVALUATION20 (runner, preregistrazione, coorti, audit finestre, OOD)**

| Modulo | Righe | Scopo (prima riga della docstring) | Protezione | Commenti |
|---|---:|---|---|---|
| `evaluation/evaluation20_campaign.py` | 479 | Safe evaluation20 campaign runner (300 planned runs). | hash git RQ1 | bloccato |
| `evaluation/evaluation20_preflight.py` | 338 | OpenRCA Market: audit GT-free per 20 nuovi incidenti EVALUATION. | - | completo |
| `evaluation/evaluation20_preregister.py` | 266 | Preregistrazione create-only delle 300 run EVALUATION20, senza API. | hash git RQ1 | bloccato |
| `evaluation/experiment_config.py` | 218 | (nessuna docstring di modulo) | hash git RQ1 | bloccato |
| `evaluation/experiment_runner.py` | 1146 | (nessuna docstring di modulo) | hash git RQ1 | bloccato |
| `evaluation/ood_class_inventory.py` | 257 | Controlled label inventory for phase-2 OOD cases. Evaluation-only, NOT agent code. | SHA-256 consolidamento | bloccato |
| `evaluation/ood_holdout_preflight.py` | 170 | Inventario OOD preliminare, GT-free, in sola lettura. | SHA-256 consolidamento | bloccato |
| `evaluation/v2_case_window_audit.py` | 219 | Audit in sola lettura delle finestre degli esperimenti V1. | SHA-256 consolidamento | bloccato |
| `evaluation/v2_cohort_selector.py` | 453 | V2.5: proposta riproducibile di una NUOVA coorte GT-free, solo development. | - | completo |
| `evaluation/v2_preregister.py` | 267 | V2.6: prepara un piano preregistrato per 40 run, nessuna chiamata LLM. | - | completo |

**RQ2 K (esecutore, L1/L2, audit)**

| Modulo | Righe | Scopo (prima riga della docstring) | Protezione | Commenti |
|---|---:|---|---|---|
| `evaluation/rq2_k_catalog.py` | 270 | RQ2-K: catalogo dei KPI misurato sui SOLI incidenti discovery (sola lettura). | SHA-256 consolidamento | bloccato |
| `evaluation/rq2_k_l1_preflight.py` | 466 | RQ2-K: preflight L1 delle regole candidate (GT-FREE, solo lettura). | SHA-256 consolidamento | bloccato |
| `evaluation/rq2_k_l1_protocol.py` | 458 | RQ2-K: congelamento del protocollo L1/L2 e run L1 sui 4 incidenti di discovery. | SHA-256 consolidamento | bloccato |
| `evaluation/rq2_k_l2_execute.py` | 442 | RQ2-K L2a: esecuzione della regola congelata sui gruppi temporali dei sigillati, SENZA ground truth. | SHA-256 consolidamento | bloccato |
| `evaluation/rq2_k_l2_scoring.py` | 281 | RQ2-K L2b: valutazione CON ground truth delle decisioni L2a. Processo SEPARATO da L2a. | SHA-256 consolidamento | bloccato |
| `evaluation/rq2_k_records.py` | 93 | RQ2-K: lettura delle regole K dai record V5 (sola lettura, nessuna etichetta). | SHA-256 consolidamento | bloccato |
| `evaluation/rq2_k_rule_evaluation.py` | 228 | RQ2-K: valutazione CON riferimento di una regola K gia' eseguita (processo GT-only). | SHA-256 consolidamento | bloccato |
| `evaluation/rq2_k_rule_executor.py` | 302 | RQ2-K: esecutore deterministico delle regole candidate (GT-free). | SHA-256 consolidamento | bloccato |
| `evaluation/rq2_k_rule_inventory.py` | 108 | RQ2-K: inventario delle regole candidate rispetto al catalogo dei KPI (solo lettura). | - | completo |
| `evaluation/rq2_k_run_audit.py` | 175 | RQ2: audit di sola lettura del run V5 (registro delle decisioni, riga 10). | - | completo |
| `evaluation/rq2_k_run_integrity.py` | 381 | RQ2: verifica di integrita' e provenance dei record del run V5 (SOLA LETTURA). | - | completo |

**RQ2 V5 (run di discovery)**

| Modulo | Righe | Scopo (prima riga della docstring) | Protezione | Commenti |
|---|---:|---|---|---|
| `evaluation/rq2_v5_matrix_runner.py` | 706 | RQ2-V5: runner a matrice, magro e riprendibile (solo libreria standard). | - | completo |
| `evaluation/rq2_v5_response_normalization.py` | 203 | RQ2-V5.1: normalizzazione del formato della risposta, UGUALE per tutti i modelli. | - | completo |
| `evaluation/rq2_v5_retry.py` | 95 | RQ2-V5: politica di retry unica, dichiarata PRIMA del run scientifico. | - | completo |
| `evaluation/rq2_v5_run_cli.py` | 335 | RQ2-V5: riga di comando per Colab (check, run, summary). | - | completo |
| `evaluation/rq2_v5_stage_executor.py` | 349 | RQ2-V5: esecutore reale di D, C e K per il runner a matrice. | - | completo |

**RQ2 catena V2 (piano unificato, ledger, release)**

| Modulo | Righe | Scopo (prima riga della docstring) | Protezione | Commenti |
|---|---:|---|---|---|
| `evaluation/rq2_v2_ck_provider_transport_candidate.py` | 108 | Versioned RQ2 C/K transport CANDIDATE (NOT connected to scientific live). | - | da fare (EN 3, senza docstring 1) |
| `evaluation/rq2_v2_ck_text_extraction_candidate.py` | 62 | Candidate uniform C/K text extraction policy; OFFLINE, not wired to live. | - | da fare (EN 3, senza docstring 1) |
| `evaluation/rq2_v2_unified_discovery_plan.py` | 230 | Piano OFFLINE e NON eseguibile per RQ2-V2: 5 harness x 3 modelli. | - | da fare (EN 0, senza docstring 2) |
| `evaluation/rq2_v2_unified_live_stage_preflight.py` | 221 | G4H — source-bound preview di UN SOLO stage scientifico Opzione A. | - | completo |
| `evaluation/rq2_v2_unified_provenance_gate.py` | 131 | Gate OFFLINE per la provenance D nella RQ2-V2 comune ai cinque agenti. | - | completo |
| `evaluation/rq2_v2_unified_provider_result_adapter.py` | 251 | G4J: normalizza SOLO ricevute D/C/K verso il ledger RQ2-V2 unificato. | - | da fare (EN 0, senza docstring 5) |
| `evaluation/rq2_v2_unified_release_blueprint.py` | 212 | RQ2-V2 UNIFICATA — descrizione offline della futura release G4B. | - | da fare (EN 1, senza docstring 2) |
| `evaluation/rq2_v2_unified_release_preflight.py` | 209 | G4A RQ2-V2 unificata: preview source-bound GT-free, NON una release. | - | da fare (EN 0, senza docstring 2) |
| `evaluation/rq2_v2_unified_scientific_ledger.py` | 784 | RQ2-V2 Opzione A: ledger scientifico comune create-only, NO MODEL API. | - | da fare (EN 2, senza docstring 15) |
| `evaluation/rq2_v2_unified_scientific_ledger_preflight.py` | 189 | G4D: guardia READ-ONLY del FUTURO ledger scientifico RQ2-V2. | - | da fare (EN 0, senza docstring 3) |
| `evaluation/rq2_v2_unified_scientific_release_contract.py` | 204 | G4E RQ2 V2: contratto della FUTURA release scientifica, solo dati. | - | da fare (EN 0, senza docstring 3) |

**RQ2 catena V3 (piano, ponte D, ricevute)**

| Modulo | Righe | Scopo (prima riga della docstring) | Protezione | Commenti |
|---|---:|---|---|---|
| `evaluation/rq2_v3_ck_provenance_receipt_candidate.py` | 165 | Proposed successor-only C/K receipt contract with auditable text provenance. | - | da fare (EN 4, senza docstring 1) |
| `evaluation/rq2_v3_d_final_stream_candidate.py` | 163 | RQ2 V3 candidate: exact visible-text extraction for FINAL D responses. | - | da fare (EN 7, senza docstring 2) |
| `evaluation/rq2_v3_d_runner_capture_candidate.py` | 135 | V3 D runner instrumentation candidate, OFFLINE ONLY; no paid dispatch. | - | da fare (EN 3, senza docstring 6) |
| `evaluation/rq2_v3_scientific_receipt_adapter_candidate.py` | 346 | Proposed pure V3 D/C/K scientific receipt adapter (OFFLINE ONLY). | - | da fare (EN 5, senza docstring 5) |
| `evaluation/rq2_v3_unified_gtfree_discovery_plan.py` | 195 | Successor RQ2 V3 GT-free discovery plan; PRE-RELEASE, NO API/CLAIM. | - | da fare (EN 2, senza docstring 3) |

**RQ2 catena V4 (piano, contratti, ricevute)**

| Modulo | Righe | Scopo (prima riga della docstring) | Protezione | Commenti |
|---|---:|---|---|---|
| `evaluation/rq2_v4_d_task_aware_contract.py` | 182 | RQ2-V4: validazione D task-aware, GT-free, senza API né scritture. | - | da fare (EN 0, senza docstring 1) |
| `evaluation/rq2_v4_scientific_receipt_adapter_candidate.py` | 235 | RQ2-V4 scientific receipt adapter: D task-aware; C/K frozen semantics. | - | da fare (EN 3, senza docstring 3) |
| `evaluation/rq2_v4_unified_gtfree_discovery_plan.py` | 119 | Piano successore RQ2-V4 solo OFFLINE: nuova identita, nessuna API. | - | da fare (EN 0, senza docstring 2) |

**RQ2 moduli comuni (budget, contratti, bundle, probe, store)**

| Modulo | Righe | Scopo (prima riga della docstring) | Protezione | Commenti |
|---|---:|---|---|---|
| `evaluation/rq2_budget_preflight.py` | 245 | GT-free, offline and NON-AUTHORIZING RQ2 model/cost preflight. | - | da fare (EN 6, senza docstring 4) |
| `evaluation/rq2_ck_provider_transport.py` | 296 | Actual C/K provider path, HARD-BLOCKED until scientific protocol release. | - | da fare (EN 8, senza docstring 2) |
| `evaluation/rq2_discovery_claim_journal.py` | 252 | Offline-only durable, create-only claims against duplicate RQ2 calls. | - | da fare (EN 4, senza docstring 6) |
| `evaluation/rq2_discovery_stage_recorder.py` | 391 | Offline-only D/C/K discovery recording from caller-supplied outputs. | - | da fare (EN 9, senza docstring 7) |
| `evaluation/rq2_dryrun_plan.py` | 284 | RQ2 non-executable, GT-free stage-plan preview. | - | da fare (EN 6, senza docstring 4) |
| `evaluation/rq2_evidence_bundle.py` | 256 | Read-only RQ2 bundle of tool observations already captured by RQ1 runners. | - | da fare (EN 5, senza docstring 7) |
| `evaluation/rq2_kpi_formalizability_preflight.py` | 189 | GT-free offline-only KPI inventory and RQ2-K formalizability preflight. | - | da fare (EN 4, senza docstring 3) |
| `evaluation/rq2_model_factory.py` | 82 | Candidate RQ2-only model factory, with explicit pinned synchronous transport. | - | da fare (EN 4, senza docstring 0) |
| `evaluation/rq2_output_contracts.py` | 240 | Strict RQ2 JSON contracts for offline validation of LLM-produced C/K output. | - | da fare (EN 4, senza docstring 10) |
| `evaluation/rq2_probe_adapter.py` | 195 | OFFLINE-only assembly of RQ2 C (cause) and K (candidate rule) prompts. | - | da fare (EN 3, senza docstring 5) |
| `evaluation/rq2_protocol_identity_preflight.py` | 182 | Offline RQ2 pre-freeze fingerprints with RQ1 frozen-source parity. | - | da fare (EN 8, senza docstring 4) |
| `evaluation/rq2_provider_policy_source_audit.py` | 186 | RQ2 read-only provider retry/timeout *source* inventory, NOT network verification. | - | da fare (EN 5, senza docstring 4) |
| `evaluation/rq2_rule_group_scorer.py` | 189 | RQ2-C offline-only GROUP-LEVEL rule outcome scorer (proposal V0). | SHA-256 consolidamento | bloccato |
| `evaluation/rq2_sdk_retry_mock_probe.py` | 208 | RQ2: sandboxed SDK retry-behavior probe, no external HTTP, no model invocations. | - | da fare (EN 9, senza docstring 3) |
| `evaluation/rq2_stage_artifact_store.py` | 388 | RQ2 source-bound, create-only STAGE ARTIFACT storage (no execution). | - | da fare (EN 10, senza docstring 11) |
| `evaluation/rq2_stage_binding.py` | 261 | OFFLINE-only binding of RQ2 C/K prompt packages to draft workflow stages. | - | da fare (EN 6, senza docstring 5) |
| `evaluation/rq2_toolfree_fake_transport.py` | 231 | RQ2 C/K LangChain messages, executed ONLY against a strict fake model. | - | da fare (EN 7, senza docstring 6) |

## B1. Campagne e audit RQ1 storici (conservare: hanno prodotto risultati citabili)

| Modulo | Righe | Scopo (prima riga della docstring) | Protezione | Commenti |
|---|---:|---|---|---|
| `evaluation/claude_development_campaign.py` | 603 | Claude V3 content-block recovery: 80 runs (40 Sonnet + 40 Haiku), GT-free. | - | da fare (EN 1, senza docstring 14) |
| `evaluation/claude_development_freeze.py` | 98 | Freeze read-only validation of all 40 Claude runs for ONE model. | - | da fare (EN 1, senza docstring 3) |
| `evaluation/paired_cohort.py` | 180 | Pre-register an A1 vs A1_VERIFY development cohort without accessing GT. | - | da fare (EN 5, senza docstring 3) |
| `evaluation/paired_runner.py` | 418 | Safe paired-run orchestration for the frozen GT-free development cohort. | - | da fare (EN 12, senza docstring 4) |
| `evaluation/paired_st_cohort.py` | 181 | Pre-registra casi development nuovi per A1_VERIFY vs A1_VERIFY_ST. | - | da fare (EN 0, senza docstring 6) |
| `evaluation/paired_st_runner.py` | 429 | Safe paired-run orchestration for the frozen GT-free development cohort. | - | da fare (EN 12, senza docstring 4) |
| `evaluation/v2_campaign_runner.py` | 417 | V2.6: campagna di 40 run. DEFAULT: preflight offline in sola lettura. | - | da fare (EN 0, senza docstring 6) |
| `evaluation/v2_frozen_prediction_audit.py` | 344 | Audit V2 in sola lettura delle 32 risposte storiche congelate. | - | da fare (EN 0, senza docstring 3) |
| `harness/hypothesis_coverage_audit.py` | 236 | Audit offline della copertura investigativa dei candidati A1-R8. | - | completo |

## B2. Audit e preflight in sola lettura (conservare: documentano le decisioni di protocollo)

| Modulo | Righe | Scopo (prima riga della docstring) | Protezione | Commenti |
|---|---:|---|---|---|
| `evaluation/ood_dependency_sensitivity.py` | 162 | GT-controlled, read-only sensitivity audit for possible OOD incident dependencies. | - | da fare (EN 2, senza docstring 4) |
| `evaluation/ood_source_schema_audit.py` | 99 | Fase 2: inventario di SCHEMA delle sorgenti OpenRCA Market (solo header). | - | da fare (EN 0, senza docstring 1) |
| `evaluation/rq2_development_kpi_audit.py` | 308 | GT-free Market KPI presence audit on DEVELOPMENT windows only. | - | da fare (EN 7, senza docstring 5) |
| `evaluation/rq2_discovery_prereg_readiness.py` | 199 | REAL GT-free, READ-ONLY pre-registration readiness check for RQ2. | - | da fare (EN 3, senza docstring 4) |
| `evaluation/rq2_fault_type_eval_policy.py` | 200 | RQ2-A frozen-CANDIDATE class normalization and offline-only scoring. | - | da fare (EN 5, senza docstring 3) |
| `evaluation/rq2_historical_trajectory_audit.py` | 139 | Offline RQ2 compatibility audit for already-frozen V3 tool trajectories. | - | da fare (EN 8, senza docstring 1) |
| `evaluation/rq2_partition_preview.py` | 159 | OFFLINE EVALUATION-ONLY RQ2 allocation preview. Never import into agent. | - | da fare (EN 3, senza docstring 2) |
| `evaluation/rq2_partition_preview_v1.py` | 257 | RQ2 V1 DRAFT partition: group-safe, cloudbed-balanced, adjacency-aware. | - | da fare (EN 9, senza docstring 2) |
| `evaluation/rq2_q045_development_log_audit.py` | 270 | Read-only, GT-free audit of q045-style WARNING signals on DEVELOPMENT logs. | - | da fare (EN 9, senza docstring 1) |
| `evaluation/rq2_source_bound_d_preflight.py` | 224 | Read-only, GT-free RQ2 discovery D preflight on the ORIGINAL manifest. | - | da fare (EN 5, senza docstring 2) |
| `evaluation/rq2_v1_gemini_readonly_audit.py` | 207 | Audit di SOLA LETTURA degli stage Gemini discovery RQ2-V1. | - | da fare (EN 0, senza docstring 2) |
| `evaluation/rq2_v5_fence_audit_readonly.py` | 167 | Audit OFFLINE e in SOLA LETTURA dei due D Claude V4 (Sonnet, Haiku). | - | da fare (EN 0, senza docstring 4) |

## C1. Script manuali una tantum (candidati all'archivio dopo la consegna)

| Modulo | Righe | Scopo (prima riga della docstring) | Protezione | Commenti |
|---|---:|---|---|---|
| `evaluation/manual_offline_real_evidence_audit.py` | 142 | Audit di integrazione su telemetria OpenRCA REALE, senza API o ground truth. | - | completo |
| `evaluation/manual_paired_batch.py` | 74 | Preview frozen paired cohort; explicitly opt in to ONE API-funded pair. | - | da fare (EN 1, senza docstring 1) |
| `evaluation/manual_paired_st_batch.py` | 74 | Preview frozen paired cohort; explicitly opt in to ONE API-funded pair. | - | da fare (EN 1, senza docstring 1) |
| `evaluation/manual_preregister_dev.py` | 70 | Run-only preflight for the GT-free A1 vs A1_VERIFY development cohort. | - | da fare (EN 1, senza docstring 1) |
| `evaluation/manual_smoke_structured_gemini.py` | 59 | Smoke test manuale: UNA chiamata Gemini per verificare lo structured output. | - | da fare (EN 0, senza docstring 1) |

## C2. RQ2 pre-V5: ledger, dispatcher, pilot, sonde, prototipi (candidati all'archivio dopo la consegna)

| Modulo | Righe | Scopo (prima riga della docstring) | Protezione | Commenti |
|---|---:|---|---|---|
| `evaluation/rq2_discovery_d_provider_transport.py` | 174 | Live-capable RQ2 discovery D wrapper around the FROZEN RQ1 runner. | - | da fare (EN 8, senza docstring 0) |
| `evaluation/rq2_fake_discovery_driver.py` | 191 | OFFLINE fake-provider rehearsal of the *existing* RQ2 stage machinery. | - | da fare (EN 9, senza docstring 4) |
| `evaluation/rq2_langchain_bridge_source_trace.py` | 155 | RQ2 pre-freeze: inspect exact installed LangChain/SDK bridge SOURCE only. | - | da fare (EN 5, senza docstring 1) |
| `evaluation/rq2_langchain_fake_http_invoke.py` | 232 | RQ2 prefreeze FINAL targeted offline invoke: real LangChain+SDK, fake HTTP 503. | - | da fare (EN 6, senza docstring 7) |
| `evaluation/rq2_langchain_parameter_mock_probe.py` | 198 | Offline RQ2 LangChain-to-SDK configuration forwarding probe. | - | da fare (EN 7, senza docstring 3) |
| `evaluation/rq2_mock_journal.py` | 327 | RQ2 *mock-only* create-only journal for fail-closed workflow tests. | - | da fare (EN 7, senza docstring 9) |
| `evaluation/rq2_mock_pipeline_integration.py` | 176 | RQ2 D->C->K offline MOCK integration using existing validated components. | - | da fare (EN 5, senza docstring 0) |
| `evaluation/rq2_q045_warning_detector_synthetic.py` | 165 | Pure synthetic-only prototype for one *unverified* Gemini RQ2-K candidate. | - | da fare (EN 3, senza docstring 0) |
| `evaluation/rq2_v2_artifact_store.py` | 354 | Archivio RQ2-V2 separato, create-only, SOLO per prove sintetiche offline. | - | da fare (EN 0, senza docstring 11) |
| `evaluation/rq2_v2_claim_journal.py` | 208 | Journal indipendente RQ2-V2, create-only e SOLO per fixture sintetiche. | - | da fare (EN 0, senza docstring 6) |
| `evaluation/rq2_v2_isolation_policy.py` | 101 | Bozza RQ2-V2: verifica OFFLINE di identita' e destinazioni disgiunte. | - | da fare (EN 0, senza docstring 1) |
| `evaluation/rq2_v2_k_quality_rubric.py` | 199 | Rubrica K preregistrata RQ2-V2, SOLO analisi offline e GT-free. | - | da fare (EN 1, senza docstring 1) |
| `evaluation/rq2_v2_sonnet_c_contentblocks_v2.py` | 510 | RQ2 V2 — C Content Blocks V2: protocollo tecnico successore sul discovery q050. | - | da fare (EN 0, senza docstring 9) |
| `evaluation/rq2_v2_sonnet_c_sourcebound.py` | 460 | RQ2 V2 — una nuova C reale, figlia della D Sonnet q050 già congelata. | - | da fare (EN 0, senza docstring 9) |
| `evaluation/rq2_v2_sonnet_k_single_live.py` | 400 | RQ2 V2 — una sola K Sonnet reale, da D e C congelate e verificate. | - | da fare (EN 0, senza docstring 7) |
| `evaluation/rq2_v2_sonnet_k_sourcebound_preview.py` | 200 | RQ2 V2 Sonnet — preflight READ-ONLY per K, da D e C ContentBlocks V2. | - | completo |
| `evaluation/rq2_v2_sonnet_pilot_driver.py` | 202 | Entrypoint isolato per una SOLA D Sonnet V2 sul discovery q050. | - | da fare (EN 0, senza docstring 8) |
| `evaluation/rq2_v2_sonnet_pilot_ledger.py` | 437 | Ledger scientifico V2 per UN solo pilot Sonnet D reale, separato da V1. | - | da fare (EN 0, senza docstring 15) |
| `evaluation/rq2_v2_unified_dispatcher_offline.py` | 328 | G4G: orchestratore D→C→K con vero ledger scientifico, SOLO FAKE. | - | da fare (EN 0, senza docstring 9) |
| `evaluation/rq2_v2_unified_live_dispatcher.py` | 285 | G4K — dispatcher RQ2-V2 unificato, LIVE disabilitato di default. | - | da fare (EN 0, senza docstring 4) |
| `evaluation/rq2_v2_unified_single_stage_dispatcher.py` | 298 | G4I: dispatcher unico RQ2-V2 per UN SOLO stage, per ora FAKE-ONLY. | - | da fare (EN 0, senza docstring 4) |
| `evaluation/rq2_v2_unified_synthetic_journal.py` | 499 | Journal UNIFICATO G3 (5 harness x 3 modelli), SOLO fixture sintetiche. | - | da fare (EN 0, senza docstring 13) |
| `evaluation/rq2_v3_offline_provenance_journal_prototype.py` | 303 | ISOLATED OFFLINE-ONLY journal prototype for candidate C/K provenance. | - | da fare (EN 3, senza docstring 12) |
| `evaluation/rq2_v3_scientific_ledger.py` | 560 | RQ2-V3 independent source-bound D/C/K ledger; NO PROVIDER DISPATCH. | - | da fare (EN 7, senza docstring 11) |
| `evaluation/rq2_v3_scientific_live_stage_preflight.py` | 480 | RQ2-V3 runtime: pure preview plus scoped synthetic/Drive live gate. | - | da fare (EN 14, senza docstring 1) |
| `evaluation/rq2_v3_scientific_single_stage_dispatcher.py` | 373 | RQ2-V3 single discovery stage dispatcher, default HARD DISABLED. | - | da fare (EN 11, senza docstring 1) |
| `evaluation/rq2_v3_scientific_source_inventory.py` | 273 | Read-only RQ2-V3 source inventory proposal; NOT a scientific release. | - | da fare (EN 8, senza docstring 5) |
| `evaluation/rq2_v3_scientific_source_release_gate.py` | 295 | RQ2-V3 strict GT-free scientific source/release gate: NO API, NO CLAIM. | - | da fare (EN 5, senza docstring 1) |
| `evaluation/rq2_v4_scientific_ledger.py` | 562 | RQ2-V4 independent source-bound D/C/K ledger; NO PROVIDER DISPATCH. | - | da fare (EN 7, senza docstring 11) |
| `evaluation/rq2_v4_scientific_single_stage_dispatcher.py` | 374 | RQ2-V4 single discovery stage dispatcher, default HARD DISABLED. | - | da fare (EN 11, senza docstring 1) |
| `evaluation/rq2_v4_scientific_source_inventory.py` | 134 | Inventario sorgenti RQ2-V4 GT-free e immutabile, solo read-only. | - | completo |
| `evaluation/rq2_v4_scientific_source_release_gate.py` | 286 | Gate RQ2-V4 per source, release e runtime: NO MODEL API / NO CLAIM. | - | completo |
