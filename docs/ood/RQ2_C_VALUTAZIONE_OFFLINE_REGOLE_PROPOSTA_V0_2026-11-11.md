# RQ2-C — Valutazione offline delle pseudoregole: proposta di protocollo V0

**11 novembre 2026** · **BOZZA DA CONGELARE PRIMA DEL TEST** · Nessuna API o nuova inferenza eseguita.  
Dipendenze: `PROTOCOLLO_RQ2_BOZZA_V0_2026-11-11.md`, `CONTRATTI_RQ2_DIAGNOSI_E_PSEUDOREGOLA_V0_2026-11-11.md`, audit V3 e piano `rq2_dryrun_workflow_preview_v0`.

## 1. Tre risultati distinti, da non confondere

- **RQ2-A — Diagnosi:** i modelli identificano o meno il tipo di guasto sulle 11 query test con la probe C uniforme, separatamente dall'RCA nativo D valutato dallo scorer Microsoft.
- **RQ2-B — Proposta di conoscenza:** sui soli quattro incidenti discovery il modello produce fino a **24** risposte K: 4 discovery × 2 harness × 3 modelli. Ogni K è un'**ipotesi non verificata**, con stato `candidate` oppure `insufficient_evidence`. Un JSON corretto non dimostra né capacità predittiva né implementabilità.
- **RQ2-C — Trasferimento sottoposto a prova:** le sole specifiche candidate ritenute formalizzabili secondo una griglia definita *prima* del test vengono **congelate** e trasformate in un controllore deterministico indipendente, senza eseguire codice generato dal modello. Il controllore è applicato **offline, in sola lettura**, a telemetria dei casi test; successivamente uno scorer isolato legge le etichette di riferimento e conta TP/FP/TN/FN/astensioni/errori. **Se nessuna regola supera il gate, non attribuire trasferimento; indicare RQ2-C non applicabile/negativo secondo criteri prefissati.**

Una eventuale **proposta di 24 regole** seguita da D/C sui test, senza esecuzione cieca del detector congelato, **non** basta a dimostrare trasferimento.

## 2. Gate proposto per la formalizzabilità prima del test

Il gate della regola da sviluppare non è un giudizio umano interattivo. È un'analisi deterministica a schema e catalogo telemetrico già verificato, senza cicli di feedback al modello:

1. Il JSON K è valido secondo `rq2_candidate_rule_v0` e gli ID E citano solo osservazioni realmente registrate nel D di discovery; nessun errore provider C/K è reinterpretato come regola vuota.
2. Tutte le metriche e le unità di `required_signals` sono disponibili **nello schema ufficiale dei tool**; i nomi KPI/unità devono essere verificati e fissati usando documentazione o codice, **non dedotti da una stringa LLM**. Se il KPI è inesistente o l'unità non verificabile → non formalizzabile.
3. Operatori e aggregazioni appartengono all'insieme chiuso del contratto, la finestra è misurabile sui dati disponibili, le soglie numeriche sono finite e non ricavate *ex post* dal test. Se il testo `pseudocode` contraddice i campi strutturati → segnalare contraddizione, non eseguire pseudocode.
4. Sono specificate condizioni di astensione e falsificatori; niente accesso al GT, allo scorer, a diagnosi del test o a regole congelate RQ1 come risposta precompilata.
5. Il controllore reale dovrà essere un interprete **fisso e controllato da noi**, con catalogo KPI e allineamento di unità, non `eval`/codice fornito dall'LLM. Il catalogo deve essere congelato prima del test.
6. La procedura deve preservare uno status distinto: `valid_candidate`, `insufficient_evidence`, `invalid_contract`, `unavailable_signal`, `unit_unverified`, `not_formalizable`, `provider_error`, senza sopprimere gli errori.

**Non ancora deciso:** regola/arm primaria, gestione dei candidati multipli e dizionario di alias delle quattro classi per il confronto offline. Le scelte devono essere fissate **prima di vedere predizioni, telemetria derivata e score del test**. Non selezionare retrospettivamente il candidato più accurato; una modalità conservativa è riportare **tutti i 24 candidati** e valutare separatamente quelli formalizzabili, designando **ex ante** un braccio/criterio primario.

## 3. Unità di scoring e multi-fault

