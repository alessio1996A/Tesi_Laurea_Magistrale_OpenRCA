# RQ2 — Audit in sola lettura della configurazione provider (12 novembre 2026)

**Stato:** codice predisposto su branch RQ2; **7 test nuovi NON ancora attestati da PyCharm**. RQ1 congelata non modificata; niente release, niente API, niente test OOD.

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

**Attesi 7 metodi di test; esito da confermare dal log reale dell'utente.**
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
