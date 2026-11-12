# RQ2 — Audit in sola lettura della configurazione provider (12 novembre 2026)

**Stato:** 7/7 test nuovi **superati in PyCharm** (`0.102s`) **e in Colab** (`0.026s`), entrambi attestati dall'utente il 12 novembre 2026. Runtime Colab completo con sei versioni coincidenti e SHA dei quattro sorgenti provider acquisiti. RQ1 congelata non modificata; niente release, niente API, niente test OOD.

## Motivazione e problema aperto

Il preflight originale GT-free del 12 novembre è stato superato e archiviato in
`RQ2_PREFLIGHT_GT_FREE_REALE_VERIFICATO_2026-11-12.md`.
Tuttavia quel preflight attestava **false** entrambe le proprietà
`effective_Google_SDK_retry_timeout_verified` e
`effective_Anthropic_SDK_retry_timeout_verified`. Non si può firmare una
politica `NO_AUTOMATIC_RETRY` basandosi sul fatto che il wrapper RQ2
chiami `invoke` una sola volta: il trasporto sottostante potrebbe ritentare.

Da `src/agent/model_factory.py` frozen RQ1 (Git blob
`05308d5740763db0444556dcb7330d8fb4c308ec`):
- Claude esplicita `max_retries=0` e `max_tokens=4096`, ma non timeout.
- Gemini è istanziato con il solo `model=model_name`, quindi non esplicita
  né retry né timeout: **non dedurre** il comportamento effettivo del
  client Google o il conteggio dei tentativi.
- Per Gemini è necessario distinguere semantiche `max_retries` del
  wrapper e `HttpRetryOptions.attempts` dell'SDK, e i percorsi
  streaming/non-streaming, prima di fissare una politica per le chiamate.
  Verificare sul codice delle **versioni osservate in Colab**, non su
  documentazione generica o su una branch di libreria più recente.

Fonti da verificare contro gli esatti package installati:
- https://github.com/langchain-ai/langchain-google/issues/1843
- https://github.com/langchain-ai/langchain-google/issues/1652
- https://platform.claude.com/docs/en/api/sdks/python

## Nuova CLI di inventario NON eseguibile

`src/evaluation/rq2_provider_policy_source_audit.py`:
- analizza con AST soltanto le keyword dichiarate nella factory RQ1;
- conferma il Git blob immutato RQ1 o segnala drift;
- legge **solo** la metadata/versione e il digest SHA-256 dei file sorgente
  predefiniti delle dipendenze già installate; non importa SDK, non
  istanzia client e non stampa segreti o contenuti dei pacchetti;
- conserva status `SOURCE_EVIDENCE_ONLY_EFFECTIVE_RETRIES_TIMEOUTS_UNVERIFIED`;
- restituisce sempre `can_execute_D/CK/test=false`, release non firmato,
  chiamate API zero, e flag retry/timeout **non verificati**.

Questa CLI è solo un inventario per stabilire precisamente quali sorgenti
e versioni esaminare; **non è** una prova dinamica di comportamento HTTP.
Una prova dinamica valida richiederà trasporto fake con HTTP bloccato
dall'esterno, controllo dei tentativi e dei timeout, senza credenziali.

### PyCharm / PowerShell, da root del repository

```powershell
git status --short
git pull --ff-only origin feature/ood-knowledge-transfer-audit-2026-11-10
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_provider_policy_source_audit.py" -v
python -m evaluation.rq2_provider_policy_source_audit --repo-dir .
```

**Verificati 7/7 metodi in PyCharm, `Ran 7 tests in 0.102s — OK`, output condiviso dall'utente.**
Riportare il JSON della CLI come prodotto del computer dove viene eseguita.
Non interpretare l'eventuale differenza tra PyCharm Windows e Colab Linux
come fallimento scientifico automatico: serve lo snapshot anche sul runtime
effettivo di esecuzione prima del freeze. Non serve alcuna API key.

## Gate successivi

1. Registrare il risultato dei 7 test su PyCharm e le versioni/digest osservati.
2. Verificare offline il codice sorgente delle versioni esatte; provare con
   trasporto completamente finto le richieste Google/Anthropic e i parametri
   retry/timeout per i percorsi D/C/K (senza implementare nuovi agenti).
3. Definire una soluzione **RQ2-only** motivata e riproducibile se i default
   di Gemini non soddisfano la policy; non modificare RQ1 frozen né affermare
   parità di trasporto se si cambia il comportamento.
4. Solo dopo le restanti decisioni scientifiche preregistrate, firmare il
   release create-only. Gli 11 casi test restano preclusi fino al freeze K.

