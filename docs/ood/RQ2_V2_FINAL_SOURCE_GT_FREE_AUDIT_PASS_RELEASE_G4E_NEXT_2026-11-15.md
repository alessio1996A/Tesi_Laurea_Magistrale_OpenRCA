# RQ2-V2: audit finale sorgenti GT-free PASS; prossimo manifesto G4E draft

**Data:** 15 novembre 2026. Evidenza: output Colab integrale fornito dall'utente nel dialogo. E' un audit **prerelease**, non un'autorizzazione del manifesto, non un'esecuzione provider.

## PASS verificato, pin e ambiente

`=== RQ2-V2 FINAL GT-FREE SOURCE AUDIT ===`; `GIT PIN: OK`; `CHECKOUT CLEAN: OK`; `status: RQ2_V2_FINAL_SOURCE_PREFLIGHT_PASS_NO_API`; `FINAL SOURCE AUDIT: PASS — 0 API LLM`; `CHECKOUT TEMPORANEO: RIMOSSO`.

- **Checkout esatto attestato**: `f0b64a36b08c2ae5db424b544965db5362190377` (branch `feature/rq2-v2-runtime-optin-final-source-2026-11-15`). Questo e' il commit di codice verificato; eventuali nuovi commit SOLO documentali non modificano i sorgenti, ma una release deve pinning esplicito dell'esatto commit effettivamente sottoposto a convalida.
- **Inventario 30 sorgenti SHA256**: `709afa6158a6244a7dccda2f72c928dd7a12855211083001f7949474e3bea103`.
- **Blueprint SHA256**: `54a9df1b243a1ccc3a522958379bbbd1b26738c8276a31baea054946976f9bea`.
- **Dispatcher G4K source SHA256**: `afc37d35d74d2032e072bc689b485ca2efc15acc6d4a8233ab988d1c13dcb60a`.
- **Ledger G4L source SHA256**: `c1b9c388434639ade1330d26185c9aedba95214dee89f2fd285b66b7c4b11d43`.
- **K rubric SHA256**: `d8b969d33e2e042ab44121a9b6e089fa96a4aa2b8be03cb31b3edeede6f83f52`.
- **Piano SHA256**: `e6f797c4ca01ed422b80e928854469b9f8c7f7cc4215835bf91f9f7305425a00`.
- **Split SHA256**: `c3e99db3facbca592b13009829280b7402ed3a0b38e5bc687f2d1f8f73f2c724`.
- **Manifest SHA256**: `5fabd40123aaa8bb614bb812f2994c776967b9b04ec3bfe477f89c1dde614d13`.
- **C prompt SHA256**: `81a5800500b3fafc23af4b7643e79a3d206c3ca6c80f6924514001ec85dc2a42`.
- **K prompt SHA256**: `0935e2b7232715b623bb174f0a059387659f8d9bc7939804c8a372d8aa27ba71`.

## Sicurezza attestata

- `runtime_snapshot_verified=true`; pinned SDK: anthropic=2.6.0, google-genai=2.34.0, langchain-anthropic=1.7.7, langchain-core=1.7.1, langchain-google-genai=4.4.2, langgraph=1.2.18.
- `live_api_enabled=false`, `release_writer_enabled=false`, `can_execute_api=false`, `can_run_ood_test=false`, `ground_truth_read=false`, `ledger_namespace_absent=true`, `release_sha256=null`, `provider_requests_sent=0`, `scientific_claims_written=0`.
- `dossier_status=PRERELEASE_DOSSIER_REVIEW_ONLY_NO_AUTHORITY`.
- 180 stage logici pianificati: per Gemini, Sonnet, Haiku 20 D + 20 C + 20 K; 11 casi OOD Opzione B ancora LOCKED. Primo stage candidato: `rq2_v2_unified_five_harness_discovery_v0:cloudbed-1_q032:gemini:A0:D`.
- PyCharm 33/33 test G4K/G4L/opt-in riferiti PASS dall'utente senza log dettagliato, da distinguere dai dati numerici completi del Colab.

## Decisioni utente gia' registrate

- Budget operativo per tutta Opzione A: **USD 100.00**; non e' un hard cap garantito o consenso illimitato.
- Consenso procedurale a proseguire verso il **solo** pilot Gemini A0 D sul caso cloudbed-1_q032; NON verso gli altri 179 stage o 11 OOD.
- **Ancora nessun consenso sul contenuto/hash canonico del manifesto G4E**, che non esiste. Non costruire release_v1.json finché utente non approva esplicitamente SHA e approvazione esterna.

## Prossimo passaggio: release G4E in sola memoria

Non ripetere test PyCharm o il preflight Colab gia' PASS. Nel processo Python read-only:
1. Clone temporaneo pulito allo **SHA sorgenti auditato** `f0b64a36b08c2ae5db424b544965db5362190377`, verificare HEAD+clean, usare SDK pinned e split/manifest GT-free originali.
2. Opt-in env di release e live esattamente **assenti**. Ricostruire G4A source e G4B blueprint, G4D namespace assente, G4E contratto dei campi `REQUIRED_KEYS`.
3. Proporre manifesto con `approved_total_usd_limit="100.00"`, protocollo Opzione A completo, `ood_test_locked=true`, 30 SHA originali, commit f0b64, 6 runtime pinned. Il riferimento di approvazione deve riferirsi a una **decisione utente reale** ed essere esplicitamente confermato insieme al digest; non fabbricare approvazione di SHA prima del consenso.
4. Calcolare SHA256 con `release_digest` e mostrare ricevuta di **preview (non autorità)**, digest, id campagna, costo, commit e nessuna scrittura. Se si esegue `validate_future_release` con il digest calcolato nel medesimo processo, etichettare chiaramente il risultato come sola verifica strutturale, NON approvazione esterna.
5. Dopo nuova approvazione utente dell'esatto SHA/referenza, la fase create-only release G4L sarà un passo separato con controllo su Drive; le credenziali/provider non vanno toccati nel draft.

**Non aggiornare sorgenti RQ1 o RQ2, rubrica K, prompt, split, manifest, 11 OOD.** Gli hash riportati qui sono del commit f0b64; i commit documentali non estendono l'attestazione a un commit differente per una release, anche se i sorgenti restano uguali.
