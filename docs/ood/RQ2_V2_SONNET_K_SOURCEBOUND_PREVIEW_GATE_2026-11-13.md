# RQ2 V2 — Sonnet K source-bound read-only preview, GT-free

**Data:** 2026-11-13. **Stato:** codice offline preparato ma NON ancora verificato in PyCharm. Nessuna API, nessuna release K, nessuna K eseguita e nessuna scrittura su Drive.

## Parent congelati
- D di scoperta `cloudbed-1_q050 / sonnet / A1 / D` status `RECORDED_COMPLETE`. D record `521ed45b3dfefe6fd6c21427ca1c4ac0d03edbb1608bf80cbc424109c9f1a009`, D bundle `f63f1f0fd744497acc92814d8aabf80fb30cb08d8e5244ec62501d29052154d6`.
- C originale `rq2_v2_sonnet_q050_c_sourcebound_v1`: `INVALID_OUTPUT`, raw_response vuota, record `39364800134f3713302a6f314822930b501a4300af6d62a12f7ce376a93f0579`. Rimane invalida, non correggibile/ripetibile.
- C successore `rq2_v2_sonnet_q050_c_contentblocks_v2`: 1 API reale, `RECORDED_COMPLETE`, `diagnosis`, record `8e853074e69f1718ae1a8ebda3f67954bc495fa0d14651e0dfa8a3f03744a49b`, claim `1c87f64f92ff7487b647cfd7beb430cda26a5e6d34db98caf1021e843d980591`, release `7053f040afa04cdf9e63d91722e1ac7594e2da3965502a83234a9fa21c75e849`, code `73927d747430bf79e36cb65ecdcba632d9561f9d`, binding `344ce9ba435176e5ab48f1fabe139e470d739933b344ef0bfc35dcc404e2ede8`. Una lista Anthropic con 1 text e 1 nontext block, 7702 in + 754 out, USD 0.022944 stimati.
- Audit C read-only `SONNET_V2_C_CONTENTBLOCKS_READONLY_AUDIT_OK`: ipotesi `Node CPU spike (high user-space CPU load)`, componente `node-6`, confidence `low`, evidenze `E001,E008`, 3 alternative, 6 limitazioni. **Non è verità verificata**. OOD 11 query ancora locked.

## Sorgenti aggiunte, senza modificare i freeze
- Nuovo branch `feature/rq2-v2-sonnet-k-sourcebound-preview-2026-11-13` basato sull'HEAD C congelata `73927d747430bf79e36cb65ecdcba632d9561f9d`.
- `src/evaluation/rq2_v2_sonnet_k_sourcebound_preview.py`: esclusivamente `preview_k(data_dir,repo_dir)` e `require_fresh_k_namespace`. Rilegge source binding GT-free dal CSV originale, parent D, causa C, pacchetto C verificato, vecchia C invalida invariata. K usa esattamente `prepare_candidate_rule` e `validate_cause_probe` già esistenti. Ritorna un K prompt GT-free non eseguibile, identificativo K bind a nuova HEAD e parent C/D e SHA pacchetto K.
- `src/tests/test_rq2_v2_sonnet_k_sourcebound_preview_offline.py`: 18 test sintetici (pianificati) per source binding, status, SHA, problemi parent, K namespace vuoto, mancata contaminazione OOD, `insufficient_evidence` e soglie non finite.
- Nessuna `run_one_k`, nessuna release K: deliberatamente NO_API. No modifica al modello/prompt K del protocollo già esistente.
- Una candidate K è *esplorativa*. La bassa confidenza della C rende accettabile, e può rendere preferibile, `insufficient_evidence` se osservazioni, unità o soglie non giustificabili. Mai imporre a Claude una regola o inventare soglie.
- Il successivo campione K sullo stesso q050 sarà parte di un workflow di engineering corretto dopo un fallimento precedente, non una prova indipendente della generalizzazione OOD. Non comparare a GT.

## Gate immediato PyCharm

```powershell
git status --short
git fetch origin
git switch --track origin/feature/rq2-v2-sonnet-k-sourcebound-preview-2026-11-13
git log -1 --format="%h %s"
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_sonnet_k_sourcebound_preview_offline.py" -v
```

Se 18 mirati OK, regressione completa attesa 922 (904+18) test, da confermare. Solo dopo: **nuovo checkout Colab su HEAD K**, read-only `preview_k` con exact SHA D/C, K namespace assente, zero API/write/GT. Riportare K_PACKAGE_SHA e K_BINDING_SHA. Poi, previa decisione, codice esecutore K, release separata e una chiamata K. Non presumere validità della regola né sbloccare OOD.

Scadenza consegna tesi: 2026-12-01. Refactoring/commenti italiani/pulizia file superflui prima della scrittura, senza alterare protocolli congelati.
