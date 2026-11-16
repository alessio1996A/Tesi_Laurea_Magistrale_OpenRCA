# RQ2 — Protocollo di verifica delle regole K: BOZZA V1 da congelare

> **Sostituita** da `RQ2_PROTOCOLLO_K_DEFINITIVO_PROPOSTA_2026-11-16.md` (dopo le
> precisazioni di ChatGPT: tre valori, copertura sui negativi, orizzonte globale H,
> perimetro RQ2-A). Si conserva come cronologia.

**16 novembre 2026.** Stato: **bozza, non approvata.** Nessun dato sigillato è stato
aperto: non ho letto né telemetria né ground truth dei 11 incidenti sigillati. Conosco
solo gli ID e i conteggi per classe che stanno già nei documenti del repository.

Questo testo **precisa** il protocollo V0 dell'11 novembre
(`docs/ood/RQ2_C_VALUTAZIONE_OFFLINE_REGOLE_PROPOSTA_V0_2026-11-11.md` e
`docs/ood/PROTOCOLLO_RQ2_BOZZA_V0_2026-11-11.md`): ne conserva l'unità di scoring
(gruppo temporale), lo scorer isolato e la regola "se nessuna regola supera il gate,
non si attribuisce trasferimento". Sostituisce due mie proposte precedenti (registro
decisioni #8 e #9): la classe della regola presa dall'incidente discovery e il
criterio "almeno metà dei positivi".

## 1. Quattro livelli, da non confondere

| Livello | Cosa afferma | Dati usati | Chi lo calcola |
| --- | --- | --- | --- |
| L0 Contratto | Il JSON K rispetta `rq2_candidate_rule_v0` | solo la risposta del modello | `rq2_output_contracts` (esiste) |
| L1 Eseguibilità | Le metriche esistono nei dati e la regola si valuta con l'interprete fisso | telemetria dei **4 incidenti discovery**, senza etichette | da scrivere |
| L2 Verifica operativa preliminare | La regola congelata rileva la classe sui gruppi sigillati e non dà falsi positivi | telemetria sigillata (sola lettura) + riferimento GT in un processo separato | da scrivere + `rq2_rule_group_scorer` (esiste) |
| L3 Generalizzazione scientifica | La regola vale oltre questi casi | non raggiungibile | **non si afferma** |

L3 è fuori portata per costruzione: 2–4 gruppi positivi per classe, un solo cloudbed
per la classe write I/O, gruppi che non sono iniezioni fisicamente indipendenti. La
tesi dichiara L2 come **studio di fattibilità** (strategia E1 del protocollo V0).

## 2. Cosa significa "regola verificata operativamente" (proposta)

Una regola R, associata alla classe c (sezione 3), è **VERIFICATA_OPERATIVAMENTE** se,
sui gruppi sigillati con `reference_complete = true`, valgono **tutte**:

1. **Copertura.** R produce una decisione forte (positiva o negativa) su ogni gruppo
   positivo per c: nessun `error`, nessuna astensione sui positivi.
2. **Rilevazione.** FN = 0 sui positivi: R decide `positive` su tutti i gruppi che
   contengono c.
3. **Localizzazione e tempo.** In ogni gruppo positivo il componente di riferimento
   (cmdb_id) è tra i componenti su cui R scatta, e il primo istante in cui scatta cade
   in [t_gt − 60 s, t_gt + w_max + 60 s], dove w_max è la finestra più lunga della
   regola. Il ritardo ammesso è quindi dato dalla regola stessa, non tarato sui dati.
   I 60 s sono la tolleranza che attribuisco allo scorer ufficiale: **da riverificare
   nel codice dello scorer prima del congelamento.**
4. **Falsi positivi.** FP = 0 su tutti i gruppi negativi per c con riferimento
   completo, inclusi quelli che contengono solo altre classi RQ2.

Altrimenti il verdetto è **NON_VERIFICATA**, con il motivo riportato (mancata
rilevazione, mancata localizzazione, falso positivo) oppure **NON_VALUTABILE** se la
copertura manca (metrica assente, condizione non valutabile). NON_VALUTABILE non è un
fallimento della regola: è un limite del dato, e si conta a parte.

Le soglie di accettazione sono volutamente rigide (FN = 0, FP = 0). Con n piccolo
anche il risultato perfetto resta modesto: l'intervallo esatto di Clopper-Pearson al
95 % per k = n ha limite inferiore 0,158 per n = 2, 0,292 per n = 3, 0,398 per n = 4.
Il risultato si riporta sempre come **k su n con il denominatore**, senza percentuali
isolate e senza test di significatività.

È probabile che poche regole, o nessuna, superino il criterio. Il protocollo V0 già
prevede che sia un esito legittimo.

## 3. Associazione della regola alla classe (indipendente dai sigillati)

- La classe dell'incidente discovery da cui nasce la K si conserva come metadato
  `origin_class`. **Non** decide la classe della regola.
