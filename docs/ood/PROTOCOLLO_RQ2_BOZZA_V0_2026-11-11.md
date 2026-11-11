# PROTOCOLLO RQ2 — BOZZA V0 (non preregistrato, nessuna API autorizzata)
**Tesi magistrale — Harness Engineering per Root Cause Analysis, OpenRCA Market**  
**11 novembre 2026** • Stato: **proposta progettuale**, da discutere prima di congelare selezione, prompt e campagna. Questo documento **non è** un piano di run pronto, non modifica RQ1, non contiene etichette per caso, non avvia inferenze.

## 0. Evidenze consolidate e limiti di partenza

- RQ1 / EVALUATION20 congelata al commit sorgente `e4845e7fe9a399e10dd2db6f320dfeaeeddf3379`; NON modificare codice, prompt, scorer, output o metadati degli esperimenti storici.
- Fonte split Market: SHA256 `c3e99db3facbca592b13009829280b7402ed3a0b38e5bc687f2d1f8f73f2c724`; manifest GT-free SHA256 `5fabd40123aaa8bb614bb812f2994c776967b9b04ec3bfe477f89c1dde614d13`.
- 148 query originali: 92 development, 23 evaluation, 18 mixed_quarantine, 15 ood_holdout. Le 15 query OOD corrispondono alle **quattro classi intenzionalmente tenute fuori dallo sviluppo delle regole**:
  - node CPU spike: **3** query;
  - container write I/O load: **3** query (**tutte cloudbed-2**);
  - container process termination: **4** query;
  - container packet loss: **5** query.
- 14 gruppi temporali OOD di 30 minuti; `cloudbed-1_q014` e `cloudbed-1_q030` sono nello **stesso** gruppo e rappresentano **due classi differenti**. Non separare mai le due query in fasi diverse.
- Non risultano overlap OOD con altri split; nelle analisi di sensibilità fino a 4 ore non emergono ulteriori coppie aventi stesso cloudbed + classe + componente. **Questo non dimostra indipendenza fisica/causale delle fault injection**.
- **8/15** task originali richiedono il motivo (`reason`); i rimanenti task non possono essere equiparati a un test completo di classificazione della causa. Le classi OOD sono sconosciute al **rule engine**, non necessariamente al pretraining dei modelli.
- Le 11 classi non riservate includono **8 con detector implementati** e **3 senza detector affidabili (R03–R05)**. Non confondere le ultime con le quattro OOD.

Fonti interne:
- `docs/ood/REPORT_PREFLIGHT_GT_FREE_2026-11-10.md`
- `docs/ood/REPORT_INVENTARIO_CLASSI_GT_CONTROLLATO_2026-11-11.md`
- `docs/ood/REPORT_SENSIBILITA_DIPENDENZE_OOD_2026-11-11.md`
- `docs/ood/CONTINUITA_RQ2_E_REGISTRO_DECISIONI_2026-11-11.md`

## 1. Domande sperimentali, ipotesi e risultati nulli

**RQ2-A — Diagnosi OOD:** un LLM dotato di harness riesce a riconoscere il *tipo di guasto non coperto dalle regole deterministiche*, usando esclusivamente la telemetria? Il contributo dei detector preesistenti R8 è positivo, nullo o negativo a parità di preprocessing, budget e modello?

- **Confronto principale proposto:** `A1` vs `A1_8R`. Entrambe le configurazioni dispongono di evidence engineering; solo la seconda aggiunge gli otto detector. **Contrasto appaiato** entro stesso incidente e modello. Non assumere superiorità di `A1_8R`: detector noti possono essere irrilevanti, produrre falsi indizi o distrarre.
- **A0** come *baseline secondaria opzionale*, non necessariamente nel budget principale; `A1_8R_Planning` e `A1_PAVE` non sono necessarie al primo test di trasferimento della conoscenza. Usarle solo per una nuova domanda preregistrata; non inserirle a posteriori.

**RQ2-B — Conoscenza candidata:** a partire dalle evidenze raccolte su incidenti di scoperta, l'LLM riesce a formulare una spiegazione verificabile e una **pseudoregola deterministica candidata** (input, aggregazioni, condizioni, limiti, falsificatori)? Non equiparare plausibilità testuale a implementazione corretta.

**RQ2-C — Verifica limitata della regola:** se la pseudoregola è formalizzabile senza nuove ipotesi arbitrarie, una sua implementazione **offline** individua guasti in episodi **mai usati per formularla**, senza generare falsi positivi eccessivi? Con i numeri attuali chiamarla validazione *esplorativa*, non dimostrazione robusta di generalizzazione.

