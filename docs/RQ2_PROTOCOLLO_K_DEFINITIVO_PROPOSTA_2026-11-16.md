# RQ2 — Protocollo K definitivo (proposta breve, da approvare e congelare)

**16 novembre 2026.** Sostituisce la bozza
`RQ2_PROTOCOLLO_VERIFICA_REGOLE_K_BOZZA_V1_2026-11-16.md` dopo le cinque precisazioni
di ChatGPT. Nessun dato sigillato aperto. **Non è approvato:** lo approvano Alessio e,
se serve, il relatore. Non cambia il run di discovery, che prosegue sul commit
congelato `ddb2ca4`.

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
- Decisione di gruppo, senza etichette: `positive` se c'è almeno un (componente, istante)
  vero; `negative` solo se nessuno è vero **e** almeno il 90 % delle celle è valutabile;
  altrimenti `abstain`. Un KPI mancante non diventa mai `negative`. Il 90 % è un
  parametro **da misurare** sul catalogo dei discovery (tasso di campioni mancanti) prima
  del congelamento.
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
   ammissibili. Una regola che si astiene sistematicamente non supera il gate.
2. **FN = 0.**
3. **FP = 0** sui gruppi negativi (altre classi RQ2 incluse).
4. **Componente e tempo:** il componente di riferimento è tra quelli su cui R scatta e il
   suo primo scatto cade in [t_gt − 60 s, t_gt + H].
   - **H è globale**, indipendente dalle finestre scelte dal modello (che arrivano a 24 h).
     Proposta: H = 5 intervalli di campionamento, misurati sul catalogo dei discovery
     (300 s se il passo è 60 s). Il 5 è una convenzione, non è derivato: **da approvare**.
   - I 60 s: l'`query.csv` pubblico di OpenRCA (copia su Hugging Face) scrive "within 1
     minutes (i.e., <=1min)" per il tempo della causa. Verificato su quel testo; **non**
     ho letto il codice dello scorer ufficiale.

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

Da scrivere, tre moduli e una tabella:
- `rq2_k_rule_executor.py`: interprete a tre valori, decisione di gruppo, primo istante.
  Solo pandas e libreria standard, nessuna etichetta.
- `rq2_k_catalog.py`: catalogo KPI GT-free dei discovery (cella Colab di sola lettura).
- `rq2_k_rule_evaluation.py`: processo con riferimento. Usa lo scorer di gruppo, aggiunge
  localizzazione, tempo, copertura sui negativi, Clopper-Pearson, verdetti.
- Tabella famiglia → classi (dati, non codice).
- Test sintetici per ciascuno.

## 8. Da approvare

Il 90 % di valutabilità; H = 5 intervalli; copertura sui negativi ≥ 2/3; criterio FN = 0
e FP = 0; il perimetro del punto 5 (RQ2-A solo discovery) con, se serve, l'ok del
relatore.
