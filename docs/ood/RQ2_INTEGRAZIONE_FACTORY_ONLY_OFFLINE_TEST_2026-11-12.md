# RQ2 — Integrazione factory provider dedicata e prova offline, senza API

**12/11/2026 · Stato: codice candidato predisposto, suite aggiornate NON
ancora eseguite dall'utente. Nessuna API live autorizzata.**

## Successo precedente attestato

Colab sul commit `7019020364dfae6ae649d9620ffb4948e70a2f71`:
`Ran 8 tests in 0.004s — OK`,
`SYNC_FAKE_HTTP_503_INVOKE_VERIFIED_AS_TESTED_NOT_RELEASED`.
Con credenziali letterali sintetiche e MockTransport HTTP503,
`CK_tool_free` e `D_bound_tools` producono ciascuno 1 send HTTP
mockato per provider (Google e Anthropic). `external_provider_requests=0`.
NO evidenza su timeout sotto stallo reale o su async/streaming.

## Nuovo codice candidato solo RQ2

- `src/evaluation/rq2_model_factory.py` contiene
  `crea_modello_rq2`, con provider+modelli whitelist,
  pacchetti pinned Colab, 4 digest esatti delle librerie:
  Gemini `max_retries=1` (1 tentativo totale),
  Claude `max_retries=0`, entrambi `timeout=300.0`,
  Claude `max_tokens=4096`.
- `src/evaluation/rq2_discovery_d_provider_transport.py` chiama
  `run_experiment(config, llm=crea_modello_rq2(...),
  verbose=False, salva=False)` dopo verifica del release e claim;
  **runner originale RQ1 invariato**.
- `src/evaluation/rq2_ck_provider_transport.py` usa
  la stessa factory RQ2 via alias locale, dopo release e claim;
  nessun `bind_tools` nei C/K, una sola `invoke` sync.
- `src/tests/test_rq2_model_factory.py`: 10 test stdlib e SDK finti;
  `test_rq2_discovery_d_provider_transport.py`: 12 test synthetic
  aggiornati per il parametro `llm`;
  `test_rq2_ck_provider_transport.py`: test mock preesistenti
  (inclusi error path, consumo token, release e claim invariati).

L'iniezione del modello cambia **solo il trasporto** rispetto a RQ1:
l'agent D continua ad usare lo stesso `run_experiment` e gli stessi
tool e prompt. Non dichiarare parità dei **default provider** tra
esperimenti RQ1 storici e RQ2: nella RQ2 timeout/retry sono espliciti.

`RELEASE_SHA256=None` e
`PLAN_STATUS="DRAFT_NOT_EXECUTABLE"` restano invariati.
Un fallimento o un drift nel runtime non consente fallback alla factory
originale RQ1. Le prime API a pagamento rimangono subordinate
a preregistrazione, hash release firmato e consenso esplicito.

## Un solo giro PyCharm: test non-live

Dalla root del progetto, dopo aver verificato che `git status --short`
sia pulito:

```powershell
git status --short
git pull --ff-only origin feature/ood-knowledge-transfer-audit-2026-11-10
$env:PYTHONPATH="src"

python -m unittest discover -s src/tests -p "test_rq2_model_factory.py" -v
python -m unittest discover -s src/tests -p "test_rq2_discovery_d_provider_transport.py" -v
python -m unittest discover -s src/tests -p "test_rq2_ck_provider_transport.py" -v
```

Non fare una nuova installazione SDK Anthropic in PyCharm soltanto per
questo test: le suite usano oggetti finti e non invocano provider.
In caso di `FAIL` o `ERROR`, riportare traceback e non procedere
alla firma. Se `OK`, inviare l'esito delle tre suite. Nessun Colab
necessario per questo primo passaggio: il vero runtime pinned sarà
ricontrollato **prima** del release scientifico.

## Decisioni scientifiche da chiudere dopo test verdi

1. Versione esatta/commit e SHA factory RQ2, policy di retry/timeout,
   e durata richiesta; **300s è un candidato**, non ancora scientificamente
   approvato né un timeout dell'intero stage.
2. Scoring `predicted_fault_type`: mapping alias deterministico e
   denominatori fissati prima di esaminare le risposte OOD.
3. Catalogo KPI: formalizzabilità tecnica e fisica solo se verificata
   su sorgenti consentiti; altrimenti `not_formalizable`.
4. Audit indipendente della partizione 4 discovery/11 test già
   selezionata ex ante; primario dimostrativo `A1_8R + Sonnet`
   da fissare in preregistrazione prima di osservare K.
5. Firma release discovery create-only e hash pin, test OOD
   ancora chiusi. Poi singola run D approvata.
6. In parallelo avviare capitoli della tesi RQ1 / architettura,
   per consegna 1 dicembre 2026.