**Risultati di interesse anche se negativi:** nessuna diagnosi, diagnosi errata, astensione corretta, impossibilità di formulare una regola misurabile, regola non implementabile, falsi positivi, mancanza di casi indipendenti, impossibilità di generalizzare ad altro cloudbed.

## 2. Unità statistiche e proposta di separazione discovery/test

- Unità minima di protezione del leakage: **gruppo di finestre temporali sovrapposte nello stesso cloudbed**; unità fisica di fault injection da verificare se ulteriori metadati consentono tale controllo.
- **Opzione operativa principale (da validare mediante algoritmo offline con GT isolato, NON ancora effettuata):** scegliere *una query discovery per classe* da un **gruppo singleton** (non dalla finestra condivisa), con regola deterministica di scelta basata su hash e sale/versione dichiarati **prima** di vedere predizioni LLM. In questo dataset ogni classe ha almeno due singleton, quindi la proposta è compatibile con i conteggi aggregati, ma non equivale a un piano già costruito.
- La finestra che contiene due query di classi differenti viene assegnata **interamente al test**. Proposta conseguente, **solo se l'audit di partizione conferma tutti i vincoli**:
  - discovery **4 query** (4 gruppi singleton; 1 per classe);
  - test **11 query** (10 gruppi, di cui uno contiene 2 query);
  - ripartizione *teorica* dei positivi test per classe: **2 / 2 / 3 / 4**.
- Sia nell'assegnazione sia nella metrica, evitare di contare le 15 query come 15 guasti indipendenti.
- Un eventuale caso pilota Gemini usato per cambiare prompt/harness **non può** rientrare nella prova finale *indipendente* con quella configurazione; preferire test tecnici sintetici e casi development non-ood per il pilot.
- Nessuna regola/proposta derivata da discovery deve essere corretta dopo aver visto i casi, le predizioni o le metriche del test. Se si modifica una regola, il precedente test diventa sviluppo e serve un'altra coorte.

### Regole di partizione da implementare prima di qualsiasi API
1. Leggere `record.csv`/scoring solo da un processo di **selezione/valutazione separato** dagli agenti, validando hash e allineamenti ufficiali.
2. Applicare regola di selezione deterministica descritta nel codice, con seed/sale pubblico fissato **prima** di guardare ai risultati di modelli.
3. Verificare 1 discovery per classe, nessun overlap o gruppo cross-phase, nessun query_id duplicato, tutti i 15 casi coperti esattamente una volta.
4. **Piano pubblico di run**: solo case_id, finestra, task, cloudbed, arm/phase e hash; **mai associazione case_id→classe corretta**. Una tabella separata di valutazione può leggere GT ma non è importabile nel runtime inferenziale.
5. Persistenza create-only del piano con SHA256 e riferimento Git; audit readback prima di avviare run.

## 3. Protocollo di inferenza comparabile — due stadi più sintesi sulle sole discovery

**Stadio D — Diagnosi RCA originale**, identico nel suo scopo alle esecuzioni RQ1, ma con nuovi run ID e coorte. Ogni harness esegue il task OpenRCA originale, stessi 5 tool, stessa finestra, stesso limite di **6 round tool**, modello e parametri fissati; salva **raw_response** ed esito/integrità. Nessun GT o scoring durante l'inferenza. La predizione originale rimane immutata per lo **scorer Microsoft**, che resta una metrica distinta e secondaria per RQ2.

**Stadio C — Probe uniforme della causa, per ogni query (nuova chiamata LLM senza tool)**: su rappresentazione deterministica e di lunghezza fissata delle **evidenze osservate dal medesimo run** + istruzione originale (eventualmente raw_response da trattare come *ipotesi non verificata*), richiedere un campo `predicted_fault_type`, `predicted_component`, `abstain`, `confidence` intesa solo come auto-valutazione non calibrata, `evidence_refs` osservabili, `alternatives`. **Nessuna lista delle quattro classi da passare all'agente**: sarebbe un indizio artificiale sull'etichetta o un task closed-set più facile. Stabilire una regola fissa di normalizzazione/astensione dei nomi delle cause e un contract JSON task-agnostic. La probe deve essere identica per A1 e A1_8R e fra modelli, salvo provider-adapter.

