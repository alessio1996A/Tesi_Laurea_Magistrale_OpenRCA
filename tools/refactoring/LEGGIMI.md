# Refactoring dei commenti: regole e controlli

Obiettivo: commenti e docstring in italiano, con ogni passo spiegato, **senza cambiare il comportamento del codice**.
Ramo di lavoro: `refactor/commenti-it-2026-11-17` (da `feature/rq2a-offline-scoring-2026-11-17`).

## Regole

1. Si modificano **solo** commenti (`#`), docstring e righe vuote. Nessuna istruzione, nome, costante, stringa, prompt,
   etichetta di guasto, identificativo del benchmark o nome di API.
2. **25 file non si toccano nemmeno con un commento**, perche' un hash li protegge:
   - 13 con SHA-256 congelato nel consolidamento (sez. 7.2): `agent/tools.py` e i moduli `rq2_k_*`, `rq2_rule_group_scorer`,
     `ood_class_inventory`, `ood_holdout_preflight`, `v2_case_window_audit`;
   - 13 con hash git verificato da `evaluation/rq2_protocol_identity_preflight.py` (sorgenti RQ1 di EVALUATION20: `agent/prompts.py`,
     `graph_engine.py`, `model_factory.py`, `tool_factory.py`, `harness/evidence_builder.py`, `signal_catalog.py`,
     `harness/rules/rule_container_cpu.py` (R01), `output/v2_task_contract.py`, `evaluation/experiment_*`, `evaluation20_*`);
   - `agent/tools.py` e' in entrambi gli elenchi: in totale 25 file distinti.
3. Nessuna cancellazione, spostamento o ridenominazione di file prima della consegna: i percorsi compaiono nei record e negli hash.
4. Non si riscrive la storia dei branch (niente rebase, niente force-push). I tag `rq1-*` e `rq2-*` fissano i commit citati.
5. Mai rieseguire L2b (o altri passi che verificano la catena dei file congelati) su questo ramo: usare i tag.
6. **Niente docstring su classi Pydantic (`BaseModel`) e su funzioni `@tool`**: la loro docstring viene inviata al modello
   (descrizione dello schema in `with_structured_output`, descrizione del tool). Per documentarle si usano solo commenti `#`.
   Il controllo AST ignora le docstring, quindi lo verifica un controllo apposito (punto 5 del controllore).

## Controlli (dalla radice del progetto)

    python tools/refactoring/controlla_solo_commenti.py --base HEAD      # modifiche non ancora committate
    python tools/refactoring/controlla_solo_commenti.py --base origin/feature/rq2a-offline-scoring-2026-11-17   # tutto il ramo rispetto al punto di partenza (dopo `git fetch origin`)

Usare il ramo remoto `origin/...` e non quello locale, che potrebbe essere indietro: ne risulterebbero "modifiche" non dovute al refactoring.

Esce con codice 0 solo se: i 25 file protetti sono identici; nessun file di `src/` e' stato cancellato o rinominato; per ogni
file modificato l'albero sintattico (senza docstring) e' uguale a quello del riferimento; la docstring di nessuna classe Pydantic
e di nessuna funzione `@tool` e' cambiata.

Poi i test completi (devono dare lo stesso esito di prima della modifica):

    $env:PYTHONPATH = "src;src/tests"; python -m pytest src/tests -q -p no:cacheprovider      # PowerShell
    PYTHONPATH=src:src/tests python -m pytest src/tests -q -p no:cacheprovider                 # Colab/Linux

## Mappa del codice

`docs/MAPPA_CODICE.md` si rigenera con `python tools/refactoring/genera_mappa_codice.py`: per ogni modulo mostra gruppo, scopo,
protezione da hash e stato dei commenti (misurato).
