# RQ2 — Test dell'audit Gemini read-only: 7 PASS, 1 FAIL di asserzione; fix minimo

**Data:** 13 novembre 2026. **Branch:** `experiment/rq2-provenance-v2-offline-2026-11-13`.

## Risultato realmente osservato in PyCharm

```text
Ran 8 tests in 0.017s

FAILED (failures=1)
```

Sette test sono passati, uno ha fallito:
`test_exact_24_record_summary_distinguishes_all_outcomes`
dopo aver elaborato correttamente 24 record sintetici
con 22 `RECORDED_COMPLETE`, 1 `INVALID_OUTPUT`,
1 `BLOCKED_DEPENDENCY`.

La riga di test errata era:

```python
self.assertNotIn("ground_truth", str(result))
```

Questa asserzione considera erroneamente un leak la
sottostringa `ground_truth` nel campo **legittimo**
`"read_ground_truth": False` (metadato di sicurezza).

## Correzione circoscritta

Commit `1cbcd88d838cbbeacfb012c8b33f35765641a543`
modifica **solo il nuovo test**:
```python
self.assertNotIn("ground_truth", result)
for case_summary in result["cases"]:
    self.assertNotIn("ground_truth", case_summary)
```

La semantica è adesso corretta: si verifica
l'assenza di una **chiave GT esatta** nel report
e in ciascun riepilogo, mantenendo separato il
flag `read_ground_truth=False`.

Il codice dell'audit, la V1, lo store/journal e
tutti i risultati Gemini rimangono invariati.
Non si è verificato un errore di provenance,
un errore provider né un accesso a GT.

## Gate da riconfermare localmente

```powershell
git status --short
git pull --ff-only origin experiment/rq2-provenance-v2-offline-2026-11-13
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v1_gemini_readonly_audit.py" -v
```

**Attesi 8 test**, esito del fix **NON ancora riportato**.
Non eseguire Colab o nuove API fino al PASS mirato;
poi suite globale e solo successivamente audit
Gemini reale in sola lettura. Nessun test OOD.
