# RQ2 — Preregistrazione candidata scoring C e criterio K/RQ2-C

**Data:** 12 novembre 2026. **Stato:** CANDIDATE, non firmata né
usata per scoring reale; nessuna inferenza OOD eseguita. **16/16 test
sintetici del valutatore SUPERATI in PyCharm** (`Ran 16 tests in 0.004s — OK`), attestati dall'utente.

L'oggetto di questo documento è **chiudere le scelte ex ante** prima
di osservare le risposte C/K dei 4 discovery e prima di sbloccare gli
11 test. Non importare mai questo valutatore nel processo agente/LLM.

## RQ2-A — Classificazione fault-type della prova C

Fonte della tassonomia: inventario ufficiale aggregato GT isolato
`docs/ood/REPORT_INVENTARIO_CLASSI_GT_CONTROLLATO_2026-11-11.md`.
Quattro nomi **esatti**:
- `node CPU spike`
- `container write I/O load`
- `container process termination`
- `container packet loss`

**Scorer candidato:**
`src/evaluation/rq2_fault_type_eval_policy.py`;
test sintetici `src/tests/test_rq2_fault_type_eval_policy.py`
(**16/16 SUPERATI in PyCharm, 0.004s, output utente del 12/11/2026**).

- La C ha una risposta libera `predicted_fault_type`, senza lista
  target in prompt. Scoring primario strettamente lessicale:
  `casefold`, spaziatura, sostituzione della punteggiatura con
  spazi; quattro stringhe canoniche più la variante testuale
  `container write IO load` (IO vs I/O). Niente LLM-as-judge,
  substring, stemming, sinonimi semantici suggeriti a posteriori
  o aggiunte dopo vedere risposte.
- Diagnosi C **valida con classe sconosciuta o sinonimo non incluso**:
  `unmatched_diagnosis`, **non corretta** per lo scoring primario;
  non equivale ad astensione e va quantificata separatamente.
  Questo criterio deliberatamente conservativo può sottostimare
  diagnosi semanticamente corrette: riportare il limite nella tesi.
- `RECORDED_COMPLETE + decision=abstain` conta come astensione;
  `INVALID_OUTPUT`, `PROVIDER_ERROR`,
  `BLOCKED_DEPENDENCY` e stage non salvato sono categorie
  distinte, tutte nel denominatore pianificato.
- **Metrica primaria:** `correct / 11` per ciascuna delle
  6 combinazioni 2 harness × 3 modelli sulle query test;
  nessuna eliminazione di provider error o risposte mancanti.
  Copertura diagnosi `diagnoses / 11` (anche quelle sbagliate),
  copertura contratti validi `(diagnoses+abstentions)/11`.
  Accuratezza condizionata ai soli contratti validi e alle
  sole diagnosi è **secondaria**, e mai sostituisce la primaria.
- Confronto `A1_8R` vs `A1` sullo stesso modello e caso,
  **win/tie/loss** a livello query e rapporto dei denominatori,
  includendo errori/astensioni come non corretti; non trattare
  11 query come 11 episodi statisticamente indipendenti.
  La coppia `cloudbed-1_q014/q030` con finestra condivisa
  va gestita nello stesso cluster per ogni misura di incertezza.
  Evitare affermazioni di significatività con N così piccolo.
- La verità di riferimento è letta **solo** dal processo di scoring
  isolato, da GT ufficiale e mapping task/record verificato, dopo
  aver congelato le risposte OOD. Lo scorer è una funzione pura
  che riceve mapping in RAM e **non emette** `case_id→GT`,
  non legge Market, non invia API, non produce prompt.
  Il report aggregato e i denominatori si conservano con hash.
- Non dedurre correctness di C dallo score Microsoft della D:
  quest'ultima è un task diverso e alcuni task non valutano reason.

## RQ2-B — 24 K discovery: criteri conservativi e risultati negativi

Per ogni K salvare raw JSON, versione, hash prompt/binding e outcome,
senza riparazioni: `candidate`, `insufficient_evidence`,
`invalid_contract`, `provider_error`,
`blocked_dependency`, `requires_verification`.
`candidate` significa **solo contratto strutturale valido**.
Il catalogo KPI source-only `rq2_kpi_formalizability_preflight.py`
non certifica presenza nel Market, unità fisiche,
semantica counter/gauge/rate né aggregazione.
Perciò la label **formalizable** non si assegna automaticamente
a nessuna delle 24 K.

**Criterio preregistrato per promuovere una regola a verifica
operativa (non automaticamente causale):** tutte le metriche devono
avere nome esatto, provenienza e disponibilità in sorgenti
**development autorizzate GT-free**, unità misurabile esplicitamente
definita, tipo di campione (counter vs gauge ecc.), aggregazione e
finestra riproducibili, gestione missing/sparse,
threshold finito e non scelto sugli 11 test, astensioni e
controesempi controllati. L'esecuzione deterministica deve essere
implementata **da codice verificato**, mai eseguendo il testo
`pseudocode` dell'LLM.

Se manca anche una sola precondizione, marcare
`not_formalizable` o `requires_verification` senza eseguire la
regola sugli 11 test. Non inventare unità, conversioni o metriche.
Un esito con **0 regole formalizzabili** è un risultato scientifico
negativo da riportare, **non un motivo per cambiare le soglie
dopo aver visto la test**.

## RQ2-C — Condizione per esperimento con pseudoregola

Arm principale dimostrativo da fissare **prima** di vedere le K:
`A1_8R + claude-sonnet-5-5`, coerente con RQ1 e scelto
a priori; tutte le K degli altri arm rimangono nella tabella
descrittiva, non vengono eliminate o selezionate secondo score.
RQ2-C si esegue **solo** se una o più regole passano i controlli
statici di implementabilità e sono **congelate con hash e
criteri di applicazione** prima di esaminare gli 11 test OOD.

Il valutatore `rq2_rule_group_scorer.py` tratta la finestra
temporale multi-guasto come positiva per ciascuna delle classi
contenute, con GT completo fornito da processo separato;
TP/FP/TN/FN, abstain, error e coverage in gruppi, non
pseudocodice eseguito. Gruppi con reference incompleta restano
non valutabili; nessuna finestra healthy inventata.
Con 10 gruppi temporali test non dichiarare generalizzazione
statistica forte.

## Confini e check da soddisfare prima della release

- [x] 16 unit test del valutatore lessicale su dati sintetici
  superati e risultato registrato: `Ran 16 tests in 0.004s — OK`;
  nessun GT letto. **Il gate del test sintetico è chiuso**, non la firma scientifica.
- [ ] Scelta finale della policy lessicale confermata e codice
  SHA congelato **prima di eseguire discovery/test OOD**.
- [ ] Audit GT isolato già documentato, ma specifica partizione
  V1 e arm dimostrativo devono essere formalmente firmati
  nel release, non solo nominati qui.
- [ ] KPI catalog e criteri ex ante documentati con hash,
  senza inventare unità. Eventuali limitazioni onestamente
  riportate in tesi.
- [ ] Transport RQ2-only 300s per-request candidato;
  37/37 unit test offline PyCharm superati il 12/11,
  ma release scientifico ancora bloccato.
- [ ] File release scientifico create-only con identity/hashes,
  readback SHA e `test_unlocked=false`, poi consenso esplicito
  per la prima discovery D a pagamento.

**Invarianti:** non modificare RQ1, mai importare scorer nel
runtime LLM, non aprire 11 test OOD prima del freeze
**scientifico** delle regole, niente human-in-the-loop diagnostico.
