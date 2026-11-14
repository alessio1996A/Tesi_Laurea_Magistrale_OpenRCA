# RQ2 q045 — correzione portabilita' test link simbolici su Windows

Data: 2026-11-14. Nuovo branch `fix/rq2-q045-development-log-symlink-test-windows-2026-11-14` da `feature/rq2-q045-development-log-audit-2026-11-14`, commit di origine `9e3e04dcad53d2a9b70821cc346673df2997a832`.

## Output PyCharm utente
```text
Ran 20 tests in 1.011s
FAILED (errors=1)
test_wrong_dev_source_symlink_is_refused:
OSError: [WinError 1314] Il privilegio richiesto non appartiene al client
```
Gli altri **19 test sono passati**. Errore nel **setup del fixture**, alla chiamata `split_path.symlink_to(new_path)`, prima di invocare `audit(root)`. Non e' un failure del controllo di sicurezza del codice, e non autorizza un test OOD ne' la lettura di GT.

## Patch portabile e limitata al test
- Solo `src/tests/test_rq2_q045_development_log_audit.py::test_wrong_dev_source_symlink_is_refused` modificato.
- Il CSV split della fixture resta presente come file ordinario.
- Con `unittest.mock.patch.object(Path, "is_symlink", new=simulate_symlink)`, il test simula `True` solo per il path del CSV split e delega agli altri path il vero `Path.is_symlink`.
- In questo modo la verifica e' che `audit(root)` rifiuti un `is_symlink=True` e non semplicemente un file scomparso. Nessun privilegio OS o attivazione Developer Mode necessari.
- Il controllo reale `file.is_symlink()` nel modulo `src/evaluation/rq2_q045_development_log_audit.py` **non cambia**. Il numero test rimane 20.

## Gate PyCharm
```powershell
git status --short
git fetch origin fix/rq2-q045-development-log-symlink-test-windows-2026-11-14
git switch fix/rq2-q045-development-log-symlink-test-windows-2026-11-14
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_q045_development_log_audit.py" -v
```
**20 attesi, ma non dichiarare PASS prima dell'output utente.**

Nessuna API, chiamata modello, esecuzione della regola su dati reali, nuova diagnostica o scambio di campioni OOD effettuati dalla patch. Gli esperimenti e il K JSON sono immutabili; il freeze scientifico resta FALSE e 11 OOD test restano bloccati. Dopo il gate positivo, Colab solo per audit aggregato GT-free di sviluppo, con nuovo pin di branch e snapshot.
