# RQ2 — Protocollo K definitivo (proposta breve, da approvare e congelare)

> **Aggiornamento 16 novembre (sera):** il protocollo e' stato approvato con le precisazioni di GPT e
> congelato; vale il documento `RQ2_CONGELAMENTO_L1_L2_2026-11-16.md`. In particolare il `negative`
> conservativo sull'intero livello e' sostituito dalla popolazione dei componenti che espongono i KPI
> necessari (registro, righe 20-22).

**16 novembre 2026.** Sostituisce la bozza
`RQ2_PROTOCOLLO_VERIFICA_REGOLE_K_BOZZA_V1_2026-11-16.md` dopo le cinque precisazioni
di ChatGPT. Nessun dato sigillato aperto. **Non è approvato:** lo approvano Alessio e,
se serve, il relatore. Non cambia il run di discovery, che prosegue sul commit
congelato `ddb2ca4`.

**Revisione 2** (dopo il secondo parere di ChatGPT): `negative` diventa conservativo
(il 90 % non decide più), H e il margine iniziale sono parametri propri di questa
verifica e non dello scorer di OpenRCA, la soglia 2/3 sui negativi è dichiarata
esplorativa, e il perimetro RQ2-A è dichiarato come deviazione da V0. L2 resta in
stato **proposto** finché soglie, semantica e catalogo non sono congelati.

## 1. Livelli

L0 contratto (esiste) · L1 eseguibilità sui 4 incidenti discovery, senza etichette ·
L2 verifica operativa preliminare sui gruppi sigillati · L3 generalizzazione: **non
affermata**. Unità di scoring: gruppo di finestra temporale (10 gruppi per 11 query),
con `rq2_rule_group_scorer`.

## 2. Esecutore

- Interprete fisso. Mai `eval`, mai pseudocodice del modello. Insiemi chiusi del contratto.
- **Logica a tre valori** (vero / falso / sconosciuto, alla Kleene) per ogni condizione e
  per ogni coppia (componente, istante). Sconosciuto = KPI assente per il componente o
  nessun campione nella finestra.
  - `all`: falso se almeno una condizione è falsa; altrimenti sconosciuto se almeno una è
    sconosciuta; altrimenti vero.
  - `any`: vero se almeno una è vera; altrimenti sconosciuto se almeno una è sconosciuta;
    altrimenti falso.
- Decisione di gruppo, senza etichette, **conservativa**: `positive` se c'è almeno un
  (componente, istante) vero; `negative` solo se nessuna cella è vera **e nessuna è
  sconosciuta** (tutti i componenti del livello, tutti gli istanti della griglia);
  altrimenti `abstain`, con la causa (KPI assente per un componente, finestra senza
  campioni, storia non caricata, delta con un solo campione). Una lacuna non è prova di
  assenza. La quota di celle valutabili si **riporta** come misura di copertura, ma non
  decide `negative`: il 90 % è stato abbandonato perché una percentuale aggregata può
  nascondere una lacuna sul componente o sull'intervallo rilevante. Se con questa
  definizione le astensioni dominassero sui dati discovery (lo dice il catalogo:
  componenti senza KPI, copertura minima), la definizione si rivede **prima** del
  congelamento, non dopo.
- L'esecutore emette anche, per componente, il **primo istante** in cui la regola scatta.
  Non vede `t_gt`, il componente di riferimento né la classe.

## 3. Classe della regola