**Stadio K — Proposta di regola, solo per discovery, dopo C**: un'ulteriore chiamata LLM *senza tool* su evidenze/diagnosi non etichettate, con contratto JSON:
- `hypothesis`: classe e componente ipotizzati; `evidence_refs` e anomalie misurate;
- `rule_name`, `scope`, `required_telemetry` (tool, campo, unità e finestra), `aggregation`, `condition` (comparatori/soglie o `unavailable`), `counterexamples`, `abstention_when`;
- `pseudo_code` dichiarativo (senza esecuzione di codice generato), `limitations`, `insufficient_evidence`.
- Gli output saranno trattati come dati potenzialmente erronei. **Nessuna esecuzione automatica di codice generato dall'LLM**, nessuna installazione/auto-aggiornamento di regole, nessun HITL implementato.
- **Nessuna etichetta suggerita:** "una discovery per classe" è una proprietà verificata dal selettore GT isolato, non un'informazione mostrata all'LLM. Se l'agente diagnostica la classe sbagliata o si astiene, la pseudoregola rimane errata, assente o non valutabile; non ripetere l'inferenza rivelando la classe corretta.

**Precauzione contro contaminazione:** eseguire prima tutte le discovery necessarie, congelare i candidati e l'eventuale specifica implementabile/criterio di selezione, **poi** aprire test. I test ricevono D e C, **non** K. Conservare errori provider/formato e costi con manifest; non correggere output a posteriori.

**Costi orientativi non ancora autorizzati:** 15 query × 2 harness × 3 modelli = **90 run D**; ognuna con **1 probe C** = altre 90 chiamate di sola finalizzazione; 4 discovery × 2 harness × 3 modelli = **24 proposte K**. Il costo effettivo dei tool e delle chiamate di esplorazione è maggiore del semplice conteggio di run D; queste cifre sono per **pianificazione**, non previsione USD né autorizzazione. Se budget/tempo insufficiente, ridurre esplicitamente il protocollo *prima* delle inferenze, non tramite selezione opportunistica degli esiti.

## 4. Validazione delle pseudoregole: livelli da non confondere

1. **Conformità del contratto** JSON, senza riempire campi mancanti inventando soglie.
2. **Grounding**: i KPI menzionati esistono davvero nei tool, con unità, granularità e finestra consultabile; citazioni di evidenze riscontrabili nella traiettoria del run; assenza di contraddizioni manifeste.
3. **Formalizzabilità deterministica**: regola traducibile in operazioni consentite, unità non ambigue, condizioni misurabili e astensione quando i dati mancano. Se la telemetria non permette discriminazione, classificare come *non implementabile con gli strumenti disponibili*.
4. **Implementazione offline autorizzata** e test: non eseguire `pseudo_code` LLM. Un programmatore riproduce una specifica congelata con codice controllato, senza guardare il test; suite sintetica e realistica.
5. **Test cieco su positivi e negativi**: applicare lo stesso detector fisso a OOD test della classe target (positivi) e a finestre senza tale classe (negativi one-vs-rest, pur con numerosità ridotta). **Precauzione multi-fault obbligatoria:** la finestra condivisa contiene due classi differenti; NON trattare una sua query come negativo della classe presente nell'altra query della stessa finestra. L'audit offline GT deve attribuire le etichette di verifica **a livello di gruppo/finestra e di componente**, controllando tutti i guasti nella finestra; se il negativo è ambiguo, escluderlo dal denominatore e segnalarlo. Non attribuire indipendenza a query nello stesso gruppo. Segnalare detection positiva, negativa, errore o astensione. Precision/recall/specificità e falsi positivi/negativi con **numeratore e denominatore**; evitare percentuali isolate e significatività enfatizzata.
6. Se prodotte più regole per classe dai diversi modelli/harness, **non scegliere retrospettivamente la migliore in base ai risultati di test**. Opzione consigliata: misurare struttura e validità di tutte le 24 proposte, mentre la dimostrazione eseguibile primaria usa **una procedura di scelta ex ante** (per esempio una regola prefissata per modello/harness, senza scegliere in base alla qualità osservata). L'elenco delle regole eseguibili va congelato prima dello sblocco del test.

## 5. Metriche e analisi

### Diagnosi
- **Primaria RQ2-A:** `predicted_fault_type` esatto rispetto alla classe ufficiale (normalizzazione/alias consentiti preregistrati), per le **query test**, con `abstain` contato separatamente e anche nella copertura; task di origine non deve variare il significato del criterio.
- Riportare corrette su eseguite, corrette su pianificate, astensioni, errori API/JSON **separati** e complete-case come analisi di sensibilità; non trasformare errore provider in score 0.
- Confronto **appaiato per query e per modello** A1 vs A1_8R: migliora/pari/peggiora, macro-per-classe e breakdown cloudbed/task. Le query della stessa finestra non devono essere trattate come due osservazioni indipendenti nei CI: eventuale bootstrap su gruppi di finestre; con n minimo privilegiare conteggi descrittivi e incertezza esplicita.
- **Secondaria:** score Microsoft del task originale su `raw_response` D congelata, conformità del formato, token, latenza, tool round, errori, esempi esplicativi.