- La classe associata A(R) si ricava con una **tabella fissa** da compilare e congelare
  prima dei sigillati: (livello node/container, famiglia del KPI) → classi RQ2
  compatibili. Il livello si deduce dal catalogo (KPI di nodo o di container), la
  famiglia dal nome del KPI. Fonti ammesse: documentazione del benchmark e catalogo KPI
  misurato sui 4 incidenti discovery (solo cmdb_id e kpi_name, nessuna etichetta).
- `hypothesized_fault_type` (testo libero) serve solo come controllo di coerenza: se non
  concorda con A(R) si registra `class_text_mismatch`, senza cambiare A(R).
- Se A(R) ha più classi, R si valuta separatamente contro ciascuna. Se è vuoto o le
  condizioni attraversano famiglie incompatibili, la regola è **NON_CLASSIFICABILE**: si
  esegue per copertura e falsi positivi, ma non porta nessun verdetto di verifica.
- Limite noto: CPU spike e CPU load del nodo usano gli stessi KPI. La regola R07 (CPU
  load) è nel batch delle 8 regole; la distinzione tra spike e load non è verificabile
  con i soli sigillati, che appartengono alle quattro classi escluse.

## 4. Esecutore (semantica proposta)

- Interprete **fisso**, solo libreria standard e pandas. Mai `eval`, mai
  pseudocodice del modello: il campo `pseudocode` non si esegue.
- Insiemi chiusi del contratto: operatori e aggregazioni (`mean, max, min, sum, count,
  p95, last, delta`), `window_seconds` 1–86400, combinazione `all` / `any`.
- Valutazione su **ogni** componente del livello giusto che ha tutti i KPI della regola.
  Finestra scorrevole (t − w, t]. Con `all` le condizioni devono valere allo stesso t.
  `delta` = ultimo − primo valore della finestra.
- Decisione di gruppo: `positive` se R scatta su almeno un componente nella finestra
  del gruppo; `negative` se è valutabile ma non scatta mai; `abstain` se nessuna
  condizione è valutabile su nessun componente (KPI assente, serie vuota); `error` per
  eccezioni. Ogni astensione conta nella copertura.
- Le decisioni si producono **senza etichette**. Il riferimento (classi per gruppo,
  componente, istante, completezza) entra solo nel processo di scoring.

## 5. Negativi autentici e gruppi multi-guasto

- Unità = **gruppo di finestra temporale**, non la query. Nei documenti esistenti 11
  query sigillate formano 10 gruppi: `cloudbed-1_q014` e `q030` condividono la stessa
  finestra con classi diverse. Un gruppo con due classi è positivo per entrambe.
- Un gruppo è negativo per c solo se l'elenco dei guasti presenti è verificato
  completo. Altrimenti è `unscorable` e fuori dai denominatori (lo scorer lo fa già).
- I negativi "altro guasto" non sono finestre sane. Si dichiara. Un controllo su finestre
  sane si aggiunge **solo se** il riferimento di tutti i guasti del giorno è completo, e
  si riporta a parte, senza entrare nel verdetto.
- Le finestre sovrapposte tra gruppi si segnalano e si escludono dal denominatore
  negativo.

## 6. Ordine di congelamento

1. Si congelano i record del run di discovery (180 stage) e si fa l'audit dei retry.
2. Si misura il catalogo KPI sui 4 incidenti discovery (sola lettura, nessuna etichetta).
3. Si congelano in un commit: questo protocollo, la tabella famiglia → classi, il
   criterio, la tolleranza temporale, l'elenco delle regole K candidate. Si registra lo
   SHA-256 del documento.
4. Si fa L1 sui 4 incidenti discovery e si fissa l'elenco delle regole eseguibili.
   **Si valutano tutte le regole formalizzabili**, senza scegliere la migliore dopo
   aver visto i risultati (regola del protocollo V0).
5. Solo allora si apre la telemetria sigillata, in sola lettura, con log append-only.
6. Lo scoring GT avviene in un processo separato, dopo che le decisioni sono salvate
   e il loro hash è registrato. Nessuna modifica dopo.

## 7. Da approvare (decisioni non prese)

- Criterio FN = 0 e FP = 0 (rigido) oppure una soglia sui falsi positivi per ore di
  telemetria.
- Tolleranza temporale: [t_gt − 60 s, t_gt + w_max + 60 s].
- Tabella famiglia → classi e trattamento di CPU spike contro CPU load.
- Se riportare anche il controllo su finestre sane, quando il riferimento è completo.
- Taglio al 22 novembre: se l'esecutore non gira sulle classi più semplici, si riportano
  la qualità delle regole sui 4 incidenti discovery (L0, L1) e L2 solo sulle classi
  eseguibili, dichiarandolo.

## 8. Cosa non si afferma

Generalizzazione, causalità, indipendenza degli episodi, validità tra cloudbed diversi
(la classe write I/O compare solo in cloudbed-2), utilità in produzione.