La tabella (livello node/container + famiglia del KPI) stabilisce una **compatibilità
semantica**, non una causa. CPU spike e CPU load del nodo non sono sinonimi: se la tabella
non separa i due casi la regola è **NON_CLASSIFICABILE**. `origin_class` (classe
dell'incidente di origine) resta provenance, non entra nell'esecutore né nella tabella.
`hypothesized_fault_type` è solo un controllo di coerenza.

## 4. Gate VERIFICATA_OPERATIVAMENTE (sul campione, nessuna generalizzazione)

Per una regola R con classe associata c, sui gruppi con riferimento completo:

1. **Copertura:** decisione forte su tutti i positivi per c e su almeno 2/3 dei negativi
   ammissibili. La soglia 2/3 è un criterio **esplorativo**: denominatori e astensioni si
   riportano sempre. Una regola che si astiene sistematicamente non supera il gate.
2. **FN = 0.**
3. **FP = 0** sui gruppi negativi (altre classi RQ2 incluse).
4. **Componente e tempo:** il componente di riferimento è tra quelli su cui R scatta e il
   suo primo scatto cade in [t_gt − H_pre, t_gt + H].
   - **H_pre e H sono parametri di questa verifica K, in secondi, uguali per tutte le
     regole**, indipendenti dalle finestre scelte dal modello (che arrivano a 24 h) e
     **non** attribuiti allo scorer di OpenRCA. Proposta: H_pre = 1 intervallo di
     campionamento, H = 5 intervalli, misurati sul catalogo dei discovery (60 s e 300 s
     se il passo è 60 s). Il 5 è una convenzione operativa, accettabile solo se il
     catalogo conferma la granularità; poi si fissa in secondi.
   - Nota di contesto, non di fondamento: il `query.csv` pubblico di OpenRCA scrive
     "within 1 minutes (i.e., <=1min)" per il tempo della causa nel compito di diagnosi.
     Non ho letto il codice dello scorer ufficiale.

FN = 0 e FP = 0 restano il gate rigoroso **sul campione osservato**. L'assenza di falsi
positivi sui soli gruppi valutabili non equivale all'assenza di falsi allarmi sull'intera
coorte, e non si afferma generalizzazione.

Altrimenti: **NON_VERIFICATA** (con motivo: FN, FP, localizzazione, tempo) o
**NON_VALUTABILE** (copertura insufficiente). Tutti gli esiti si riportano come conteggi
grezzi k su n, con intervalli esatti di Clopper-Pearson. Accanto a ogni regola
"verificata" si riporta quante regole sono state provate (fino a 60): su n così piccoli,
con più regole in prova, un esito perfetto può venire dal caso.

## 5. Perimetro RQ2 (da confermare)

- **Come eravamo (V0, 11 nov):** RQ2-A = diagnosi sulle 11 query test con una sonda C
  uniforme, confronto principale **A1 contro A1_8R** appaiato per incidente e modello,
  A0 secondaria; Planning e PAVE solo con una nuova domanda preregistrata. K: 4 incidenti
  × 2 harness × 3 modelli = **24** proposte.
- **Come siamo (V5):** 5 harness × 3 modelli × 4 incidenti discovery = 180 stage, **60**
  possibili K. Il run non include D o C sugli 11 sigillati. L'estensione da 24 a 60 K è
  dichiarata come deviazione da V0. È fissata nel piano congelato `ddb2ca4`, prima del
  lancio del run vero; i piloti hanno usato incidenti discovery.
- **Proposta:** RQ2-A si valuta **solo sui 4 discovery**, con lo scorer ufficiale dopo il
  congelamento. Confronto principale: A1 contro A1_8R, appaiato, 4 incidenti × 3 modelli =
  12 coppie, descrittivo (migliora / pari / peggiora). Le altre tre varianti sono
  esplorative. I sigillati servono **solo** al gate L2, senza chiamate a modelli.
  Alternativa, se il relatore vuole RQ2-A anche sui test: D e C su 11 incidenti con i
  due harness principali (circa 66 stage D); costa circa un'ora o due di run.
- **Stato del parere:** ChatGPT approva la proposta operativa per ragioni di metodo e di
  calendario. È una deviazione da V0 e va dichiarata: RQ2-A sui discovery è descrittiva,
  **non** un test indipendente della generalizzazione diagnostica. La valutazione
  indipendente è RQ2-C, sulle K applicate ai sigillati. La modifica di perimetro va
  confermata da Alessio e, per il metodo, dal relatore.
- **Nessuna selezione retrospettiva:** si valutano **tutte** le K `candidate`
  formalizzabili, per modello e harness.

## 6. Ordine di congelamento

1. Fine del run, audit dei retry (registro #10).
2. Catalogo KPI dei 4 discovery: nomi, passo di campionamento, campioni mancanti, KPI
   presenti in cloudbed-1 e in cloudbed-2. Sola lettura, nessuna etichetta.
3. Un commit con: questo protocollo, la tabella famiglia → classi, il 90 %, H, l'elenco
   delle K candidate. SHA-256 registrato.
4. L1 sui discovery. Lista finale delle regole eseguibili.
5. Solo dopo: telemetria sigillata in sola lettura, decisioni salvate con hash, poi scoring
   con il riferimento in un processo separato.

## 7. Implementazione minima (stima mia: 1-1,5 giorni)

Riuso: `rq2_output_contracts` (L0), `rq2_rule_group_scorer` (conteggi, copertura, astensioni),
`agent/tools.py` (percorsi e lettura CSV), i record V5.

Stato: due moduli sono scritti e collaudati solo su dati sintetici; il resto manca.
- `rq2_k_catalog.py` (branch `feature/rq2-v5-format-fairness-2026-11-16`): catalogo KPI
  GT-free dei discovery, 10 test. Da eseguire in Colab dopo il run.
- `rq2_k_rule_executor.py` (branch `feature/rq2-k-executor-2026-11-16`): interprete a
  tre valori, decisione di gruppo conservativa, primo istante per componente, 19 test.
  Mai eseguito su telemetria reale.
- **Da scrivere:** `rq2_k_rule_evaluation.py` (processo con riferimento: usa lo scorer
  di gruppo, aggiunge localizzazione, tempo, copertura sui negativi, Clopper-Pearson,
  verdetti), il lettore dei record K del run, la tabella famiglia → classi (dati, non
  codice), e i test sintetici di ciascuno.

## 8. Da approvare

- H_pre = 1 intervallo e H = 5 intervalli, dopo il catalogo (poi fissati in secondi).
- Criterio FN = 0, FP = 0 sul campione; soglia 2/3 sui negativi come criterio esplorativo.
- Tabella famiglia → classi e trattamento di CPU spike contro CPU load.
- Definizione conservativa di `negative`: confermarla dopo aver visto, nel catalogo, quanti
  componenti mancano di un KPI e quanto è bassa la copertura.
- Il perimetro del punto 5 (RQ2-A solo discovery, descrittiva), con l'ok del relatore.