## Risultato reale PyCharm Windows — fornito dall'utente il 12/11/2026

CLI `rq2_provider_policy_source_audit_v0`, eseguita nella `.venv` locale,
Python **3.12.10**; `status=SOURCE_EVIDENCE_ONLY_EFFECTIVE_RETRIES_TIMEOUTS_UNVERIFIED`.

- `factory_git_blob_sha1=05308d5740763db0444556dcb7330d8fb4c308ec`,
  `frozen_rq1_factory_blob_match=true`.
- RQ1 Anthropic: `max_retries=0` dichiarato esplicitamente;
  nessun timeout dichiarato. Gemini: nessuno dei due dichiarato.
- `langchain-core=1.7.0`, `langgraph=1.2.18`,
  `langchain-google-genai=4.4.2`, `google-genai=2.33.0`;
  `anthropic=null`, `langchain-anthropic=null` perché **non installati
  nella .venv locale esaminata**.
- SHA-256 file `langchain_google_genai/chat_models.py`:
  `589106719f2038805a27ddd0c44c23d5e4a4486ea0d7116b38a83d37722ac27f`.
- SHA-256 file `google/genai/_api_client.py`:
  `26ea3189d3ba09bbf16208d2a46a9846bd19bc7c478ae9d61bc479a90dd831fb`.
- `matches_previous_colab_versions=false`: **coerente con la differenza
  d'ambiente** rispetto al preflight Colab del 12/11:
  Python 3.13.18, `langchain-core=1.7.1`,
  `langgraph=1.2.18`, `langchain-anthropic=1.7.7`,
  `langchain-google-genai=4.4.2`, `anthropic=2.6.0`,
  `google-genai=2.34.0`.
- Nessuna chiamata API, nessun accesso a GT, Market o predizioni;
  `can_execute_D=false`, `can_execute_CK=false`,
  `can_execute_test=false`.

**Interpretazione:** il test PyCharm dimostra il funzionamento dell'audit e
la provenienza della factory RQ1, **non** dimostra la policy effettiva di rete
su Colab. Evitare di modificare la `.venv` Windows soltanto per rendere i
numeri uguali: il runtime scientifico candidato è quello Colab isolato.

**Prossima azione:** eseguire solo l'inventario sorgenti sul runtime Colab
con le dipendenze già isolate, usando la cella in
`RQ2_COLAB_SDK_POLICY_SOURCE_AUDIT_2026-11-12.md`.
Prima di qualunque release servono audit del trasporto su SDK versionati
con finti client HTTP, policy di timeout/retry documentata, e gate scientifici.

## Evidenza reale Colab — audit SHA SDK (12/11/2026)

**Commit eseguito dall'utente:** `9c7b31f5dbcaa018dd52bad473f675dcda71d64a`.
**Test:** `Ran 7 tests in 0.026s — OK`.

- Python **3.13.18**; `matches_previous_colab_versions=true`.
- `langchain-core=1.7.1`; `langgraph=1.2.18`;
  `langchain-google-genai=4.4.2`; `google-genai=2.34.0`;
  `langchain-anthropic=1.7.7`; `anthropic=2.6.0`.
- SHA `langchain_google_genai/chat_models.py`:
  `589106719f2038805a27ddd0c44c23d5e4a4486ea0d7116b38a83d37722ac27f`.
- SHA `google/genai/_api_client.py`:
  `b179b80a126a35c98b98aeefa701950304c38c8a1e117136a2270a0901fd93e4`.
- SHA `langchain_anthropic/chat_models.py`:
  `c55a0cb8fed75b3d310dbddf03a455f95c3c1d47aab650317bf3c9e4bab62544`.
- SHA `anthropic/_base_client.py`:
  `a42ef507300287261fe0b215023672a97f8a9b01216a135d614bbede72fff680`.
- Factory RQ1 blob `05308d5740763db0444556dcb7330d8fb4c308ec`.
- `api_calls_executed=0`; `read_ground_truth=false`;
  `read_market=false`; `read_predictions=false`; `files_written=false`.
- `effective_google_sdk_retry_timeout_verified=false`,
  `effective_anthropic_sdk_retry_timeout_verified=false`;
  D/C/K/test sempre bloccati, release non firmato.

**Decisione:** identificità *di versioni e file sorgente* confermata nel
runtime Colab. Non confondere questo con prove di retry/timeout effettivi.
Prossimo test separato: `rq2_sdk_retry_mock_probe.py`, solo trasporti
finti e callback Python in memoria, con verifica fail-closed dei quattro SHA.
Il comportamento di LangChain e i timeout di rete rimangono altri gate.
