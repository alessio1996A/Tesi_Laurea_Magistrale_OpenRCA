# Fase 1 — Esperimento controllato del planner (4+2 vs 5+1)

**Stato: codice offline, nessuna API eseguita.** La campagna V3 rimane
congelata al commit 6747eecc77c1b2fff7d581c7284578b5c574b4f7.
Questa ablation crea piano e risultati in directory differenti.

## Ipotesi e controllo

L'unica variabile trattata e' la riserva di round del planner:

- Braccio 4p2: max_tool_rounds=6, max_verification_checks=2.
- Braccio 5p1: max_tool_rounds=6, max_verification_checks=1.

Identici: A1_8R_Planning, Gemini gemini-3.5-flash-lite, prompt
RCA e task contract, cinque tool, report unificato, otto regole,
finestre ufficiali [start_unix,end_unix), limite ricorsione=30.
Il massimo di 6 round non garantisce 6 round effettivi: l'LLM puo'
fermarsi prima e il planner puo' avere meno candidati.

Gli 8 casi provengono dal piano V3 in Drive; il codice verifica
l'identita' del piano e gli SHA di manifest/split GT-free.
Il piano alterna l'ordine dei bracci per caso e prevede 16 run.
Risultati: **development/tuning**, non test indipendente.

## File

- src/evaluation/planner_budget_ablation.py: builder, preflight e runner
  create-only per **una run per invocazione**.
- src/tests/test_planner_budget_ablation.py: test offline senza API.

Percorsi Drive creati soltanto su richiesta:

- data/protocols/v2/openrca_planner_budget_4p2_5p1_development_v1_plan_v1.json
- data/results/v2/openrca_planner_budget_4p2_5p1_development_v1/

Non usare il vecchio v2_campaign_runner.py per lanciare questa fase:
e' vincolato al commit originale della V3.

## PyCharm Windows — test offline

Dalla root del progetto, dopo aver fatto checkout del branch:

~~~powershell
$env:PYTHONPATH="src"
python -m compileall -q src
python -m unittest discover -s src/tests -p "test_planner_budget_ablation.py" -v
python -m unittest discover -s src/tests -p "test_verify_graph.py" -v
python -m unittest discover -s src/tests -p "test_*.py" -v
~~~

Non considerare l'ultimo comando superato fino a quando PyCharm
non ne mostra l'esito.

## Colab — SOLO DOPO test locali

Montare Drive, clonare questo branch su una working tree pulita,
installare dipendenze, verificare SHA e Secrets (senza stamparli).

La creazione del piano e' **offline** e **create-only**:

~~~bash
PYTHONPATH=src python -m evaluation.planner_budget_ablation \
  --data-dir /content/drive/MyDrive/Tesi_OpenRCA \
  --repo-dir /content/Tesi_OpenRCA \
  --write-plan
~~~

Dopo la creazione, il preflight in sola lettura e':

~~~bash
PYTHONPATH=src python -m evaluation.planner_budget_ablation \
  --data-dir /content/drive/MyDrive/Tesi_OpenRCA \
  --repo-dir /content/Tesi_OpenRCA
~~~

Il preflight restituisce 16 run pianificate e stati
ready, blocked_by_previous, complete, CLAIM_PENDING_NO_AUTO_RETRY,
ORPHAN_OUTPUT_REVIEW oppure REVIEW_*; non invoca alcun LLM.

**Non eseguire run pagate adesso.** Il runner a pagamento richiede
run_id, --confirm-api e --approved-budget-usd positivi;
nessun loop batch e' attivato di default. Il budget dichiarato e' una
**approvazione esterna**, non un limite di spesa garantito lato provider.
Qualsiasi crash dopo il claim blocca per sicurezza il run, anche quando
non sappiamo se sia stato addebitato.

Prima di autorizzare: verificare prezzi correnti, token stimati V3,
versione reale di langchain-google-genai, identita' del modello
sull'account e un tetto massimo accettato. Il nuovo client imposta
max_retries=1 su versione 4.x, che nell'SDK Google corrisponde a
**un tentativo complessivo**; una versione differente blocca il run.
Anche questo parametro, comune a entrambi i bracci, va registrato.

## Dopo le API (non ora)

Registrare per ogni caso score ufficiale parziale, strict/exact,
validita' JSON, token, latenza, preprocessing, round esplorativi
e di verifica realmente eseguiti, differenza paired 5p1 - 4p2.
Confrontare gli SHA delle evidenze tra i bracci. Congelare JSON,
claim, piano e commit prima dello **scoring offline separato**,
con scorer Microsoft OpenRCA al commit congelato
2a481ae63cb045c3eadbeca9eddaa10ec1151979.

**Limite metodologico:** questi sono gli 8 development gia' analizzati
nella V3. Un eventuale miglioramento e' esplorativo, non dimostra
generalizzazione. La fase 3 dovra' usare una coorte nuova disgiunta.
