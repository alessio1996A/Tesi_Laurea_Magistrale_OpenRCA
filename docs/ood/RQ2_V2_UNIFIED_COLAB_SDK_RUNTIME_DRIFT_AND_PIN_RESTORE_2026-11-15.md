# RQ2-V2 unificata — Colab SDK snapshot drift rilevato correttamente (2026-11-15)

## Evidenza utente, audit senza chiamate API

Il preflight sulle **29 sorgenti reali GT-free**, commit
`601dc7c2f971b919962ff190e6feb192c4dd237a`, ed il controllo
`fcntl.flock` + `O_EXCL` su scratch MyDrive sono già PASS.
Il controllo successivo `rq2_provider_policy_source_audit.preview_provider_policy`
nel nuovo runtime Colab Python **3.13.18** ha prodotto:
```text
status: RQ2_SDK_RUNTIME_SOURCE_AUDIT_NO_API
runtime_snapshot_ready: false
frozen_rq1_factory_unchanged: true
can_execute_api: false
model_requests_sent: 0
```

Snapshot SDK osservato senza target di pacchetti RQ2 dedicato:
| Pacchetto | Richiesto dal codice RQ2 (frozen) | Osservato |
|---|---|---|
| langchain-core | 1.7.1 | 1.7.4 |
| langgraph | 1.2.18 | 1.2.19 |
| langchain-anthropic | 1.7.7 | absent |
| langchain-google-genai | 4.4.2 | absent |
| anthropic | 2.6.0 | absent |
| google-genai | 2.34.0 | 2.12.1 |

SHA reale osservato per `google-genai` = `d0209bc9b335c6e8c440ed0a6f3b46af367785a4e5743aedc51b46e395e5e205`,
NON il previsto `b179b80a126a35c98b98aeefa701950304c38c8a1e117136a2270a0901fd93e4`.
Le altre tre SHA provider erano null (file non presenti).
Tutti e sei `versions_match` e tutti e quattro
`source_hashes_match` = false.

**Diagnosi:** la sessione Colab appena riconnessa sta usando
l'ambiente Python **predefinito**, non il target isolato di
dipendenze RQ2 fissate e verificate nelle sessioni precedenti.
**Non è deriva delle sorgenti RQ1, split, manifest o del benchmark.**
Il valore `frozen_rq1_factory_unchanged=true` lo conferma.
La factory RQ2 `assert_exact_runtime_snapshot()` rifiuta
correttamente la costruzione del provider in questo runtime:
**non iniziare il pilot, non aggiornare globalmente Colab**.

## Ripristino proposto, ancora DA ESEGUIRE dall'utente

Riutilizzare l'approccio già verificato nel documento
`RQ2_COLAB_PREFREEZE_REALE_SOLO_LETTURA_2026-11-12.md`:
`pip install --target /content/rq2_v2_pinned_sdk_py313`
esclusivamente sul filesystem temporaneo Colab `/content`,
con gli stessi pin del precedente ambiente RQ2:
```text
langchain==1.4.7
langchain-core==1.7.1
langgraph==1.2.18
langchain-google-genai==4.4.2
langchain-anthropic==1.7.7
google-genai==2.34.0
anthropic==2.6.0
google-auth==2.56.0
pandas, networkx, python-dotenv (requisiti storici non pin)
```

**Non riciclare il release V1** o alterare gli hash attesi.
Ripetere l'audit read-only in **un sottoprocesso fresco** con
`PYTHONPATH=/content/rq2_v2_pinned_sdk_py313:/content/Tesi_OpenRCA_RQ2_Unified_Preflight/src`.
Il processo iniziale Colab mantiene le librerie globali: l'esito
valido è quello del subprocess con percorso isolato effettivamente
iniettato nel runtime, non l'insieme globale.

Gate richiesti prima di futuri mock / pilot:
- 6/6 versioni esatte,
- 4/4 SHA dei sorgenti provider esatti e
  `original_factory_unchanged=true`,
- `api_calls_executed=0` e permessi discovery/OOD ancora false.
Se fallisce, STOP e conservare log pip/audit senza cambiare
versioni o SHA per far apparire un PASS.

Questo ripristino non è un'operazione LLM:
l'installazione ha accesso a PyPI, ma **nessuna** chiamata ai
modelli Google/Anthropic. Non scrivere nuovi risultati su Drive;
nessuna release live, claim, scorer o GT.

**Stato campagna**: 0/180 stage API reali, 11 OOD locked;
G4K 18/18 PASS offline, G4A 19/19 PASS, preflight reale
29 sorgenti PASS e scratch Drive lock PASS sono separati e invariati.
