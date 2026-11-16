# RQ2 — Congelamento del protocollo L1/L2 (16 novembre 2026)

**Stato.** Approvato da GPT e da Alessio il 16 novembre con le precisazioni sotto. Questo
documento fissa *prima* di aprire gli 11 incidenti sigillati e prima di leggere qualunque
ground truth: la tabella semantica, i parametri, i criteri L1 e L2 e il modo in cui si
verificano. Nessuna chiamata ai modelli; la discovery (commit `ddb2ca4`, 180 record) non si
tocca. Gli hash delle regole e degli elenchi li stampa e li registra il comando `freeze`
(file create-only `data/rq2_k_freeze_v1/freeze.json` su Drive); qui sotto sono quelli già
noti.

## 1. Decisioni approvate

| | Decisione |
|---|---|
| (a) | Tabella semantica v1 = mappatura di **compatibilità**, non di causalità. `ping.can_connect` è esplicitamente un KPI di nodo senza firma diretta. L'hash è stato ricalcolato dopo la modifica. |
| (b) | Tre esiti L1 (FORMALIZZABILE, NON_FORMALIZZABILE_NODE_CONTAINER, NON_CLASSIFICABILE), con **eseguibilità tecnica** e **classificabilità semantica** tenute separate. Una regola classificabile non è ammessa a L2 se non supera anche i controlli su unità, storia e condizioni. |
| (c) | Valutazione sui componenti che espongono i KPI necessari, popolazione fissata senza GT; esclusi tutti contati; copertura sul totale; un componente di riferimento non osservabile rende il positivo **NON_VALUTABILE**; nessuna conclusione sull'intera popolazione dai negativi osservabili. |
| (d) | Le due candidate eseguibili ma non classificabili (iowait del nodo, throttling CPU del container) sono riportate solo in modo descrittivo in L1; nessun verdetto L2. |
| (e) | H_pre = 60 s, H = 300 s, uguali per tutte le regole, fissati prima dei sigillati. Convenzione operativa, **non** tolleranza certificata dallo scorer Microsoft. |
| (f) | L2 è un caso di studio di verifica operativa preliminare su **una sola** candidata, senza affermazioni di generalizzazione. |
| cautela | `container_start_time_seconds` rileva un **riavvio osservabile**, non dimostra di per sé la causa della terminazione. Il limite è scritto nella famiglia di KPI e compare nel report accanto alla regola. |

## 2. Cosa è congelato

* **Codice**: commit `88e46580c38dd89cbfae8076ba0752776c1c12b5` (esecutore v2, valutatore v2,
  preflight, protocollo L1). Il comando `freeze` registra il commit effettivo, e `run`
  si rifiuta di partire se è diverso. I file del run V5 e dei contratti sono identici a `ddb2ca4`.
* **Tabella semantica** `rq2_k_semantic_table_v1`, hash `642b9d2c5f3bfd1b6bb70fe93d4410e142b0addf99c301ce34055ee87289c981`
  (era `5a42718…` prima di `ping.can_connect` e della cautela).
* **Parametri**, hash `7875e28f6075eb6e6b1ff3b29f963a06b38dbbc933bfe453fb54041f656a5ce0`
  (`PARAMETERS` in `rq2_k_l1_protocol.py`).
* **Run di discovery**: impronta dell'insieme dei 180 record
  `94e07d606b983aa06120238605eaeedf90eeb4be7abfc4ae3a5850edde2c7b4a`, `source_commit`
  `ddb2ca4` in tutti, 0 orfani.
* **Candidate**: 8 regole provate (molteplicità = 8). Elenco delle eseguibili e delle ammesse
  a L2, con l'hash di ogni regola, nel `freeze.json`.

Famiglie della tabella (la prima che corrisponde per livello e nome):

| Famiglia | Livello | Classe compatibile |
|---|---|---|
| uso CPU del nodo (`system.cpu.pct_usage/user/system/idle`) | nodo | node CPU spike |
| avvio del container (`container_start_time_seconds`) | container | container process termination |
| scritture su disco (`container_fs_writes…`) | container | container write I/O load |
| pacchetti scartati o errori di rete | container | container packet loss |
| iowait, `ping.can_connect`, altri `system.*`, throttling CFS, volumi di rete, altri `container_*` | nodo / container | nessuna firma diretta |

La classe è unica **dentro le quattro**: non si afferma di distinguere, per esempio, un picco
di CPU dal carico di CPU, classe già coperta dalle regole fisse e assente dai sigillati.

## 3. Criteri

**Ammissione a L2** = FORMALIZZABILE (un solo livello e una sola classe) e, separatamente:
unità dichiarata non incoerente col nome del KPI; in tutti e 4 i casi ogni componente che
espone il KPI ha il campione nella prima finestra e la storia completa; nessuna soglia
irraggiungibile in tutti i casi; nessun contatore cumulativo usato senza `delta`.

**L1 passato** (sui soli 4 incidenti di discovery, senza GT): l'esecutore non dà errore;
popolazione non vuota in ogni caso; frazione valutabile ≥ 0,95; file storici presenti;
componenti totali uguali a quelli del catalogo.

**Verdetto L2** (solo dopo l'ok a leggere il report L1): `VERIFICATA_OPERATIVAMENTE` solo con
0 FN, 0 FP, ogni positivo valutabile rilevato e localizzato (componente di riferimento tra
quelli che scattano, primo scatto in [t_gt − 60 s, t_gt + 300 s]) e copertura dei negativi
ammissibili ≥ 2/3 (soglia **esplorativa**); `NON_VERIFICATA` con una prova contraria;
`NON_VALUTABILE` per lacune. Intervalli di Clopper-Pearson al 95 %. Un positivo con riferimento
non osservabile esce dai denominatori ed è riportato a parte; un negativo vale per i soli
componenti osservabili.

## 4. Limiti dichiarati

* V5, V5.1 e il retry di trasporto sono post hoc (dichiarati nel registro).
* I criteri di ammissione sono stati scritti **dopo** aver visto il preflight sui 4 casi di
  discovery: non sono ciechi, ma non usano etichette.
* Una sola regola pronta, una sola classe, 2/2/3/4 positivi per classe: L2 è un caso di studio.
* Le altre tre classi non hanno nessuna regola da verificare; 5 candidate su 8 richiedono
  metriche di servizio, log o trace, che l'interprete non esegue (lavoro futuro).
* L'uso di H_pre/H e della soglia 2/3 è convenzionale; il codice di valutazione l'ha scritto
  Claude e ha una revisione indipendente di GPT.

## 5. Procedura

1. `freeze` (scrive `freeze.json`, create-only) → 2. `run` (verifica il freeze, esegue L1 sui
4 incidenti di discovery, scrive `l1_report.json`, create-only) → 3. lettura del report da
parte di Alessio e GPT → 4. solo con il loro ok, L2 sugli 11 sigillati in un processo separato
con la GT. Se il codice cambia dopo il freeze serve un nuovo congelamento, dichiarato.