### Conoscenza
- Griglia di valutazione preregistrata per **riferimenti di evidenza**, presenza di KPI, coerenza unità/soglie, falsificabilità, copertura delle alternative, limiti e astensione; due valutazioni separate quando possibile, disaccordi riportati senza mascherarli come misure oggettive.
- Tasso proposte strutturalmente valide / formalizzabili / non implementabili; non confondere *spiegazione plausibile* con *evidenza causale*.
- Verifica offline della regola: TP, FP, TN, FN, astensioni, copertura e casi non valutabili. Controlli negativi devono essere presenti e tracciati.

### Interpretazione
- Solo 3/3/4/5 query per classe e 14 finestre globali; **nessuna inferenza statistica forte** sulla generalizzazione. Non dichiarare OOD in senso di assenza da pretraining o causalità dimostrata. Con soli 2 positivi di test per le due classi meno frequenti, perfino 2/2 corretti resta un risultato esplorativo.

## 6. Decisione condizionata sull'ampliamento

L'archivio Market attualmente analizzato comprende già tutti i 148 record dei due cloudbed, suddivisi negli split congelati. **Non esistono ulteriori righe non alloccate dentro questi due cloudbed**; non fabbricare finestre e non ripescare evaluation/quarantine come nuovi test indipendenti.

**Prima delle API**, scegliere e documentare una delle strategie:
- **E1 (raccomandata se non ci sono nuove sorgenti indipendenti verificabili):** portare avanti con le 15 query, inquadrando RQ2-B/C come studio di fattibilità con limiti espliciti e mostrando comunque negativi/astensioni.
- **E2 (solo se disponibili nuovi episodi con stessa tassonomia e telemetria):** inventariare **altre campagne/cloudbed/dataset compatibili**, tracciarne fonte e possibili esposizioni, verificare fault injection indipendenti, preregistrare un'estensione distinta e bloccarla prima di usare i risultati. Almeno **3 positivi indipendenti di test per classe** è un *obiettivo progettuale illustrativo*, **non un criterio statistico di potenza**: con 1 discovery per classe, al momento ne rimarrebbero 2 per node CPU spike e write I/O, quindi servirebbero almeno +1 positivo di test per ognuna per raggiungere tale obiettivo, salvo altre dipendenze. Per il write I/O servirebbe un episodio esterno a cloudbed-2 se si volesse test cross-cloudbed.
- Non promettere E2 senza conferma delle fonti. Se si trovano nuovi episodi **dopo** l'analisi RQ2, classificarli come studio esterno/replica successiva e non aggiornare retroattivamente l'holdout originario.

## 7. Controlli ingegneristici obbligatori prima dell'esecuzione

- [ ] Branch e commit dedicati al protocollo; definizione completa task D/C/K, formato, normali alias, selezione e modello/provider/temperature/limiti.
- [ ] Script di partizionamento **offline e isolato GT** con test PyCharm (gruppo condiviso, una discovery per classe, nessun overlap, output senza mapping delle classi).
- [ ] Audit GT-free del piano esportato e hash SHA256 di split, manifest, codice, prompt, istruzioni e coorte.
- [ ] Test che impediscano in agent/tool/runner l'accesso a `record.csv`, `query.scoring_points`, scorers e mapping caso→etichetta.
- [ ] Test del contratto diagnostico, estrazione testo Anthropic, fallimenti e astensioni; mock provider senza spesa.
- [ ] Test di gestione create-only dei risultati su Drive, restart/resume, nessun retry involontario e congelamento raw prima di scoring.
- [ ] Costi preventivati da token storici reali e guardie su pilot/campagna; autorizzazione esplicita dell'utente per API Gemini/Sonnet/Haiku.
- [ ] Documento freeze del protocollo con hash dei manifest; analisi indipendente solo dopo freeze delle risposte.

## 8. Stato di approvazione, non-decisioni e prossimo passo

**Questa è una BOZZA V0, NON un protocollo approvato o congelato.** Sono ancora da approvare: quantità/criteri delle discovery; modello e harness per i detector eseguibili primari; strategia E1/E2; modalità esatta della probe C (input, token, contratto) e griglia K; budget. Nessun nuovo codice dell'agente, piano di run, selezione per-caso, invocazione API o scrittura di output sperimentale è stato eseguito.

**Prossimo passo implementativo:** predisporre un **selettore deterministico di partizione** in modulo `src/evaluation/` isolato, inizialmente `dry-run` sui 15 casi; test sintetici PyCharm, poi Colab offline, e discutere con l'utente il risultato PRIMA di congelare. La partizione deve mantenere la coppia con finestra condivisa e verificare 1 discovery per classe + tutti gli altri test, senza divulgare l'etichetta di alcun caso.
