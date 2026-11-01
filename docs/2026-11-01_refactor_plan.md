# Piano di rifattorizzazione e validazione — 2026-11-01

## Obiettivo invariato

**Harness Engineering for LLM-based Root Cause Analysis**: progettare e misurare l'effetto di meccanismi di harness sull'accuratezza e sul costo di un agente RCA nel benchmark **OpenRCA 1.0 Market**, senza modificare i pesi dell'LLM.

Il sistema deve essere *model-agnostic* per architettura, ma gli esperimenti iniziali utilizzano **solo Gemini Flash Lite**: altri provider sono una verifica finale opzionale, non un prerequisito delle fasi centrali.

Le tre linee di ricerca sono:
1. Evidence harness: preparazione, selezione e tracciamento delle evidenze; 5 tool di telemetria; otto regole esistenti.
2. PAVE-inspired verification: supporto delle ipotesi, relazione nodo/container/servizio, compatibilità temporale, alternative; mai equiparare un'anomalia alla causa radice.
3. Knowledge transfer: estrazione di regole candidate da diagnosi *verificate*, versione e test di non regressione su casi di sviluppo indipendenti; nessuna promozione automatica.

## Snapshot sperimentale immutabile

- Repository: `alessio1996A/Tesi_Laurea_Magistrale_OpenRCA`
- Baseline storica: `e4951737640e4c690b4e7e89e3358dd7a016e624` (`feature/ablation-a1-v2`).
- Nuovo branch: `refactor/model-agnostic-harness-v1`.
- Varianti storiche: A0; A1_V2 (report unificato senza regole); A1 (A1-R8, report + R01, R02, R06, R07, R08, R09, R10, R11).
- Split preesistente **non modificabile**: development 92, evaluation 23, mixed_quarantine 18, OOD holdout 15.
- Batch iniziale: `cloudbed-1_q052`, `cloudbed-1_q040`, `cloudbed-2_q006`, `cloudbed-2_q012`.
- Dodici JSON e CSV `data/results/development_pilots/riepilogo_batch_development_v1.csv` conservati nel Drive; non sovrascrivere, riparare o reinterpretare retroattivamente le predizioni.
- Punteggi ufficiali del primo batch: A0 0,000; A1_V2 0,0625; A1-R8 0,375 di media su quattro casi, con **una sola esecuzione per variante/caso**. Questi risultati sono esplorativi, non una dimostrazione generalizzabile.
- Ground truth accessibile **solo al modulo di valutazione dopo il salvataggio delle predizioni**; mai nei prompt, nelle feature, negli strumenti o nelle regole. I quattro casi del batch sono già stati analizzati con GT e **non possono essere trattati come test indipendenti** di nuove idee.

## Decisioni architetturali

- **Model Factory**: separare la creazione del modello dal runner; mantenere l'iniezione di `llm` già supportata dal motore `graph_engine.py`; configurazione esplicita `provider/model`; nessuna modifica ai 5 tool per il solo cambio di provider.
- **Evidence Harness**: preservare algoritmi, soglie, formati e codici delle regole fino al completamento dei test di regressione. Non riscrivere per motivi estetici.
- **Output Contract**: modello interno `Diagnosis` con `root_causes`, validazione dei campi, dei tipi, dei timestamp e della cardinalità quando ricavabile dall'istruzione; serializzazione deterministica nel formato OpenRCA. Conservare sempre `raw_response`; eventuali tentativi di riparazione saranno tracciati, con budget e confronti separati. Distinguere conformità interna stretta, validità del parser e scoring ufficiale.
- **Verification** (fase successiva): report strutturato con stato supportato / contraddetto / non verificato, fonti, finestre e limiti. Nessuna lettura GT. Se i dati non consentono conclusioni, preservare l'incertezza.
- **Knowledge transfer** (fase successiva): registro delle regole candidate con provenienza, ragione, esempi di supporto e controesempi, test su sviluppo non utilizzato per inventare la regola, versionamento e gate di promozione; non modificare R01–R11 sulla base dei casi valutati.
- **Evaluation**: stesso task, finestra, strumentazione, criterio ufficiale e budget per i confronti accoppiati; misurare score, successi completi, component/reason/time dove valutabili, conformità JSON, tool calls, token, latenza e costi. Congelare configurazioni prima di usare evaluation/OOD.

## Sequenza di lavoro (senza nuove chiamate LLM finché non serve)

1. **Inventario e protezione**: controllare albero, dipendenze e test; mantenere snapshot e risultati; classificare file in mantenere/rifattorizzare/archiviare/eliminare. Non cancellare ora nulla in PyCharm o Colab.
2. **Model Factory minima**: togliere la costruzione Gemini dal runner; configurare provider e modello con default storico; fake LLM nei test. Verificare compatibilità con LangGraph.
3. **Regressione offline**: eseguire la suite test; confrontare su casi fissati gli hash deterministici delle evidenze e i prompt; nessun cambiamento silenzioso ai cinque tool o alle regole.
4. **Output contract**: schema, validator e serializer indipendenti dal provider; test con i 12 output storici senza alterarli. Soltanto dopo, smoke test Gemini su nuovi casi di sviluppo.
5. **Verifica PAVE-inspired**: partire da pochi controlli fondati sulla telemetria disponibile, con test sintetici e casi di sviluppo; ablazione isolata rispetto allo schema JSON.
6. **Trasferimento della conoscenza**: pipeline off-line separata dalla diagnosi online; gate di qualità e anti-overfitting delle regole candidate.
7. **Valutazione**: esperimenti predefiniti su ulteriori development, replicazioni quando sostenibili, poi evaluation e OOD tenuti sigillati fino al congelamento della versione.
8. **Documentazione e presentazione**: README aggiornato, diagramma, protocollo, risultati e limiti; consulto con il relatore **prima** di investire in un ampio secondo batch.

## Criteri di completamento della pulizia

- `README.md` descrive accuratamente lo stato e come riprodurre gli esperimenti.
- Ambiente PyCharm e Colab eseguono lo stesso package con configurazioni esplicite: niente path assoluti sparsi nella logica applicativa.
- `graph_engine.py` e l'harness non importano SDK di un provider specifico.
- Test offline verdi; preflight SHA storici verificabili; split GT-free invariati.
- Colab contiene solo setup, smoke test e runner sperimentale riproducibili; notebook storici sono archiviati, non cancellati alla cieca.
- Tutti i risultati precedenti rimangono immutabili e riconducibili al commit originale.
- Le nuove varianti hanno identificatori/versioni diversi dalle storiche.

## Priorità con obiettivo laurea dicembre 2026

Priorità alta: allineamento rapido con il relatore, architettura chiara, protocollo rigoroso, refactor minimo, harness verificabile, primi esperimenti indipendenti e stesura della tesi in parallelo.

Priorità successiva: PAVE-inspired mirato e knowledge transfer dimostrabile con esempi + controlli; non sacrificare la qualità sperimentale per l'ampiezza.

Priorità opzionale se tempi/API lo consentono: secondo provider LLM, ulteriori classi di regole e approfondimenti estesi. La discussione entro dicembre dipende anche da scadenze ufficiali e approvazione del relatore, non soltanto dal codice.
