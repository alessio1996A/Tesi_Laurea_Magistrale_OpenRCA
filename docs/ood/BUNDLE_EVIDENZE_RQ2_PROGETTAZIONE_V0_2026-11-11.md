# RQ2 — Bundle deterministico delle evidenze realmente osservate (bozza V0)

**Data:** 11 novembre 2026  
**Stato:** codice e test sintetici creati, ma **non ancora verificati dall'utente**; nessuna inferenza, nessun accesso a Market, nessuna API. Il protocollo RQ2 e la selezione V1 non sono ancora congelati.

## 1. Scopo e compatibilità con l'architettura storica

Il nuovo modulo **isolato** `src/evaluation/rq2_evidence_bundle.py` trasforma esclusivamente la sequenza `tool_trajectory` già prodotta dagli agenti OpenRCA (RCA originale D) in un oggetto JSON con evidenze numerate `E001`, `E002`, ecc. e tracciabilità delle osservazioni dei tool. Non modifica `src/agent/graph_engine.py`, `src/agent/verify_graph.py`, runner storici, tool, limiti di round, prompt RQ1, scorer o risultati congelati.

Le due strutture di traiettoria **verificate sul codice sorgente GitHub**:
- **A0/A1/A1_8R** tramite `graph_engine.py`: eventi `{"tipo":"tool_call","nome":...,"parametri":...}` seguiti da `{"tipo":"tool_result","nome":...,"risposta":...}`, senza `tool_call_id`. Non è corretto dedurre che ogni risultato corrisponda a una specifica chiamata se ci sono **più chiamate concorrenti allo stesso tool**.
- **Planning / verify_graph**: eventi analoghi ma con `tool_call_id` e `origine` (LLM o planner). Il bundler è compatibile con la presenza degli ID e usa una corrispondenza **esatta** quando sono forniti.

**Politica conservativa:** per la traiettoria legacy senza ID l'associazione è ammessa solo se al momento del risultato esiste **una sola** chiamata pendente con quello stesso nome di tool. Se ne esistono due, la procedura **si interrompe senza costruire un bundle ambiguo**. Lo stesso vale per risposte orfane, chiamate senza risposta, duplicazioni di ID, tool non compresi nell'allowlist dichiarata e campo/struttura inattesa.

## 2. Proprietà del bundle

- ID delle evidenze assegnati nell'**ordine di arrivo delle risposte dei tool**, in modo riproducibile, non nell'ordine delle chiamate LLM.
- Per ogni evidenza: `tool`, argomenti del tool realmente registrati, `tool_call_id` quando presente, `call_origin` (oppure `unknown`), `observation_text`, SHA256 del testo **originale** della risposta, numero caratteri originali, indicatori di troncamento e osservazione vuota, `units_verified=false`.
- Le unità non vengono inventate. Anche se gli argomenti contengono intervalli `start_unix/end_unix`, la procedura non deduce KPI, cronologia, causazione o normalizzazione della misura. Un eventuale catalogo delle metriche deve essere verificato separatamente.
- Troncamento **esplicito e riproducibile**: preserva prefisso/coda, con marker al centro, al massimo **2400 caratteri per tool result** e **24000 caratteri visibili totali**, ripartiti uniformemente fra i risultati. Non sono nascoste omissioni di intere risposte; se troppe risposte non consentono il budget minimo, l'operazione fallisce. Il testo integrale va conservato nel log della run, **non ricostruito dal bundle**.
- `source_trajectory_sha256` identifica la traiettoria come catturata; `bundle_sha256` identifica il bundle derivato. Serializzazione JSON canonica e stabile per controlli di integrità.
- Il nome di tool deve essere esplicitamente presente in un'**allowlist** fornita dal runner; non viene creato un tool di GT. Difesa aggiuntiva rifiuta marcatori noti di ground truth/scoring (`scoring_points`, `ground_truth`, `record.csv`, `query.csv`, `scorer`) nei parametri/testi degli eventi.
- La difesa per marcatori testuali è soltanto **defense in depth**, non una garanzia che un testo malevolo o un dato non dichiarato non possa contenere risposte. La separazione vera delle sorgenti GT va garantita anche a livello di runner/tool e verificata prima delle API.
- Il bundle viene passato ai validatori `validate_cause_probe` e `validate_candidate_rule` usando `evidence_ids(bundle)`: un modello non può attribuirsi fonti con ID inesistenti senza causare errore di schema.
- Il testo delle osservazioni è **non attendibile come istruzione** (rischio prompt injection nei log/trace). Le note del bundle lo dichiarano, ma la mitigazione completa richiederà prompt e test di resistenza specifici.

## 3. Artefatti preparati

- `src/evaluation/rq2_evidence_bundle.py`: modulo **solo memoria e sola lettura della traiettoria**, Python standard library.
- `src/tests/test_rq2_evidence_bundle.py`: **14 test sintetici**, fra cui determinismo/hash, chiamate legacy sequenziali, risultati con ID fuori ordine, rifiuto ambiguità, GT accidentale, test input vuoto, troncamento, args non validi e integrazione di `evidence_ids` con il contratto C. I test sono **da eseguire in PyCharm**.
- `src/evaluation/rq2_output_contracts.py`: validatori JSON puri senza GT, già verificati da **16 test sintetici superati** in PyCharm secondo output dell'utente `Ran 16 tests in 0.034s — OK`. Questi test verificano lo schema, non l'accuratezza diagnostica o la correttezza delle pseudoregole.
- Sono stati preparati su `feature/ood-knowledge-transfer-audit-2026-11-10`, senza modificare i risultati EVALUATION20 e senza chiamate API.

## 4. Passi prima del protocollo congelato

1. Eseguire in PyCharm i 14 test del bundle; correggere eventuali anomalie su un **nuovo commit documentato**, mai su freeze RQ1.
2. Verificare in sola lettura la **vera allowlist** dei cinque tool e quali campi delle risposte contengano KPI e unità. Non usare nomi di esempio dei test sintetici come prova che tutti i tool reali siano compatibili.
3. Progettare un estrattore/adapter di input D→C/K **a partire dal runner corrente** con protezione sia sui file sia sui dati. In caso di ambiguità legacy, si dovrà decidere se aggiornare un **nuovo runner RQ2** per preservare `tool_call_id` (senza toccare RQ1), oppure marcare la probe come non disponibile; **mai inventare parametri abbinati al risultato**.
4. Preparare mock LLM e prove di injection/astensione; testare creazione e ripresa create-only di risultati. Non lanciare ancora Gemini/Claude.
5. Fissare i prompt C/K, metrica di classe, scelta ex ante delle regole, negative controls e budget **prima** del freeze e dell'autorizzazione delle API.

## 5. Limiti scientifici

La sola presenza di un ID come `E001` dimostra che un risultato del tool è stato registrato; **non** prova né la correttezza del risultato, né che sostenga la diagnosi, né la causalità. In RQ2-B saranno necessarie verifiche supplementari di grounding e discriminazione delle ipotesi. La coorte attualmente selezionata in anteprima rimane di 4 discovery e 11 test, con inferenza sulla generalizzazione solo **esplorativa**.