Sono presenti **11 query test ma 10 gruppi di finestre temporali**, poiché due query (`cloudbed-1_q014` e `cloudbed-1_q030`) condividono la stessa finestra e **classi diverse**. Lo scorer **non** usa le query come prove indipendenti. Per ogni regola target (T), il gruppo è **positivo** se almeno una classe nell'insieme completo delle etichette del gruppo è (T). Altrimenti è negativo **solo se** l'elenco di fault presenti nel gruppo è verificato completo. Con riferimento incompleto/ambiguo, il gruppo è `unscorable` e non può diventare un TN artificiale.

Stati della regola sul gruppo: `positive`, `negative`, `abstain`, `error`. L'unità statistica è il **gruppo temporale**, non la query e non necessariamente un episodio di iniezione fisicamente indipendente.

Metodologia di valutazione:
- Conservare **conteggi assoluti**: TP, FP, TN, FN, astensioni positive/negative, errori positivi/negativi, gruppi con reference incompleta.
- **Copertura decisionale** = gruppi con hard decision (positiva/negativa) / gruppi con reference completa. Non convertire automaticamente astensioni/errori in FN.
- Precision/recall/specificità **condizionate alle hard decision** con denominatori espliciti, eventualmente non definite quando manca il denominatore. Riportare anche l'impatto delle astensioni/errori; evitare confronti che premiano modelli con bassa copertura.
- In RQ2 il GT della coorte viene letto **soltanto nello scorer offline post-freeze**, non nei messaggi D/C/K o nei tool; non esportare mai tabella `case_id → etichetta` verso runner, repository di produzione o prompt.
- I negativi `one-vs-rest` negli altri guasti OOD non equivalgono necessariamente a finestre sane; bisogna distinguere i controlli negativi con altra iniezione e un'eventuale coorte healthy separata, se disponibile, senza inventare esempi. Limitare le conclusioni alle condizioni testate.

## 4. Componente di scoring isolato predisposto

`src/evaluation/rq2_rule_group_scorer.py`: **funzione pura di sola valutazione** `evaluate_group_decisions(...)`. Non implementa la regola né usa `Market.zip`. Accetta *solo* in memoria:
- una tassonomia di riferimento fornita dal processo offline;
- gruppi con `group_id`, `case_ids`, `fault_types` (possibile insieme multi-label) e `reference_complete`;
- le **decisioni già prodotte da un detector congelato**, per `group_id`, senza vedere etichette.

Restituisce **solo aggregati**, mai le etichette per caso/gruppo. Un gruppo incompleto non diventa un negativo. Sono disponibili TP/FP/TN/FN, conteggi di errori e astensioni, copertura, tassi condizionati.

**Importante:** la funzione riceve GT dal suo *chiamante offline*; non è un modulo GT-free da importare nel runner! Non deve essere distribuita nell'ambiente inferenziale con il mapping delle etichette; conservarne separati ambiente ed input. Nessun test su vere query OOD è autorizzato prima del freeze.

`src/tests/test_rq2_rule_group_scorer.py`: **20 test completamente sintetici predisposti, NON ancora eseguiti dall'utente**, inclusa la verifica dei gruppi a due classi, rifiuto di duplicati/GT incompleto, errori, astensioni, denominatori, nessun label mapping nell'output. Nessun collegamento a telemetria reale.

**Esecuzione PyCharm proposta:**
```powershell
git status
git pull --ff-only origin feature/ood-knowledge-transfer-audit-2026-11-10
$env:PYTHONPATH="src"
python -m unittest discover -s src/tests -p "test_rq2_rule_group_scorer.py" -v
```
Attesi **20 test**. **Non** passare alla valutazione dei 10 gruppi reali finché non esiste uno schema regola validato/congelato e le inferenze D/C/K sono concluse.

## 5. Decisioni da chiudere e rischi

- Formato del **catalogo KPI/unità** compatibile con i cinque tool e relative aggregazioni.
- Definizione degli ID modello esatti e del budget massimo per D, C e K.
- Conferma della partizione V1 (4/11), della strategia E1 con limiti di n piccolo e del criterio primario di comparazione.
- Scelta ex ante delle regole da implementare o policy per verificare **tutte quelle formalizzabili** senza selezione dal test.
- Create-only degli output e autenticazione dei digest dei dati reali prima dello scoring; separazione GT fra runtime agent e processo valutativo.
- A fronte di 71/209 osservazioni storiche troncate, indicare `truncated_count` e valutare il rischio di informazione mancante, senza cambiare prompt in funzione di risultati test.

Il valore del presente scorer è metodologico: **non** esiste ancora una misurazione di TP/FP sui 10 gruppi OpenRCA di test, né una dimostrazione causale o cross-cloudbed.
