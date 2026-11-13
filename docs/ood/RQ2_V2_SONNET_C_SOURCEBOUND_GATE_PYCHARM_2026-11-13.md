# RQ2 V2 — C Sonnet q050, sviluppo source-bound, gate PyCharm ancora da eseguire

**Data:** 2026-11-13. **Stato:** `CODE_READY_FOR_OFFLINE_TEST`, `NO_C_RELEASE`, `NO_NEW_API`, `OOD_LOCKED`.

## Risultati antecedenti osservati

La D reale q050 / sonnet / A1 sul commit `bf2b0a0a67977a65c79d47ada4b07e825eaf8dff` e' `RECORDED_COMPLETE`, con 8 tool call e 8 tool result, 8 ID nativi associati, 7 richieste LLM, 139155 token osservati, $0.301102 stimati, non fattura. Gli hash:
- D release: `c07e0aaa19b6cc1826e532c7da89e856c68e73975be84f572a727c09c7580813`
- D record: `521ed45b3dfefe6fd6c21427ca1c4ac0d03edbb1608bf80cbc424109c9f1a009`
- D bundle: `f63f1f0fd744497acc92814d8aabf80fb30cb08d8e5244ec62501d29052154d6`.

C readiness verificata dall'utente su Drive in sola lettura:
```text
STATUS: SONNET_V2_C_READINESS_OK
EVIDENCE_COUNT: 8
EVIDENCE_TRUNCATED: 3
C_PACKAGE_SHA256: 49422ee1f91909514acc3cdf5868aa5c4e73990392804fe7b1fa8dec950e333f
C_SYSTEM_PROMPT_SHA256: 81a5800500b3fafc23af4b7643e79a3d206c3ca6c80f6924514001ec85dc2a42
C_PROMPT_CHARS: 18084
API_CALLS: 0
FILES_WRITTEN: FALSE
OOD_TEST: LOCKED
```
I 3 troncamenti sono deliberate limitazioni del budget visibile delle osservazioni, **non** 3 evidenze perse o ignorate. La C va interpretata con questa limitazione esplicita.

## Codice preparato sul nuovo branch

`feature/rq2-v2-sonnet-c-sourcebound-2026-11-13`, basato sul commit D congelato `bf2b0a0...`.

- `src/evaluation/rq2_v2_sonnet_c_sourcebound.py`: un solo stage C per `cloudbed-1_q050/sonnet/A1`, usa source binding GT-free attuale, verifica in sola lettura parent D release/claim/record usando hash storici **anche se il commit C nuovo è diverso da quello D**. Ricostruisce `prepare_cause_probe`, blocca se package/hash/8 evidenze/3 troncamenti/18084 caratteri variano. C ha nuovo protocollo, namespace dedicato, release SHA indipendente e stato `NO_API` per default. Nuovo claim `O_EXCL` prima della chiamata; validazione C con `validate_cause_probe`, output esatto, scelta diagnosis/abstain, provider error, token usage, prezzo stimato, readback e no retry. Niente K.
- `src/tests/test_rq2_v2_sonnet_c_sourcebound_offline.py`: **14 nuovi test** con mock solo per source, parent, release e fake LLM; ledger e parser reali. Verificano consent, release, source/package, claim/restart, JSON corretto e non corretto, astensione, errori e usage, tampering, V1 assente.
- Nessun altro file preesistente modificato, nessun risultato scientifico riscritto.

**Importante:** i 14 test non sono ancora stati eseguiti; il baseline reale di PyCharm resta **867 PASS**. Atteso con i test nuovi: **14 mirati**, **881 globali** (se discovery invariata). Non dichiarare PASS prima di output utente.

## Nuovo gate GitHub → PyCharm

```powershell
git status --short
git fetch origin
git switch --track origin/feature/rq2-v2-sonnet-c-sourcebound-2026-11-13
git log -1 --format="%h %s"
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_sonnet_c_sourcebound_offline.py" -v
```

Solo se i 14 passano:
```powershell
python -m unittest discover -s src/tests -p "test_*.py" -v
```

## No API finché non conclusi questi gate

1. Correggere eventuali test solo sul nuovo codice C e in nuovo commit.
2. Bloccare il commit esatto del nuovo branch, ripetere preflight Colab reale read-only sulla nuova HEAD (source binding SHA diverso da D); verificare la D parent **senza** eseguire D.
3. Scrivere solo C `release_v1.json` in nuovo namespace dedicato, digest SHA, validazione e readback; consenso esplicito alla singola API (modello Sonnet 5.5, 1 richiesta, no retry, max output 4096, 300s per-request, limite operativo proposto USD 5 non hard cap).
4. Solo successivamente una C reale, niente K finché non c'è un C record valido. Nessuna C/K eseguita ora.
5. Mai toccare D, i 39 record V1, RQ1 scorer, gli 11 OOD test o GT.

**Scadenza tesi:** 1 dicembre 2026. Dopo freeze: refactoring, commenti italiani, pulizia, scrittura.
