# Consolidamento scientifico e operativo — chiusura della fase sperimentale RQ2

**Data:** 16 novembre 2026; **revisione del 17 novembre 2026** (sezioni 0, 1.2, 1.2b, 1.2c, 1.4, 4, 5, 8, 9).
**Branch:** `feature/rq2-k-executor-2026-11-16`; la revisione sta su `feature/rq2a-offline-scoring-2026-11-17`.
**Commit di partenza:** `5b51b3286d3354252e9b41e0f1e1f6b1d5c2ba47`.
**Natura del documento:** solo documentazione. Nessun codice, record, manifest, report o
artefatto è stato modificato o cancellato per scriverlo; nessuna chiamata a un modello; nessun
nuovo protocollo di valutazione. I numeri provengono da file già congelati o dal registro; gli unici
calcoli nuovi sono sottrazioni dichiarate (sezione 3.2) e conteggi sul repository (sezione 6).
La revisione del 17 novembre riporta anche l'esito di RQ2-A (sezione 1.2b), calcolato offline da un modulo
nuovo (`evaluation/rq2_a_offline_scoring.py`, non bloccato da hash) sui record già congelati: nessuna
chiamata a modelli (`provider_calls` 0), nessun record modificato.

**Decisione che questo documento registra** (GPT + Alessio, 16 novembre): la fase sperimentale di
RQ2 è chiusa. Nessuna nuova campagna LLM, nessuna nuova regola, soglia o configurazione, nessuna
modifica retroattiva dei risultati congelati (compresi quelli negativi). Si passa al refactoring
essenziale e soprattutto alla scrittura della tesi.

---

## 0. In sintesi: cosa è concluso e cosa resta

| Ambito | Stato | Riferimento |
|---|---|---|
| RQ1 (harness che migliora la RCA) | **Sperimentazione conclusa**; approvata dal relatore il 10 novembre. Resta la scrittura | sez. 1.1 |
| RQ2, D→C→K | **Run concluso e congelato**: 180 stage, 60 K, 8 regole candidate, 49 `insufficient_evidence`, 3 non validi con il contratto strict | sez. 1.2 |
| RQ2-A (D e C sui 4 discovery, scoring offline) | **Eseguita il 17 novembre**, descrittiva: lo strumento non misura l'identificazione della classe; lettura qualitativa a parte | sez. 1.2b, 1.2c |
| RQ2, verifica L1/L2 (esplorativa) | **Conclusa e congelata**: esito `NON_VERIFICATA` sull'unica regola ammessa; nella tesi diventa una sezione breve, protocollo in appendice | sez. 1.3 e 5 |
| Pipeline human-in-the-loop | **Non implementata, lavoro futuro dichiarato** | sez. 1.4 |
| Refactoring | **Da fare**, essenziale e controllato, dopo la revisione di questo documento | sez. 6 e 8 |
| Scrittura della tesi | **Da fare** | sez. 5 e 8 |

**Cosa resta aperto prima della consegna** (dettaglio in sez. 8): revisione di questo documento;
conferma col relatore di come presentare RQ2 e L1/L2 (punto in sez. 4); refactoring essenziale; scrittura.
**Consegna: 5 dicembre 2026** (confermata da Alessio il 17 novembre; il "1 dicembre" era un errore di un
contesto precedente, registro riga 34).

---

## 1. Stato finale per ambito (risultati empirici, limiti, lavoro futuro)

### 1.1 RQ1 — Harness Engineering per la RCA

**Domanda.** Componenti di Harness Engineering aggiunti progressivamente (evidenze deterministiche,
otto regole, pianificazione/verifica, contesto strutturale-temporale ispirato a PAVE) migliorano
accuratezza, efficienza e affidabilità di un agente LLM su OpenRCA 1.0 (Market)? Cinque varianti:
A0, A1, A1_8R, A1_8R_Planning, A1_PAVE (nomi storici A1_V2, A1, A1_VERIFY, A1_VERIFY_ST).

**Risultati empirici** (scorer ufficiale Microsoft, commit `2a481ae63cb045c3eadbeca9eddaa10ec1151979`):

1. *Development, Gemini, 8 incidenti, 1 replica* (storico, coorte usata anche per sviluppare; fonte
   `docs/ARCHITETTURA_E_RISULTATI_V3.md`, codice congelato `6747eecc…`):

   | Variante | Score medio | Diagnosi esatte | Token medi | Tempo medio (s) |
   |---|---:|---:|---:|---:|
   | A0 | 0,0000 | 0/8 | 35.286 | 157,84 |
   | A1 | 0,4062 | 2/8 | 48.659 | 170,76 |
   | A1_8R | 0,5000 | 3/8 | 48.177 | 191,14 |
   | A1_8R_Planning | 0,4375 | 2/8 | 32.144 | 101,67 |
   | A1_PAVE | 0,2812 | 1/8 | 36.100 | 109,91 |

2. *Development, tre modelli × cinque harness × 8 incidenti = 120 run*: confronto ufficiale congelato
   in `data/results/scoring/v2/openrca_cross_model_dev8_official_comparison_v1.json` (SHA-256
   `975ff3b8f28aea16a94a9ca8cb1e69c36c7bdf818d855c1c4be274c34ab76e71`). I numeri non sono
   riprodotti qui perché non sono stati riletti in questa sessione: citarli dal file.

3. *EVALUATION20, 20 incidenti non usati per lo sviluppo × 3 modelli × 5 harness × 1 replica = 300
   tentativi; 295 diagnosi valutate; 5 errori del provider (503, Gemini) conservati come mancanti,
   non come zero.* Fonte: relazione del 9 novembre (Drive,
   `EVALUATION20_2026-11-09/Relazione_EVALUATION20_relatore_con_grafici_2026_11_09.pdf`). Tabella
   completa nella sezione 3.1. Confronto primario preregistrato, A1 − A0 appaiato entro modello:

   | Modello | Coppie | Differenza media di score | IC bootstrap 95% | Vittorie/pari/sconfitte |
   |---|---:|---:|---|---|
   | Sonnet | 20 | +0,2795 | [+0,1000; +0,4715] | 9/10/1 |
   | Haiku | 20 | +0,0875 | [−0,1000; +0,2750] | 5/13/2 |
   | Gemini | 18 | +0,0928 | [−0,0278; +0,2228] | 4/13/1 |

   La direzione è positiva in tutti e tre i modelli; solo per Sonnet l'intervallo esclude lo zero.
   Le ablazioni successive sono secondarie e **non monotone**: per Sonnet, A1_8R → Planning è
   negativa (−0,0670, IC [−0,1350; −0,0125]) e Planning → PAVE positiva (+0,1375, IC
   [+0,0125; +0,2875]); per Haiku e Gemini gli intervalli includono lo zero (relazione del 9 novembre).

**Limiti (da dichiarare nella tesi).**
- 20 incidenti, una sola replica per condizione: i 300 tentativi non sono indipendenti e la variabilità
  intra-modello non è misurata.
- I dodici intervalli delle ablazioni non sono corretti per confronti multipli.
- Il confronto con l'archivio storico dell'RCA-agent Microsoft (media 0,0667 sui 20 `row_id`, 0/20 strict)
  è retrospettivo e a condizioni diverse (modello, strumenti, budget): la relazione del 9 novembre lo
  definisce *preliminare* finché non è ricontrollato dalla cella Colab di archiviazione. Non è stato
  verificato in questa sessione se quel ricontrollo sia stato eseguito.
- Token confrontabili soprattutto entro lo stesso modello (provider diversi li contano diversamente).
- Conformità al contratto V2 e accuratezza sono misure diverse; il contratto V2 non sostituisce lo
  scorer ufficiale e non è OpenRCA 2.0.
- Le otto regole coprono 8 delle 15 classi di guasto; con le quattro classi di RQ2 se ne contano 12.
  **Restano tre classi** né coperte dalle regole né oggetto di RQ2: non sono state ricostruite in
  questa sessione (`CONTESTO_ALLINEAMENTO_GPT_2026-11-16.md`, sez. 2, lo segnala già). Va dichiarato
  nella tesi, dopo averle ricostruite dalla tabella delle classi del benchmark.

**Lavoro futuro.** Più repliche per condizione, coorti più ampie, correzione per confronti multipli,
valutazione dell'harness su OpenRCA 2.0.

### 1.2 RQ2 — D→C→K sulle quattro classi non coperte dalle regole

**Domanda.** Un agente LLM può investigare guasti delle quattro classi escluse (CPU spike del nodo,
carico di I/O in scrittura del container, terminazione di processo del container, packet loss del
container) e proporre, da D (diagnosi) → C (spiegazione della causa) → K, una pseudo-regola
deterministica candidata?

**Risultato centrale (congelato, run a commit `ddb2ca499c4b41aa32a36fdc2f9850cb09bb75c3`,
namespace `data/rq2_v5_format_fair_v1`).**
- **180 stage** = 4 incidenti di discovery × 3 modelli (Gemini, Sonnet, Haiku) × 5 harness × 3 stadi.
  177 `RECORDED_COMPLETE`, 3 `INVALID_OUTPUT`; i 3 non validi sono tutti stadi K di Haiku. D e C:
  120/120 completi. Un solo retry (Gemini, C, q045 A0), recuperato; nessun `PROVIDER_ERROR` finale.
- **60 tentativi K → 8 regole candidate strutturate (`candidate`), 49 `insufficient_evidence`, 3 non
  validi con il contratto strict.** I 3 non validi contengono una chiave `combination` duplicata e
  sono `insufficient_evidence` nella sostanza; il parser strict li rifiuta, nessuna riparazione
  (registro, righe 15 e 19). Si riportano a parte, non si fondono con le astensioni valide.
- **Cosa si può affermare:** la pipeline D→C→K ha prodotto, in 8 stage K su 60, una regola candidata
  strutturata, conforme al contratto. È una **capacità di generare pseudo-regole candidate osservata**.
- **Cosa non si afferma:** che le 8 candidate siano corrette, causalmente valide o pronte per
  l'installazione nell'harness. Le pseudo-regole non sono conoscenza validata.

**Limiti.**
- 4 incidenti di discovery, una esecuzione per cella: nessuna stima statistica, nessuna inferenza sull'effetto
  dell'harness o del modello sulla capacità di produrre candidate (le candidate sono 8 su 60).
- La politica di formato V5 / V5.1 (un fence JSON valido è accettato) è motivata **a posteriori** da un
  audit V4 e dichiarata prima del run; si riportano sempre sia la conformità strict sia quella tollerante
  (Gemini 60/60 strict; Haiku 45 strict + 12 con fence accettato + 3 non validi; Sonnet 59 strict + 1
  fence, registro riga 13).
- Il confronto sull'accuratezza di D con lo scorer ufficiale (perimetro "RQ2-A", registro riga 11) è stato
  **eseguito il 17 novembre** (sezione 1.2b, registro riga 33). Il suo esito è quasi tutto zero per limiti
  dello strumento, non per un risultato sulla capacità dell'agente.
- I token tra provider non sono confrontabili alla pari (Claude: `max_tokens=4096` condiviso con
  l'eventuale ragionamento esteso).
- Il codice dell'harness e dei protocolli è stato scritto con l'assistenza di Claude Sonnet 5.5, che è anche uno dei tre
  modelli valutati: conflitto di interesse da elencare tra le minacce alla validità (registro, "Limiti dichiarati").

**Lavoro futuro.** Vedi 1.4.

### 1.2b RQ2-A — D e C sui 4 incidenti di discovery (scoring offline, eseguito il 17 novembre)

**Che cos'è.** Scoring a posteriori dei 120 record D e C già congelati (4 incidenti × 3 modelli × 5 harness ×
D e C): D con lo scorer ufficiale OpenRCA, C con la politica congelata `rq2_fault_type_eval_policy_v1_candidate`.
Nessuna chiamata a modelli. Modulo `src/evaluation/rq2_a_offline_scoring.py` (commit `6c8ca00` e `ab0b62f`, 11 test
sintetici): rilegge ogni record verificandone l'hash SHA-256, rifiuta record fuori piano e incidenti sigillati,
scrive un solo report create-only. Report: `data/rq2_a_offline_v1/report.json` su Drive, SHA-256
`96051ba2c6a30038d9f90e247f141a36c8d7ab29b5bfb2e99ff74a25bb9d66d2`, impronta dei record `c7ce184b…263f`
(`records_read` 120, `provider_calls` 0). Scorer ufficiale: commit `2a481ae63cb045c3eadbeca9eddaa10ec1151979`,
`evaluate.py` SHA-256 `9a1c235139266c32b0e95c7e9938591b8fe014aad4cde95580f73f13a54d53f1` (verificato prima dell'uso).

**Risultati (descrittivi: 4 incidenti, una esecuzione per cella, nessun intervallo).**

| D, punteggio medio sui 4 incidenti | A0 | A1 | A1_8R | A1_8R_Planning | A1_PAVE |
|---|---|---|---|---|---|
| Gemini | 0 | 0 | 0 | 0 | 0 |
| Sonnet | 0 | 0,25 | 0,25 | 0,25 | 0,25 |
| Haiku | 0 | 0,25 | 0,25 | 0,25 | 0,25 |

- L'unico punteggio non nullo è `cloudbed-2_q026` (task_1: solo l'orario del guasto, tolleranza ±1 minuto):
  Sonnet e Haiku lo trovano con A1, A1_8R, A1_8R_Planning e A1_PAVE (8 celle su 8), con A0 no (0 su 2); Gemini
  mai. Gli altri tre incidenti (q032, q050, q045) sono task_2, cioè chiedono il motivo: 0 in tutte le 45 celle.
- Confronto appaiato A1_8R contro A1: 12 pareggi su 12 (nessuna vittoria, nessuna sconfitta, per ciascun modello).
- C, tipo di guasto: 0 corrette su 60, 0 con una classe nota sbagliata. 13 astensioni (Gemini 10, Haiku 3,
  Sonnet 0) e 47 diagnosi in testo libero che la politica lessicale non riconduce a nessuna classe.

**Perché gli zeri sul motivo non sono un risultato.** Lo scorer ufficiale confronta il motivo per stringa
esatta con l'etichetta di classe; il prompt di D non elenca le etichette; la politica di C non ha un vocabolario
delle quattro classi (il prompt di C vieta di assumere un elenco predefinito). Le etichette esatte arrivano
all'agente solo attraverso le regole, che per le quattro classi non esistono per progetto. Quindi con questi
strumenti l'identificazione della classe **non è misurabile**, né in positivo né in negativo.

**Cosa si può affermare.**
1. Con le evidenze deterministiche (A1) i due modelli Claude trovano l'orario del guasto in 1 incidente su 4,
   con A0 in nessuno; stessa direzione di RQ1, ma è un solo incidente.
2. Le otto regole sono neutre fuori dalle classi che coprono (12/12 pareggi, sempre su 4 incidenti).
3. Nient'altro: nessuna affermazione sull'identificazione della classe, sul miglioramento della generazione di
   candidate attribuibile all'harness, né sulla superiorità della candidata formalizzabile (#8) rispetto a quelle
   prodotte da A0 (verdetto L2 `NON_VERIFICATA`, n = 1; C e K vedono solo la traiettoria degli strumenti).

### 1.2c RQ2-A — lettura qualitativa dei testi liberi di D e C (post hoc, non cieca, non è una metrica)

Elenco in sola lettura prodotto da `--list-text` (senza ground truth; CSV `data/rq2_a_offline_v1/testo_libero_D_C.csv`
su Drive), affiancato a mano alle classi vere del report. **Lettura mia, fatta dopo aver visto le classi vere,
senza una rubrica fissata prima, su testo troncato a 120 caratteri.** I conteggi sono conteggi di lettura, non
risultati: in tesi vanno usati come esempi, non come numeri.

| Caso (classe vera) | D, testo libero | C, testo libero |
|---|---|---|
| q032, container process termination | 11 celle su 15 scrivono esaurimento o carico di memoria di cartservice-0; nessuna nomina un riavvio | 1 su 15 nomina "container restart / process termination (pod kill)": Sonnet, A1_8R_Planning, la cella da cui nasce la candidata #8. La stessa cella aveva scritto in D "node disk space consumption" |
| q050, node CPU spike | CPU a livello di nodo (node-6): A0 0/3, A1 2/3, A1_8R, A1_8R_Planning e A1_PAVE 9/9. Con le regole molte celle scrivono "node CPU load" | Sonnet nomina node CPU spike o saturazione in 3 celle su 5 (A1, A1_8R_Planning, A1_PAVE); Haiku sospetta la CPU di node-6 in 2 celle; Gemini si astiene in 4 su 5 |
| q026, container write I/O load | task_1: solo l'orario. Minuto giusto in 8/8 celle Claude con A1 o superiore; con A0 l'orario è arrotondato a 22:00 | I/O in scrittura o iowait in 8 celle su 15, nessuna con A0 né con A1_8R_Planning; solo Sonnet A1_8R scrive "container write I/O load"; gli altri parlano di disco o iowait del nodo |
| q045, container packet loss | A0 e A1: 6/6 sul percorso productcatalogservice verso TiDB (DNS, connessioni interrotte), nessuna scrive "packet loss". A1_8R, A1_8R_Planning, A1_PAVE: 7 celle su 9 si spostano su adservice (eccezione NullPointer, CPU, I/O) | Sonnet A0 scrive "DNS resolution failure / network packet loss", unica cella con "packet loss"; Haiku descrive timeout DNS o di rete verso il database in 4 celle su 5 |

**Che cosa se ne ricava (e con quale forza).**
- Nei casi q050 e q026 le evidenze A1 portano il testo libero verso la famiglia giusta più di A0, nella
  stessa direzione di RQ1; il punteggio ufficiale non lo vede, perché confronta l'etichetta esatta.
- L'etichetta di classe esatta compare in 6 celle di C su 60, tutte di Sonnet (q032 1, q050 3, q026 1, q045 1).
  Haiku descrive il sintomo (timeout DNS, saturazione di disco) senza nominare la classe; Gemini si astiene in 10
  celle C su 20. È un dato sul "livello di dettaglio delle spiegazioni dei diversi modelli" chiesto dal relatore,
  da trattare come osservazione.
- Le varianti con regole non migliorano rispetto ad A1 (12/12 pareggi). Due ipotesi **da non affermare**, da
  verificare solo leggendo le traiettorie: (i) in q050 la regola R07 ("node CPU load", dichiarata nel codice
  come "solo aumento persistente; non lo spike") suggerisce un'etichetta vicina ma diversa da quella vera;
  (ii) in q045 le varianti con regole spostano l'attenzione su adservice; se sia uno spostamento sbagliato dipende
  dal componente vero, che non ho letto.

### 1.3 RQ2 — verifica esplorativa L1/L2 delle candidate

**Che cosa è.** Una verifica operativa pre-registrata delle 8 candidate, sviluppata dopo il run con GPT.
È un **approfondimento esplorativo** (sez. 4): non fa parte del risultato centrale.

**Risultati empirici (tutti congelati; hash in sez. 7).**
- **L1** (GT-free, sui 4 incidenti di discovery): delle 8 candidate, **3 eseguibili**; **1 FORMALIZZABILE**
  (`container_start_time_advance_restart_detector`, classe *container process termination*); **2
  eseguibili ma NON_CLASSIFICABILI** (iowait del nodo; throttling CFS del container), solo descrittive;
  **5 NON_FORMALIZZABILI nell'esecutore** (2 con la metrica di servizio `mrt_max`, 2 su log, 1 su
  trace: tutte fuori dal catalogo node/container).
- **L2** (sui 11 incidenti sigillati, 10 gruppi di finestre temporali, una sola regola ammessa):
  verdetto **`NON_VERIFICATA`**. TP 0, FN 0, TN 5, **FP 2**: 2 falsi positivi su 7 gruppi negativi
  completi (IC95% esatto 0,037–0,710). Tre gruppi con un guasto della classe bersaglio (W01, W06, W10)
  sono **non osservabili** con il confronto per nome esatto (esclusi dai denominatori, contati). Lettura
  post hoc: se fossero ammessi, sarebbero 3 falsi negativi (rilevazione 0/3, IC95% 0–0,708) e i falsi
  positivi resterebbero 2/7; il verdetto non cambia (`RQ2_ESITO_L2_2026-11-16.md`).
- **Limite sui nomi, scoperto dopo L2b:** il valutatore confronta per stringa esatta il componente di
  riferimento con la telemetria; i container reali sono `node-N.<pod>`, i riferimenti stanno a livello
  di nodo, servizio o pod senza prefisso, e il protocollo congelato non definisce la corrispondenza
  servizio-pod. Non corretto, perché L2a/L2b sono immutabili.

**Che cosa mostra, e che cosa no.** Mostra che **generare non equivale a validare**: la regola passata
alla verifica è stata respinta e il filtro ha funzionato come filtro. Non mostra che gli LLM non possano
produrre regole verificabili per queste classi: è una regola, 10 gruppi, 3 positivi.

**Limiti.** Caso di studio su una candidata; criteri di ammissione scritti dopo aver visto il preflight sui
4 casi di discovery (non ciechi, ma senza etichette); soglia di copertura dei negativi (2/3) esplorativa;
H_pre = 60 s e H = 300 s sono convenzioni operative, non tolleranze dello scorer Microsoft; possibile
dipendenza temporale tra W07 e W08; nessuna affermazione di livello L3.

### 1.4 Lavoro futuro dichiarato (non implementato)

Pipeline human-in-the-loop, **da non descrivere come già realizzata**:

> LLM → diagnosi (D) → spiegazione (C) → pseudo-regola candidata (K) → **supervisione umana** →
> verifica e approvazione → eventuale integrazione nell'harness

Inoltre: tabella di corrispondenza dichiarata a priori tra nomi di riferimento (nodo, servizio, pod) e
componenti della telemetria; estensione dell'esecutore a log, trace e metriche di servizio (oggi le 5
candidate non formalizzabili restano fuori); ripetizioni e un campione di verifica indipendente più ampio;
le altre tre classi non coperte.

**Architettura duale** (idea del relatore nell'incontro del 5 novembre, da presentare solo come concetto): un
motore deterministico sempre attivo, che applica le regole verificate; un ramo LLM che si attiva quando il
motore non spiega l'anomalia, produce diagnosi, spiegazione e pseudo-regola candidata e le consegna al
supervisore umano; solo dopo la verifica e l'autorizzazione la regola entra nel motore. Il relatore ha
detto che non va implementata.

**Illustrazione del rapporto al supervisore** (esempio **illustrativo**, non l'output di un sistema
implementato; i campi usano i fatti congelati della candidata #8):

| Campo | Contenuto |
|---|---|
| Proposta | `container_start_time_advance_restart_detector`, classe container process termination |
| Origine | Sonnet, A1_8R_Planning, incidente di discovery `cloudbed-1_q032` (D → C → K) |
| Verifica eseguita | L1 passata; L2 su 11 incidenti sigillati (10 gruppi): `NON_VERIFICATA`, 2 falsi positivi su 7 gruppi negativi; rilevazione non stimabile (3 gruppi con la classe, non osservabili con il confronto per nome) |
| Limiti dichiarati | caso di studio su una sola regola; rileva un riavvio osservabile, non prova la causa; nomi dei componenti non allineati tra riferimenti e telemetria |
| Decisione del supervisore | spazio per l'autorizzazione o il rifiuto (non implementato) |

---

## 2. Le 8 pseudo-regole candidate

Fonte: `freeze.json` (SHA-256 del corpo `38d23b4c…8ea78`, Drive `data/rq2_k_freeze_v1/`), esiti L1 dal
report congelato. "Incidente" = incidente di discovery da cui la regola proviene. L'hash è il prefisso
di `rule_sha256`.

| # | Modello | Harness | Incidente | Regola (nome dato dal modello) | KPI / segnale | Categoria L1 | Motivo del limite | Storia (s) | Hash |
|---|---|---|---|---|---|---|---|---:|---|
| 1 | Gemini | A0 | `cloudbed-1_q032` | `checkoutservice_high_response_latency` | `mrt_max` (metrica di servizio) | NON_FORMALIZZABILE | KPI fuori dal catalogo node/container | 1800 | `0a56df42` |
| 2 | Gemini | A0 | `cloudbed-2_q045` | `productcatalogservice_database_errors_and_latency` | `mrt_max` (metrica di servizio) | NON_FORMALIZZABILE | KPI fuori dal catalogo node/container | 60 | `a78b2544` |
| 3 | Gemini | A1_8R | `cloudbed-2_q026` | `high_node_cpu_iowait_detection` | `system.cpu.iowait` (nodo) | NON_CLASSIFICABILE (eseguibile) | Nessuna firma diretta delle quattro classi: l'iowait non è l'uso CPU del nodo; solo descrittiva in L1 | 60 | `95d65f5e` |
| 4 | Gemini | A1_8R_Planning | `cloudbed-2_q045` | `adservice_null_pointer_exception_monitor` | log applicativi di `adservice` | NON_FORMALIZZABILE | Segnale su log: fuori dal catalogo node/container | 60 | `b9847389` |
| 5 | Haiku | A0 | `cloudbed-1_q032` | `cartservice-0 slow-span detector (symptom-level, exploratory)` | durata degli span di trace di `cartservice-0` | NON_FORMALIZZABILE | Segnale su trace: fuori dal catalogo node/container | 1800 | `a16b4037` |
| 6 | Sonnet | A0 | `cloudbed-1_q050` | `container_cfs_throttling_burst_vs_zero_baseline` | `container_cpu_cfs_throttled_periods`, `container_cpu_cfs_throttled_seconds` | NON_CLASSIFICABILE (eseguibile) | Nessuna firma diretta delle quattro classi; in L1 scatta in tutti e 4 i casi con 15–21 container su 40 (poco selettiva); solo descrittiva | 1800 | `f59cb0ac` |
| 7 | Sonnet | A1 | `cloudbed-2_q045` | `productcatalogservice replica MySQL driver connection-error burst` | righe di log per pod con `packets.go:37: unexpected EOF` o `driver: bad connection` | NON_FORMALIZZABILE | Segnale su log: fuori dal catalogo node/container | 60 | `d19555dd` |
| 8 | Sonnet | A1_8R_Planning | `cloudbed-1_q032` | `container_start_time_advance_restart_detector` | `container_start_time_seconds` (delta su 600 s) | **FORMALIZZABILE** (classe *container process termination*) | Rileva un **riavvio osservabile**, non dimostra la causa della terminazione. **L2: NON_VERIFICATA** (2 FP su 7 negativi; nessun guasto della classe rilevato) | 600 | `09001140` |

**Lettura della tabella.**
- Delle 8, una sola è stata ammessa a L2. Cinque su otto si appoggiano a metriche di servizio, log o
  trace: la conoscenza proposta dai modelli passa in parte da segnali che l'esecutore corrente (che legge
  solo metriche di nodo e container) non sa eseguire. Non è un giudizio sulla qualità delle regole.
- Nessuna candidata eseguibile e classificabile per le altre tre classi (*node CPU spike*, *container write
  I/O load*, *container packet loss*): nessuna delle 8 usa KPI di scritture su disco, pacchetti scartati o
  uso CPU del nodo (registro, riga 19).
- L1 sulla regola ammessa: popolazione 40/42 componenti in tutti e 4 i casi, frazione valutabile 1,0;
  positiva in q032 (1 componente) e q045 (1 componente), negativa in q050 e q026. Il positivo in q032 non
  è una prova: la regola è stata scritta dal modello sull'evidenza di q032 (registro, riga 23).
- Il nome "pseudo-regola" è corretto: sono condizioni deterministiche proposte, non regole dell'harness.

---

## 3. Sintesi dei risultati per modello e harness (senza affermazioni di miglioramento universale)

### 3.1 RQ1, EVALUATION20 (20 incidenti, 1 replica, scorer ufficiale)

"Strict" = score 1,0. "V2" = conforme al contratto V2 (dimensione diversa dall'accuratezza).

| Modello | Variante | Run valutate | Score medio | Strict | V2 conformi | Strict + V2 |
|---|---|---:|---:|---:|---:|---:|
| Sonnet | A0 | 20 | 0,1165 | 1 | 9 | 1 |
| Sonnet | A1 | 20 | 0,3960 | 4 | 17 | 3 |
| Sonnet | A1_8R | 20 | 0,4335 | 6 | 18 | 5 |
| Sonnet | A1_8R_Planning | 20 | 0,3665 | 5 | 18 | 5 |
| Sonnet | A1_PAVE | 20 | 0,5040 | 8 | 16 | 6 |
| Haiku | A0 | 20 | 0,1415 | 1 | 11 | 1 |
| Haiku | A1 | 20 | 0,2290 | 3 | 8 | 0 |
| Haiku | A1_8R | 20 | 0,2750 | 3 | 6 | 0 |
| Haiku | A1_8R_Planning | 20 | 0,2415 | 3 | 14 | 2 |
| Haiku | A1_PAVE | 20 | 0,3210 | 4 | 7 | 2 |
| Gemini | A0 | 19 | 0,0789 | 0 | 19 | 0 |
| Gemini | A1 | 19 | 0,1668 | 0 | 18 | 0 |
| Gemini | A1_8R | 18 | 0,1156 | 0 | 17 | 0 |
| Gemini | A1_8R_Planning | 20 | 0,2205 | 2 | 20 | 2 |
| Gemini | A1_PAVE | 19 | 0,2147 | 1 | 17 | 1 |

Totali: 295 run valutate, 41 con score 1,0 (conteggi di run, non di incidenti distinti), 28 anche conformi
a V2, 215 conformi a V2. Il confronto storico con l'archivio Microsoft (media 0,0667, 0/20 strict) è
contestuale e preliminare (sez. 1.1).

**Letture ammesse.** Le evidenze deterministiche (A0 → A1) hanno direzione positiva su tutti e tre i modelli
e un intervallo che esclude lo zero solo per Sonnet. L'effetto delle componenti aggiuntive è non monotono e
dipende dal modello. Entro lo stesso modello, le varianti con pianificazione cambiano token e tempo (nella
relazione: A1_8R → Planning, Sonnet −27,9% token e −22,1% tempo; Haiku +17,0% e +15,2%; Gemini −27,8% e
−17,2%).
**Letture non ammesse.** Un miglioramento universale dell'harness; un confronto causale con l'RCA-agent
originale; una graduatoria tra modelli (le condizioni di provider e budget non sono identiche).

### 3.1b RQ1, analisi esplorativa per copertura delle regole (17 novembre, post hoc)

**Che cos'è.** Le 295 run di EVALUATION20, con i punteggi ufficiali **già congelati** (scoring su `raw_response`),
divise per classe del guasto: 15 incidenti con classe tra le otto coperte da regola, 5 con classe fuori dalle
dodici note (l'etichetta non è salvata dallo script; lettura diretta di `record.csv` il 17 novembre: sono tutte
classi di rete senza regola, vedi sotto), 0 misti; 3 multiguasto. Modulo `evaluation/rq1_coverage_stratification.py`, report
`data/rq1_coverage_v1/strata_v2.json` (SHA-256 `f8f9bc5c9fbfabc2978c6a1ef762f9e0c998f9a9aafe0f8fa0f2e792821758f3`).
Prima di leggere i numeri, lo script ha riprodotto le 15 medie della tabella 3.1 (esito OK), 0 discordanze di hash,
5 run senza punteggio (errori di Gemini mai riprovati). Controllo di separazione (registro, riga 36): nessuna delle
quattro classi di RQ2 in development (0 su 92) né in evaluation (0 su 23), quindi nessuna nei 20 incidenti.

**I 5 incidenti non coperti** (lettura diretta di `record.csv`, riga = numero dopo `q`; verificata la
numerazione su tre casi noti): cloudbed-1_q012 (pod shippingservice-1, *container network packet
retransmission*); cloudbed-1_q058 (pod frontend2-0, *container network packet corruption*); cloudbed-2_q031
(servizio recommendationservice, *container network latency*); cloudbed-2_q054 (pod shippingservice-0,
*container network packet corruption*); cloudbed-2_q074 (servizio frontend, *container network latency*).
Sono quindi le tre classi di rete senza rilevatore affidabile (R03–R05): lo strato "non coperta" coincide con
"guasti di rete", e il confronto va letto così, non come "classi sconosciute".

Differenza media appaiata per incidente (vittorie/pareggi/sconfitte); coperta n = 12–15 per cella, non coperta n = 5.

| Confronto | Strato | Gemini | Sonnet | Haiku | Tre modelli insieme |
|---|---|---|---|---|---|
| A1 − A0 | coperta | +0,167 (4/9/0) | +0,339 (8/6/1) | +0,150 (4/10/1) | 16/25/2 |
| A1 − A0 | non coperta | −0,100 (0/4/1) | +0,100 (1/4/0) | −0,100 (1/3/1) | 2/11/2 |
| A1_8R − A1 | coperta | −0,091 (0/9/3) | +0,050 (3/10/2) | +0,128 (4/9/2) | 7/28/7 |
| A1_8R − A1 | non coperta | 0,000 (0/5/0) | 0,000 (0/5/0) | −0,200 (0/4/1) | 0/14/1 |

(Il totale su tre modelli conta lo stesso incidente tre volte: descrittivo, non indipendente.)

**Letture ammesse.**
1. Il guadagno delle evidenze deterministiche (A0 → A1) sta quasi tutto negli incidenti con classe coperta, con
   segno positivo su tutti e tre i modelli; nei 5 non coperti non c'è guadagno.
2. Le otto regole sopra A1 non mostrano un effetto netto nemmeno dove esistono (7 vittorie, 7 sconfitte): il
   segno dipende dal modello (Gemini negativo, Sonnet quasi nullo, Haiku positivo). Fuori dalle loro classi non
   danneggiano (0/14/1). L'ipotesi "il vantaggio delle regole si concentra dove le regole esistono" **non è
   sostenuta** da questi dati.
3. Per la tesi: il contributo robusto di RQ1 è lo strato delle evidenze; l'effetto marginale delle regole è
   incerto e dipende dal modello, in linea con la non monotonia già dichiarata in 3.1.

**Letture non ammesse.** Che le regole "non servano" (strati piccoli, una replica, effetto dipendente dal modello);
conclusioni generali sui guasti di rete (5 incidenti, due cloudbed); un nesso causale tra classe e guadagno (classe e difficoltà del compito possono
coincidere). Gli strati sono scelti **dopo** aver visto i risultati complessivi; la scelta di leggere questo
confronto è fissata nel registro (riga 35) prima di vederlo.

### 3.2 RQ2, K per modello e per harness

I 60 K sono 4 incidenti × 3 modelli × 5 harness. Le colonne `candidate` e "non validi" vengono dalla tabella
delle 8 candidate e dal registro (righe 13 e 15). Le `insufficient_evidence` valide sono **ottenute per
sottrazione** (K totali − candidate − non validi); `rq2_v5_run_cli summary` le conta direttamente e può
confermarle in sola lettura.

| Per modello (20 K ciascuno) | `candidate` | `insufficient_evidence` | non validi (strict) |
|---|---:|---:|---:|
| Gemini | 4 | 16 | 0 |
| Sonnet | 3 | 17 | 0 |
| Haiku | 1 | 16 | 3 |
| **Totale** | **8** | **49** | **3** |

| Per harness (12 K ciascuno) | `candidate` | `insufficient_evidence` | non validi (strict) |
|---|---:|---:|---:|
| A0 | 4 | 8 | 0 |
| A1 | 1 | 9 | 2 |
| A1_8R | 1 | 11 | 0 |
| A1_8R_Planning | 2 | 9 | 1 |
| A1_PAVE | 0 | 12 | 0 |
| **Totale** | **8** | **49** | **3** |

(I tre non validi: Haiku, K, q032 A1; q050 A1_8R_Planning; q026 A1.)

**Lettura.** Con 8 candidate su 60 e 4 incidenti, queste distribuzioni sono descrittive: non permettono di
attribuire a un modello o a un harness una maggiore capacità di produrre regole. In particolare, il fatto
che metà delle candidate venga dall'harness A0 e nessuna da A1_PAVE **non** è un risultato sull'harness.

**Candidate per harness e categoria L1 (aggiunta del 17 novembre; conteggio dalla tabella della sez. 2).**

| Harness | Stage K | Candidate | Eseguibili (L1) | Formalizzabili |
|---|---:|---:|---:|---:|
| A0 | 12 | 4 (#1, #2, #5, #6) | 1 (#6, non classificabile) | 0 |
| A1, A1_8R, A1_8R_Planning, A1_PAVE (insieme) | 48 | 4 (#3, #4, #7, #8) | 2 (#3 non classificabile; #8) | 1 (#8) |

Come si legge: A0 produce più candidate (4 su 12 contro 4 su 48). Le candidate prodotte con l'harness sono
eseguibili 2 su 4 contro 1 su 4, e l'unica formalizzabile viene da A1_8R_Planning; ma quella regola ha
verdetto `NON_VERIFICATA` e le differenze riguardano uno o due casi. **Non si afferma** che l'harness migliori la
qualità delle candidate; si riporta come **osservazione e ipotesi per lavoro futuro** ("l'harness non aumenta
il numero di candidate e potrebbe spostarne la natura verso segnali eseguibili sul catalogo"). Un test di
questa ipotesi richiede incidenti non ancora usati: le quattro classi non ne hanno più (4 di discovery e 11
sigillati già aperti da L2).

---

## 4. Perimetro concordato col relatore e verifica aggiuntiva L1/L2

| Elemento | Perimetro concordato | Approfondimento esplorativo L1/L2 |
|---|---|---|
| Domanda | Un agente LLM può investigare le 4 classi escluse e proporre una pseudo-regola? | La pseudo-regola proposta si lascia formalizzare ed eseguire, e regge una verifica operativa? |
| Pipeline | D → C → K su incidenti di discovery | L1 (esecuzione GT-free sui 4 casi di discovery); L2 (11 incidenti sigillati, 10 gruppi) |
| Prodotto | Regole candidate strutturate | Esito di verifica di una sola candidata |
| Risultato | 180 stage, 60 K, 8 candidate | `NON_VERIFICATA` (2 FP su 7 negativi) |
| Ruolo nella tesi | **Contributo principale di RQ2** (con RQ2-A e lettura qualitativa) | **Sezione breve** del capitolo RQ2, caso di studio; protocollo in appendice |
| Human-in-the-loop, integrazione automatica | Solo lavoro futuro | Non implementati |

**Fonti e discrepanza da dichiarare.** Il perimetro viene da tre fonti: le istruzioni di progetto (trasformare
la conoscenza in regole deterministiche "dopo opportuna verifica"); la riga 1 del registro; la trascrizione
dell'incontro col relatore del 5 novembre (REGIS 3), che non è nel repository. Nella trascrizione il relatore
chiede, per RQ2, di far spiegare all'LLM la regola e lo pseudocodice, di confrontare il livello di dettaglio
delle spiegazioni dei diversi modelli e di usare casi non usati nello sviluppo; la pipeline human-in-the-loop
(l'agente riferisce a un supervisore umano, che autorizza l'integrazione) e l'architettura duale sono lavoro
futuro che «non la dobbiamo implementare». La trascrizione non fissa una data di consegna.

La formula "**verifica su incidenti sigillati**" della riga 1 del registro **non compare nella trascrizione**:
è la nostra traduzione operativa di "prendere un caso non usato nello sviluppo". La verifica da parte del
supervisore umano è lavoro futuro. Il protocollo L1/L2 nei suoi dettagli (popolazione osservabile, H_pre/H,
soglia 2/3, Clopper-Pearson, due processi L2a/L2b) è stato progettato dopo, con GPT e Alessio (registro righe
8–12 e 20–28), e **non risulta approvato dal relatore**: va presentato come esplorativo.

**Scelta per la tesi (revisione del 17 novembre).** D→C→K, RQ2-A e la lettura qualitativa dei testi sono il
corpo di RQ2. L1/L2 diventa una **sezione breve dentro il capitolo RQ2**, che mostra che *generare ≠ validare*;
il protocollo (freeze, addendum, L2a/L2b) va in appendice. Le soglie (H_pre = 60 s, H = 300 s, 2/3 di copertura
dei negativi, criteri di ammissione) sono **convenzioni di progetto**, non tolleranze dello scorer Microsoft né
valori derivati dai dati. La conferma col relatore di quale lettura corrisponda all'accordo resta un punto
aperto (sez. 8).

**Chi fa il trasferimento (rilettura della trascrizione, 17 novembre).** Nelle tre parti la seconda domanda è
sempre posta *a valle* della prima: individuare errori non codificati è condizionato a richieste rese più
precise dall'harnessing (REGIS 1, "se migliorano le richieste"), e il caso nuovo viene passato all'agente
"con l'harnessing" una volta dimostrato che l'harnessing migliora la RCA (REGIS 3). A0 non è nominato in nessuna
formulazione di RQ2 e nessuna lo esclude. **Scelta** (decisione di Claude; lettura da confermare col
relatore): il trasferimento di conoscenza è attribuito all'agente con harness; A0, già eseguito con la stessa
pipeline D→C→K e sugli stessi dati, è riportato come **condizione di riferimento**, senza cancellare né
rieseguire nulla. Non si afferma che l'harness sia necessario per generare candidate: A0 ne produce 4 su 12
stage K, le varianti con harness 4 su 48 (sez. 3.2). L'idea di REGIS 1 di far migliorare l'agente nel tempo con
cicli successivi di esempi non ricompare in REGIS 3, non è stata eseguita ed è lavoro futuro.

**Conclusione proposta per RQ2 (testo da confermare).** Su 8 candidate (4 di A0, 4 delle varianti con harness)
nessuna risulta verificata: 7 non sono formalizzabili o classificabili in L1 e l'unica formalizzabile, di
A1_8R_Planning, ha 2 falsi positivi su 7 gruppi negativi in L2 (`NON_VERIFICATA`, n = 1). L'output dell'agente
non può quindi essere promosso in automatico a regola: servono una verifica deterministica e, per ciò che questa
non decide, un supervisore umano, come nella pipeline descritta dal relatore (lavoro futuro, non implementata).
Questo motiva la supervisione, **non dimostra** che serva un essere umano piuttosto che un controllo più
ricco, e non è un risultato sull'harness. Il confronto con l'attesa del relatore ("l'agente riesce a spiegare
anche cose che non ha visto") va riportato per quello che è: nei dati di RQ2-A la diagnosi vale 0 salvo un
caso (orario di q026, solo modelli Claude con harness), e il testo del passo C non viene abbinato alla classe in
60 su 60 con lo strumento, con 6 su 60 chiari nella lettura qualitativa post hoc (tutti Sonnet).

---

## 5. Proposta di indice della tesi

Spazio predominante a RQ1 e a RQ2; L1/L2 come sezione breve del capitolo RQ2 (revisione del 17 novembre).
Le percentuali sono indicative.

1. **Introduzione** (≈5%): contesto, problema, domande RQ1 e RQ2, contributi, struttura.
2. **Background e stato dell'arte** (≈10%): RCA nei sistemi a microservizi; OpenRCA 1.0 e il sistema Market;
   RCA-agent Microsoft; OpenRCA 2.0 e PAVE come fonte dei principi di verifica; agenti LLM, ReAct, uso di
   strumenti; Harness Engineering.
3. **Benchmark e protocollo sperimentale** (≈8%): 148 query, 15 cause, 7 task; scorer ufficiale; coorti
   (development 8, evaluation 20, discovery 4, sigillati 11); selezione GT-free; preregistrazione, record
   create-only, hash; modelli e provider.
4. **Progettazione dell'harness** (≈12%): A0, A1, A1_8R, A1_8R_Planning, A1_PAVE; evidenze deterministiche;
   le otto regole e le 15 classi (con le tre non coperte); planner; contesto strutturale-temporale;
   contratto di output V2.
5. **RQ1 — risultati** (≈18%): development; EVALUATION20; ablazioni appaiate; efficienza; confronto
   contestuale con l'archivio Microsoft; analisi dei limiti.
6. **RQ2 — D→C→K** (≈28%): le quattro classi; pipeline e contratti; politica di formato V5.1; matrice di 180
   stage; risultati (60 K, 8 candidate, 49, 3); analisi delle 8 candidate e della loro formalizzabilità; RQ2-A
   (scoring offline di D e C, con i limiti dello strumento) e lettura qualitativa dei testi liberi, con il confronto
   tra modelli sul livello di dettaglio delle spiegazioni (≈8%); **sezione breve su L1/L2** (≈4%): esito
   `NON_VERIFICATA`, limite sui nomi, *generare ≠ validare*.
7. **Discussione e minacce alla validità** (≈9%): campioni piccoli, una replica, dipendenza dal provider,
   decisioni a posteriori dichiarate (politica di formato), confronto retrospettivo, codice scritto con un modello
   che è anche valutato, strumenti di misura che non vedono l'identificazione della classe.
8. **Lavoro futuro** (≈7%): pipeline human-in-the-loop e architettura duale (solo concetto, con il rapporto
   illustrativo della sez. 1.4 etichettato come illustrazione), tabella di corrispondenza dei nomi, estensione
   dell'esecutore a log/trace/servizio, repliche, classi restanti, OpenRCA 2.0.
9. **Conclusioni** (≈3%).

**Appendici:** tabella delle 8 candidate; protocollo L1/L2 (freeze, addendum, L2a/L2b, parametri come convenzioni
di progetto); testi liberi di D e C per i 4 casi (CSV); commit, hash e artefatti (sez. 7); mappa del codice e
istruzioni di riproduzione; registro delle decisioni (`REGISTRO_DECISIONI_RQ2.md`).

---

## 6. Codice: che cosa serve davvero e che cosa è forse superfluo (nessuna cancellazione)

**Metodo.** Grafo statico degli `import` su `src/` (156 moduli non di test), a partire dai punti d'ingresso
che hanno prodotto i risultati: esecutori e preregistrazione RQ1/EVALUATION20 (`experiment_*`,
`evaluation20_*`), il run RQ2 V5 (`rq2_v5_run_cli` e dipendenze), il filone K (`rq2_k_*`), i caricatori OOD e
l'audit delle finestre (`ood_class_inventory`, `ood_holdout_preflight`, `v2_case_window_audit`), i grafi e i
tool dell'agente, le otto regole (caricate con `import_module`). Limiti: gli import dinamici diversi da
quelli di `rule_batch` e i moduli lanciati da celle Colab non sono visibili al grafo. **"Fuori dal nucleo"
significa "non necessario al codice finale", non "eliminabile".**

| Gruppo | Moduli | Righe | Indicazione |
|---|---:|---:|---|
| **A. Nucleo del codice finale** (chiusura degli import dai punti d'ingresso) | 98 | 25.868 | Da mantenere e documentare |
| B1. Campagne e audit RQ1 storici (V2, paired, Claude development) | 9 | 2.852 | Conservare: hanno prodotto o verificato risultati citabili |
| B2. Audit e preflight in sola lettura (OOD, RQ2, sorgenti, discovery) | 12 | 2.379 | Conservare: documentano le decisioni di protocollo |
| C1. Script manuali una tantum (`manual_*`) | 5 | 414 | Candidati all'archivio |
| C2. RQ2 pre-V5: ledger e dispatcher V2/V3/V4, pilot Sonnet, sonde LangChain/SDK, mock, prototipi | 32 | 9.707 | Candidati all'archivio; superati dal runner V5 |
| **Totale fuori dal nucleo** | **58** | **15.352** | |

Test: 145 file in `src/tests/` e 4 in `tests/` (EVALUATION20). Vanno conservati, anche per i moduli dei
gruppi B e C, perché fissano il comportamento dei risultati storici. Altro: 201 file in `docs/` (di cui 169 in
`docs/ood/`) e 12 notebook in `notebooks/` (più un README): sono celle Colab di preflight e audit, non
analizzate dal grafo, da conservare.

**Attenzione ai nomi.** Nel nucleo ci sono moduli `rq2_v2_*`, `rq2_v3_*`, `rq2_v4_*` (19 in tutto): il run V5
riusa senza modifiche le parti pure V4 (piano, contratti, ponte V3, normalizzatori di ricevuta). Il suffisso
di versione non indica obsolescenza.

**Proposta di intervento (da approvare dopo la revisione, nessun intervento in questo commit):**
1. Nessuno spostamento, nessuna ridenominazione e nessuna cancellazione di moduli in questa fase: i percorsi
   compaiono nei record, negli addendum e negli hash.
2. Refactoring essenziale sul solo gruppo A: mappa dei moduli e README del codice finale; commenti e
   docstring in italiano sui file **non** bloccati (sez. 7.2), senza toccare stringhe dei prompt, nomi API,
   identificativi del benchmark, etichette dei guasti.
3. I gruppi B e C restano dove sono e sono elencati in appendice come "storici/archiviabili". Un eventuale
   spostamento in `archive/` si decide dopo la consegna.
4. Per ogni modifica, test mirati; i test completi su PyCharm prima del commit.

L'elenco completo dei moduli, per gruppo, è nell'Appendice A.

**Stato dei branch (verificato su GitHub con `ls-remote`).** 36 branch remoti. Il commit `ddb2ca4` è la testa
di `release/rq2-v5.1-discovery-v1`; `e4845e7` (provenienza EVALUATION20) è la testa di
`feature/evaluation20-gtfree-preflight-2026-11-06`; `5b51b32` era la testa del branch attuale. Il commit
`6747eecc…` (RQ1 development V3) esiste su GitHub ed è antenato di `feature/evaluation20-gtfree-preflight-2026-11-06`,
ma **non** è nella storia del branch attuale. Nel confronto tra alberi di file, rispetto a `e4845e7` il branch
attuale ha **397 file aggiunti e 0 modificati o cancellati**; rispetto a `ddb2ca4`, 25 file aggiunti e 1
modificato (`docs/REGISTRO_DECISIONI_RQ2.md`). Quindi il codice che ha prodotto EVALUATION20 e il run V5.1 è
presente, byte per byte, nel branch attuale. Il clone usato per la verifica è *shallow*: i controlli sulla
storia (antenati) sono stati fatti dopo aver scaricato i branch interessati.

---

## 7. Da non modificare durante il refactoring

### 7.1 Commit di riferimento

| Commit | Ruolo | Verificato |
|---|---|---|
| `6747eecc77c1b2fff7d581c7284578b5c574b4f7` | Codice congelato RQ1 development V3 (3 novembre) | Esiste su GitHub; non nella storia del branch attuale |
| `e4845e7fe9a399e10dd2db6f320dfeaeeddf3379` | Provenienza EVALUATION20 (300 tentativi) | Testa di `feature/evaluation20-gtfree-preflight-2026-11-06`; contenuto interamente presente nel branch attuale |
| `2a481ae63cb045c3eadbeca9eddaa10ec1151979` | Scorer ufficiale Microsoft (`main/evaluate.py`), repository esterno | Citato dai report; non nel nostro repository |
| `ddb2ca499c4b41aa32a36fdc2f9850cb09bb75c3` | Codice del run V5.1 di discovery (180 stage); `source_commit` di tutti i record | Testa di `release/rq2-v5.1-discovery-v1`; antenato del branch attuale |
| `88e46580c38dd89cbfae8076ba0752776c1c12b5` | Codice del freeze L1/L2 (L1 eseguito qui) | Antenato del branch attuale |
| `c5dafb5425122eb942946d8ad7b2423cd36124ab` | Codice L2 definitivo (`l2_code_commit` dell'addendum) | Antenato del branch attuale |
| `57ed7a9a0d8747f88852f7131cc69d06b5b37af1` | Commit su cui è stata eseguita L2a | Antenato del branch attuale |
| `ce10737371e8a94b3fe54afc97b39ed52cf1983e` | Commit su cui è stata eseguita L2b | Antenato del branch attuale |
| `5b51b3286d3354252e9b41e0f1e1f6b1d5c2ba47` | Documento di esito L2 (base di questo documento) | Era la testa del branch attuale su GitHub |

Proposta (non eseguita): creare tag annotati su questi commit prima di scrivere il capitolo di riproducibilità.
Non cancellare né riscrivere la storia dei branch citati (niente rebase o force-push).

### 7.2 Sorgenti bloccati da hash (13 file): non modificare nemmeno un carattere

Gli hash sono in `freeze.json` (6 sorgenti) e `l2_addendum.json` (2 moduli L2 + 10 caricatori); i test
`IsolationTests` e il controllo di L2b li verificano. **Tradurre i commenti in italiano cambierebbe
l'hash**: questi file sono quindi esclusi dal refactoring dei commenti. Verifica eseguita per questo
documento: i 13 file nel commit attuale e nell'albero di lavoro hanno esattamente questi SHA-256; i 6
sorgenti del freeze sono identici anche a `88e4658`. Gli hash vanno ricalcolati su un checkout Linux/Colab,
non su Windows con conversione degli a-capo.

| File (sotto `src/`) | SHA-256 |
|---|---|
| `evaluation/rq2_k_l1_preflight.py` | `673ab046419f8866665c83b383c22f41a072efdbb1d89a7a92b6ea3d07953e46` |
| `evaluation/rq2_k_l1_protocol.py` | `8de0ab363bad887512e6cd2811045210f709b569ad8e714092114306f7991065` |
| `evaluation/rq2_k_records.py` | `3a0a1641dfd6cef7660ab75794b0518462f8391e969e4326f024ed3eb3451982` |
| `evaluation/rq2_k_rule_evaluation.py` | `43b1dd98379ff49a50ccabada609b2e05ae4193a57bad03f4a5828fd2acda5de` |
| `evaluation/rq2_k_rule_executor.py` | `ed105d707dabb91f700409565fb55f075fa474fb0b712129a3d5798c1c3df1d8` |
| `evaluation/rq2_rule_group_scorer.py` | `c66c921d6b7e9d7274a2cedd2f7092976818b44cd3b08755c344b044648a6020` |
| `evaluation/rq2_k_l2_execute.py` | `1b79ed35068b12b906371e7950badd3926be6e7ad03f86859303fa04c7d371e4` |
| `evaluation/rq2_k_l2_scoring.py` | `6287f51abf0dbbec1d19d2eb3f7094063a542fdfc5f717a6eea40c19d7eec388` |
| `agent/tools.py` | `ec677c2f26d36109df3a6c614f5903333ddaa1b9e13e8c2cce844e5de464fab0` |
| `evaluation/ood_class_inventory.py` | `548b9fdcdb87f00a9c5bf917c17e0abbde08b97b5732c26d632903f761a55d81` |
| `evaluation/ood_holdout_preflight.py` | `10d4f328e530753c1b6b2805bf3ed6302e7291b1be148620c2cbdd848bd515d7` |
| `evaluation/rq2_k_catalog.py` | `c11d8b96f7210f6249ab9e8760d653e7442f14c2250263e48e3b08f2bc38e11f` |
| `evaluation/v2_case_window_audit.py` | `ebddc1312543e5b8eb8847c1c4267549681b895dbad93e82b4685abc501b68f0` |

### 7.3 Codice del run V5.1 (bloccato per commit, non per hash)

I moduli `rq2_v5_*` e le parti V2–V4 che importano hanno prodotto i 180 record con `source_commit =
ddb2ca4`. Dal run, nessun file di `src/` è stato modificato (verificato: `ddb2ca4` → branch attuale, solo
file aggiunti). Regola: nessun cambiamento di comportamento; sono ammessi solo commenti e docstring, su un
branch separato, con un test di equivalenza, e mai sulle stringhe dei prompt, sui contratti e sugli
identificativi. In caso di dubbio non toccare.

### 7.4 Artefatti e hash (Drive, create-only)

| Artefatto | SHA-256 |
|---|---|
| `data/rq2_k_freeze_v1/freeze.json`: corpo | `38d23b4c8b4369fafd4e145107e21260403b9ba4601e361031cd533b2fd8ea78` |
| `freeze.json`: file | `c926472819d0182032f84bbe19204174bda18817d7c7716ed4a0bcb223f8a12c` |
| Tabella semantica v1 | `642b9d2c5f3bfd1b6bb70fe93d4410e142b0addf99c301ce34055ee87289c981` |
| Parametri L1/L2 | `7875e28f6075eb6e6b1ff3b29f963a06b38dbbc933bfe453fb54041f656a5ce0` |
| Catalogo KPI | `d357a8371e276822c398d8296ee27ed67e26079643bf0eb3ec428840e6c480a6` |
| Impronta dei 180 record del run | `94e07d606b983aa06120238605eaeedf90eeb4be7abfc4ae3a5850edde2c7b4a` |
| Anteprima del piano | `ddba5cd92795e92e196d69cd5cc13df85eec91e9c18913561356f268127deec7` |
| `l1_report.json`: file | `7ee1bbb2dca015162e48a652c4d557bb80b017df93f486cae9dca2152c7abd4f` |
| `l2_addendum.json`: corpo | `337238327c3c9f880e85774018875c99149dc09959ef641597bcb2562ac189b1` |
| Elenco dei 10 gruppi | `d03c0920b6b373cfda9d5311962420debef4f43ef7e0e8f8ba4b878104de1ed2` |
| Release dei sigillati | `a35c02f830a3c5f97424e0cbf8653eda6cfa674b9c8c34d95d04627e1dba8c52` |
| Manifest delle finestre | `5fabd40123aaa8bb614bb812f2994c776967b9b04ec3bfe477f89c1dde614d13` |
| `l2a_decisions.json`: corpo (decisioni `0115f025f01bbd03`) | `2f418969b57f42a87439057f42784d95b2702be8b06ad28b41dc552aa2281be1` |
| `l2b_evaluation.json`: corpo | `a32f170701802d65268f8e27d7dd9cd680aa4ab140895b9f590957d2728000d3` |
| EVALUATION20: freeze delle inferenze | `f53effaa81fada14bab31b50ba0983e3642ff818294ac43550587e6982e4ee5f` |
| EVALUATION20: inventario | `c12257a0ba87502090121c6393182f5f94a22ef08cef8fadbb853c4bb5addd18` |
| EVALUATION20: report di scoring | `d2f7f6495a36c89664cb6cd864bc0f59dd55b4aa18cee29032b1d0c81748d780` |
| EVALUATION20: sorgente dello scorer | `9a1c235139266c32b0e95c7e9938591b8fe014aad4cde95580f73f13a54d53f1` |
| Confronto ufficiale development a tre modelli | `975ff3b8f28aea16a94a9ca8cb1e69c36c7bdf818d855c1c4be274c34ab76e71` |

Anche non modificabili: l'intero namespace `data/rq2_v5_format_fair_v1/` (180 record, 180 claim, 
`manifest_v1.json`), le 900 coppie claim/risultato/hash di EVALUATION20 e i file di scoring sotto
`data/results/scoring/v2/`. Il hash del *piano* di EVALUATION20 nella relazione del 9 novembre è troncato
nel testo estratto dal PDF: va riletto dal file originale prima di citarlo.

### 7.5 Risultati scientifici da non toccare, compresi quelli negativi

- RQ2: 180 stage; 60 K; **8 candidate / 49 `insufficient_evidence` / 3 non validi strict**; i 3 non validi
  restano non validi (nessuna riparazione).
- L1: 3 eseguibili, 1 FORMALIZZABILE, 2 NON_CLASSIFICABILI, 5 NON_FORMALIZZABILI.
- L2: **`NON_VERIFICATA`**, TP 0 FN 0 TN 5 FP 2; 3 positivi non osservabili; il limite sui nomi resta un limite
  dichiarato, non una correzione.
- RQ1: tutta la tabella di EVALUATION20, compresi i risultati peggiori (Gemini A0: 0 strict; Haiku A1 e A1_8R:
  3 strict ciascuna ma nessuna anche conforme a V2), i 5 errori 503 trattati come mancanti e la tabella V3
  development (A0 0/8, A1_PAVE 1/8).
- Nessun nuovo calcolo "migliorativo", nessuna riclassificazione retrospettiva, nessun nuovo protocollo.

### 7.6 Regole per il refactoring

1. Mai riscrivere record, claim, manifest, report o file di scoring.
2. Mai toccare i 13 file della sez. 7.2.
3. Nessuno spostamento o ridenominazione di moduli, per ora.
4. Prima di ogni commit: `python -m compileall -q src` e i test mirati; la suite completa su PyCharm
   (`PYTHONPATH=src:src/tests`).
5. Il refactoring va su un branch separato dal branch dei risultati.

---

## 8. Concluso e ancora aperto prima della consegna

**Concluso:** esperimenti RQ1 (approvati il 10 novembre); run RQ2 D→C→K; L1; L2a/L2b; documento di esito L2;
RQ2-A (scoring offline di D e C, 17 novembre) e lettura qualitativa dei testi liberi; registro delle decisioni
(righe 1–34); questo consolidamento.

**Aperto, in ordine di dipendenza:**
1. Revisione di questo documento (GPT supporta, decide Claude con Alessio).
2. **Data di consegna: 5 dicembre 2026**, confermata da Alessio il 17 novembre (registro riga 34). Il "1 dicembre"
   delle versioni precedenti di questo documento era un errore e non va più usato.
3. Punto da concordare col relatore: come presentare RQ2 (risultato centrale = D→C→K con RQ2-A) e L1/L2
   (sezione breve, esplorativa); la lettura della riga 1 del registro (sez. 4); se candidata + spiegazione +
   pseudocodice, con la verifica umana come lavoro futuro, basta per RQ2. La domanda è da scrivere come bozza,
   senza inviarla.
3b. Due analisi offline in sola lettura, **eseguite il 17 novembre** (registro righe 35–38): la stratificazione di
   RQ1 per copertura (sez. 3.1b) e il controllo di separazione (0 delle quattro classi in development e
   evaluation). I 5 incidenti non coperti sono tutti di rete (registro riga 40).
4. Refactoring essenziale (sez. 6): al più due giorni.
5. Ricostruzione delle tre classi di guasto non coperte (sez. 1.1) e, se serve, ricontrollo del confronto
   con l'archivio Microsoft (cella Colab già predisposta).
6. Scrittura della tesi (indice in sez. 5).

**Calendario proposto (consegna il 5 dicembre; numerazione dei capitoli come in sez. 5):**

| Periodo | Attività |
|---|---|
| 17–19 nov | Revisione di questo documento; refactoring essenziale su branch separato (sez. 6); intanto, capitoli 1–2 |
| 19–22 nov | Capitoli 3–4 (benchmark e harness) |
| 22–26 nov | Capitolo 5 (RQ1) |
| 26–30 nov | Capitolo 6 (RQ2: D→C→K, RQ2-A, sezione breve L1/L2) |
| 30 nov–2 dic | Capitoli 7–9, appendici, figure e bibliografia |
| 2–4 dic | Revisione completa; controllo dei numeri e degli hash contro questo documento; correzioni |
| 5 dic | Consegna |

Il relatore va informato prima dei capitoli 5 e 6 (RQ1 e RQ2), che sono quelli con più interpretazione. Il
calendario ha circa tre giorni di margine tra la fine della scrittura e la consegna.

---

## 9. Che cosa è stato verificato per questo documento

**Verificato da fonti primarie, in questa sessione:**
- La tabella delle 8 candidate e il freeze: letti da `freeze.json` su Drive.
- L'addendum L2 e gli hash dei 13 sorgenti: letti da `l2_addendum.json`; hash ricalcolati sul commit attuale
  e sull'albero di lavoro (13/13 uguali) e sui 6 sorgenti del freeze a `88e4658` (6/6).
- I conteggi di K (8/49/3), i 3 non validi per cella e le formattazioni: dal registro (righe 13, 15, 19).
- Commit e branch: `git ls-remote`, `git merge-base`, confronto degli alberi con `git diff --name-status`.
- La tabella V3: da `docs/ARCHITETTURA_E_RISULTATI_V3.md`.
- Moduli e righe: analisi statica con `ast` su 156 moduli.

**Verificato il 17 novembre (RQ2-A):** il report `data/rq2_a_offline_v1/report.json` è stato riletto da Drive:
i punteggi di D per modello e harness, i 12 pareggi A1_8R contro A1, le 13 astensioni di C (Gemini 10, Haiku 3,
Sonnet 0) e le 47 diagnosi non mappate, le classi vere dei 4 casi, `provider_calls` 0 e `records_read` 120, gli hash
dello scorer ufficiale. Il modulo di scoring ha 11 test sintetici superati (commit `6c8ca00` e `ab0b62f`, pushati).
**Non verificato:** la lettura qualitativa della sez. 1.2c è mia, post hoc e non cieca; il componente vero di
q045 e le traiettorie degli strumenti di q050 e q045 (necessarie per le due ipotesi della sez. 1.2c); che nessun
incidente delle quattro classi sia nei gruppi development o evaluation di RQ1 (l'audit GT ha coperto solo il gruppo
OOD).

**Trascritto da documenti, non ricalcolato:** la tabella di EVALUATION20 e le ablazioni (relazione del 9
novembre su Drive). Le somme per modello e il totale (295 run, 41 strict, 28 strict+V2, 215 conformi) sono
stati controllati aritmeticamente.

**Non verificato:** l'esito del ricontrollo Colab del confronto con l'archivio Microsoft; l'esistenza di
un'approvazione del relatore sul protocollo L1/L2; le tre classi di guasto non coperte; i numeri di `dev8`
(citati solo per hash); la presenza del commit `6747eec` nella storia delle altre branch; che
`rq2_v5_run_cli summary` confermi le 49 `insufficient_evidence` per cella.

---

## Appendice A — Moduli per gruppo

Fonte: grafo degli import (`ast`), 156 moduli non di test sotto `src/`. Colonne: righe di codice, numero di moduli che lo
importano, presenza di un blocco `__main__`, numero di file di test che citano il nome del modulo. I moduli con importato-da 0 e senza
`__main__` non sono per questo inutili (le otto regole vengono caricate con `import_module`).

### A.1 Nucleo del codice finale (gruppo A, 98 moduli)

**Agente (grafi, prompt, tool)** (8 moduli, 2.479 righe)

| Modulo | Righe | Importato da | `__main__` | File di test |
|---|---:|---:|:-:|---:|
| `agent/graph_engine.py` | 410 | 10 |  | 19 |
| `agent/model_factory.py` | 69 | 6 |  | 12 |
| `agent/prompts.py` | 170 | 3 | sì | 3 |
| `agent/rq2_v2_graph_engine.py` | 158 | 3 |  | 10 |
| `agent/tool_factory.py` | 207 | 1 |  | 0 |
| `agent/tools.py` | 918 | 4 |  | 23 |
| `agent/variant_names.py` | 82 | 4 |  | 2 |
| `agent/verify_graph.py` | 465 | 4 |  | 10 |

**Contratti di output** (4 moduli, 783 righe)

| Modulo | Righe | Importato da | `__main__` | File di test |
|---|---:|---:|:-:|---:|
| `output/openrca_contract.py` | 150 | 10 |  | 5 |
| `output/structured_finalizer.py` | 232 | 2 |  | 2 |
| `output/v2_contract.py` | 167 | 5 |  | 3 |
| `output/v2_task_contract.py` | 234 | 5 |  | 6 |

**Harness (evidenze, regole, planner, verificatori)** (24 moduli, 6.557 righe)

| Modulo | Righe | Importato da | `__main__` | File di test |
|---|---:|---:|:-:|---:|
| `harness/anomaly_detector.py` | 385 | 1 |  | 0 |
| `harness/evidence_builder.py` | 803 | 1 |  | 0 |
| `harness/evidence_selector.py` | 347 | 1 |  | 0 |
| `harness/evidence_summarizer.py` | 496 | 1 |  | 0 |
| `harness/investigation_planner.py` | 251 | 1 |  | 1 |
| `harness/mesh_runtime_detector.py` | 972 | 1 |  | 0 |
| `harness/metric_quality.py` | 84 | 1 |  | 0 |
| `harness/observational_verifier.py` | 201 | 2 |  | 1 |
| `harness/preprocessor.py` | 101 | 1 |  | 0 |
| `harness/rule_batch.py` | 204 | 3 |  | 1 |
| `harness/rules/_node_rule_common.py` | 124 | 0 |  | 0 |
| `harness/rules/rule_container_cpu.py` | 187 | 0 |  | 1 |
| `harness/rules/rule_container_memory.py` | 214 | 0 |  | 1 |
| `harness/rules/rule_container_read_io.py` | 192 | 0 |  | 1 |
| `harness/rules/rule_node_cpu_load.py` | 12 | 0 |  | 1 |
| `harness/rules/rule_node_disk_space.py` | 16 | 0 |  | 1 |
| `harness/rules/rule_node_memory.py` | 12 | 0 |  | 1 |
| `harness/rules/rule_node_read_io.py` | 56 | 0 |  | 1 |
| `harness/rules/rule_node_write_io.py` | 52 | 0 |  | 1 |
| `harness/signal_catalog.py` | 522 | 3 |  | 0 |
| `harness/structural_patterns.py` | 99 | 1 |  | 0 |
| `harness/structural_temporal_verifier.py` | 354 | 2 |  | 8 |
| `harness/topology.py` | 67 | 1 |  | 0 |
| `harness/unified_report.py` | 806 | 1 |  | 0 |

**RQ1 e EVALUATION20 (runner, preregistrazione, coorti, audit finestre, OOD)** (10 moduli, 3.515 righe)

| Modulo | Righe | Importato da | `__main__` | File di test |
|---|---:|---:|:-:|---:|
| `evaluation/evaluation20_campaign.py` | 478 | 0 | sì | 1 |
| `evaluation/evaluation20_preflight.py` | 247 | 1 | sì | 2 |
| `evaluation/evaluation20_preregister.py` | 265 | 1 | sì | 3 |
| `evaluation/experiment_config.py` | 218 | 17 | sì | 16 |
| `evaluation/experiment_runner.py` | 1145 | 12 |  | 18 |
| `evaluation/ood_class_inventory.py` | 256 | 4 | sì | 2 |
| `evaluation/ood_holdout_preflight.py` | 169 | 4 | sì | 1 |
| `evaluation/v2_case_window_audit.py` | 218 | 14 | sì | 3 |
| `evaluation/v2_cohort_selector.py` | 329 | 3 | sì | 2 |
| `evaluation/v2_preregister.py` | 190 | 3 | sì | 2 |

**RQ2 K (esecutore, L1/L2, audit)** (11 moduli, 3.023 righe)

| Modulo | Righe | Importato da | `__main__` | File di test |
|---|---:|---:|:-:|---:|
| `evaluation/rq2_k_catalog.py` | 269 | 4 | sì | 4 |
| `evaluation/rq2_k_l1_preflight.py` | 465 | 2 | sì | 2 |
| `evaluation/rq2_k_l1_protocol.py` | 457 | 2 | sì | 2 |
| `evaluation/rq2_k_l2_execute.py` | 441 | 1 | sì | 1 |
| `evaluation/rq2_k_l2_scoring.py` | 280 | 0 | sì | 1 |
| `evaluation/rq2_k_records.py` | 92 | 3 |  | 1 |
| `evaluation/rq2_k_rule_evaluation.py` | 227 | 1 |  | 3 |
| `evaluation/rq2_k_rule_executor.py` | 301 | 3 |  | 3 |
| `evaluation/rq2_k_rule_inventory.py` | 70 | 0 | sì | 1 |
| `evaluation/rq2_k_run_audit.py` | 124 | 0 | sì | 1 |
| `evaluation/rq2_k_run_integrity.py` | 297 | 1 | sì | 2 |

**RQ2 V5 (run di discovery)** (5 moduli, 1.331 righe)

| Modulo | Righe | Importato da | `__main__` | File di test |
|---|---:|---:|:-:|---:|
| `evaluation/rq2_v5_matrix_runner.py` | 545 | 3 |  | 6 |
| `evaluation/rq2_v5_response_normalization.py` | 161 | 2 |  | 2 |
| `evaluation/rq2_v5_retry.py` | 94 | 2 |  | 2 |
| `evaluation/rq2_v5_run_cli.py` | 259 | 2 | sì | 3 |
| `evaluation/rq2_v5_stage_executor.py` | 272 | 1 |  | 3 |

**RQ2 catena V2 (piano unificato, ledger, release)** (11 moduli, 2.590 righe)

| Modulo | Righe | Importato da | `__main__` | File di test |
|---|---:|---:|:-:|---:|
| `evaluation/rq2_v2_ck_provider_transport_candidate.py` | 107 | 3 |  | 5 |
| `evaluation/rq2_v2_ck_text_extraction_candidate.py` | 61 | 6 |  | 10 |
| `evaluation/rq2_v2_unified_discovery_plan.py` | 229 | 12 |  | 16 |
| `evaluation/rq2_v2_unified_live_stage_preflight.py` | 220 | 5 |  | 2 |
| `evaluation/rq2_v2_unified_provenance_gate.py` | 130 | 6 |  | 4 |
| `evaluation/rq2_v2_unified_provider_result_adapter.py` | 250 | 5 |  | 5 |
| `evaluation/rq2_v2_unified_release_blueprint.py` | 211 | 3 |  | 13 |
| `evaluation/rq2_v2_unified_release_preflight.py` | 208 | 5 |  | 6 |
| `evaluation/rq2_v2_unified_scientific_ledger.py` | 783 | 17 |  | 17 |
| `evaluation/rq2_v2_unified_scientific_ledger_preflight.py` | 188 | 12 |  | 2 |
| `evaluation/rq2_v2_unified_scientific_release_contract.py` | 203 | 1 |  | 11 |

**RQ2 catena V3 (piano, ponte D, ricevute)** (5 moduli, 999 righe)

| Modulo | Righe | Importato da | `__main__` | File di test |
|---|---:|---:|:-:|---:|
| `evaluation/rq2_v3_ck_provenance_receipt_candidate.py` | 164 | 2 |  | 2 |
| `evaluation/rq2_v3_d_final_stream_candidate.py` | 162 | 3 |  | 3 |
| `evaluation/rq2_v3_d_runner_capture_candidate.py` | 134 | 5 |  | 4 |
| `evaluation/rq2_v3_scientific_receipt_adapter_candidate.py` | 345 | 3 |  | 3 |
| `evaluation/rq2_v3_unified_gtfree_discovery_plan.py` | 194 | 8 |  | 8 |

**RQ2 catena V4 (piano, contratti, ricevute)** (3 moduli, 533 righe)

| Modulo | Righe | Importato da | `__main__` | File di test |
|---|---:|---:|:-:|---:|
| `evaluation/rq2_v4_d_task_aware_contract.py` | 181 | 4 |  | 3 |
| `evaluation/rq2_v4_scientific_receipt_adapter_candidate.py` | 234 | 3 |  | 1 |
| `evaluation/rq2_v4_unified_gtfree_discovery_plan.py` | 118 | 6 |  | 5 |

**RQ2 moduli comuni (budget, contratti, bundle, probe, store)** (17 moduli, 4.058 righe)

| Modulo | Righe | Importato da | `__main__` | File di test |
|---|---:|---:|:-:|---:|
| `evaluation/rq2_budget_preflight.py` | 244 | 9 |  | 18 |
| `evaluation/rq2_ck_provider_transport.py` | 295 | 5 |  | 6 |
| `evaluation/rq2_discovery_claim_journal.py` | 251 | 4 |  | 5 |
| `evaluation/rq2_discovery_stage_recorder.py` | 390 | 3 |  | 2 |
| `evaluation/rq2_dryrun_plan.py` | 283 | 17 | sì | 8 |
| `evaluation/rq2_evidence_bundle.py` | 255 | 14 |  | 10 |
| `evaluation/rq2_kpi_formalizability_preflight.py` | 188 | 4 |  | 1 |
| `evaluation/rq2_model_factory.py` | 81 | 14 |  | 7 |
| `evaluation/rq2_output_contracts.py` | 239 | 14 |  | 10 |
| `evaluation/rq2_probe_adapter.py` | 194 | 14 |  | 12 |
| `evaluation/rq2_protocol_identity_preflight.py` | 181 | 4 | sì | 1 |
| `evaluation/rq2_provider_policy_source_audit.py` | 185 | 10 | sì | 11 |
| `evaluation/rq2_rule_group_scorer.py` | 188 | 1 |  | 3 |
| `evaluation/rq2_sdk_retry_mock_probe.py` | 207 | 3 | sì | 2 |
| `evaluation/rq2_stage_artifact_store.py` | 387 | 2 |  | 4 |
| `evaluation/rq2_stage_binding.py` | 260 | 20 |  | 5 |
| `evaluation/rq2_toolfree_fake_transport.py` | 230 | 1 |  | 2 |

### A.2 Campagne e audit RQ1 storici (gruppo B1)

9 moduli, 2.852 righe.

| Modulo | Righe | Importato da | `__main__` | File di test |
|---|---:|---:|:-:|---:|
| `evaluation/claude_development_campaign.py` | 602 | 1 | sì | 1 |
| `evaluation/claude_development_freeze.py` | 97 | 0 | sì | 1 |
| `evaluation/paired_cohort.py` | 179 | 2 |  | 2 |
| `evaluation/paired_runner.py` | 417 | 1 |  | 1 |
| `evaluation/paired_st_cohort.py` | 180 | 1 | sì | 1 |
| `evaluation/paired_st_runner.py` | 428 | 1 |  | 0 |
| `evaluation/v2_campaign_runner.py` | 416 | 0 | sì | 1 |
| `evaluation/v2_frozen_prediction_audit.py` | 343 | 0 | sì | 1 |
| `harness/hypothesis_coverage_audit.py` | 190 | 1 |  | 1 |

### A.3 Audit e preflight in sola lettura (gruppo B2)

12 moduli, 2.379 righe.

| Modulo | Righe | Importato da | `__main__` | File di test |
|---|---:|---:|:-:|---:|
| `evaluation/ood_dependency_sensitivity.py` | 161 | 0 | sì | 1 |
| `evaluation/ood_source_schema_audit.py` | 98 | 0 | sì | 1 |
| `evaluation/rq2_development_kpi_audit.py` | 307 | 1 | sì | 1 |
| `evaluation/rq2_discovery_prereg_readiness.py` | 198 | 0 | sì | 0 |
| `evaluation/rq2_fault_type_eval_policy.py` | 199 | 0 |  | 4 |
| `evaluation/rq2_historical_trajectory_audit.py` | 138 | 0 | sì | 1 |
| `evaluation/rq2_partition_preview.py` | 158 | 0 | sì | 1 |
| `evaluation/rq2_partition_preview_v1.py` | 256 | 0 | sì | 1 |
| `evaluation/rq2_q045_development_log_audit.py` | 269 | 0 | sì | 1 |
| `evaluation/rq2_source_bound_d_preflight.py` | 223 | 2 | sì | 2 |
| `evaluation/rq2_v1_gemini_readonly_audit.py` | 206 | 0 | sì | 1 |
| `evaluation/rq2_v5_fence_audit_readonly.py` | 166 | 0 | sì | 0 |

### A.4 Script manuali una tantum (gruppo C1)

5 moduli, 414 righe.

| Modulo | Righe | Importato da | `__main__` | File di test |
|---|---:|---:|:-:|---:|
| `evaluation/manual_offline_real_evidence_audit.py` | 141 | 0 |  | 0 |
| `evaluation/manual_paired_batch.py` | 73 | 0 | sì | 0 |
| `evaluation/manual_paired_st_batch.py` | 73 | 0 | sì | 0 |
| `evaluation/manual_preregister_dev.py` | 69 | 0 | sì | 0 |
| `evaluation/manual_smoke_structured_gemini.py` | 58 | 0 | sì | 0 |

### A.5 RQ2 pre-V5: ledger, dispatcher, pilot, sonde, prototipi (gruppo C2)

32 moduli, 9.707 righe.

| Modulo | Righe | Importato da | `__main__` | File di test |
|---|---:|---:|:-:|---:|
| `evaluation/rq2_discovery_d_provider_transport.py` | 173 | 0 |  | 1 |
| `evaluation/rq2_fake_discovery_driver.py` | 190 | 0 |  | 2 |
| `evaluation/rq2_langchain_bridge_source_trace.py` | 154 | 2 | sì | 0 |
| `evaluation/rq2_langchain_fake_http_invoke.py` | 231 | 0 | sì | 3 |
| `evaluation/rq2_langchain_parameter_mock_probe.py` | 197 | 2 | sì | 4 |
| `evaluation/rq2_mock_journal.py` | 326 | 1 |  | 2 |
| `evaluation/rq2_mock_pipeline_integration.py` | 175 | 0 |  | 1 |
| `evaluation/rq2_q045_warning_detector_synthetic.py` | 164 | 1 |  | 1 |
| `evaluation/rq2_v2_artifact_store.py` | 353 | 2 |  | 5 |
| `evaluation/rq2_v2_claim_journal.py` | 207 | 0 |  | 2 |
| `evaluation/rq2_v2_isolation_policy.py` | 100 | 2 |  | 3 |
| `evaluation/rq2_v2_k_quality_rubric.py` | 198 | 0 |  | 2 |
| `evaluation/rq2_v2_sonnet_c_contentblocks_v2.py` | 509 | 2 |  | 2 |
| `evaluation/rq2_v2_sonnet_c_sourcebound.py` | 459 | 0 |  | 1 |
| `evaluation/rq2_v2_sonnet_k_single_live.py` | 399 | 0 |  | 1 |
| `evaluation/rq2_v2_sonnet_k_sourcebound_preview.py` | 199 | 1 |  | 1 |
| `evaluation/rq2_v2_sonnet_pilot_driver.py` | 201 | 0 |  | 1 |
| `evaluation/rq2_v2_sonnet_pilot_ledger.py` | 436 | 5 |  | 1 |
| `evaluation/rq2_v2_unified_dispatcher_offline.py` | 327 | 1 |  | 1 |
| `evaluation/rq2_v2_unified_live_dispatcher.py` | 284 | 0 |  | 7 |
| `evaluation/rq2_v2_unified_single_stage_dispatcher.py` | 297 | 1 |  | 2 |
| `evaluation/rq2_v2_unified_synthetic_journal.py` | 498 | 0 |  | 4 |
| `evaluation/rq2_v3_offline_provenance_journal_prototype.py` | 302 | 0 |  | 1 |
| `evaluation/rq2_v3_scientific_ledger.py` | 559 | 1 |  | 2 |
| `evaluation/rq2_v3_scientific_live_stage_preflight.py` | 479 | 2 |  | 1 |
| `evaluation/rq2_v3_scientific_single_stage_dispatcher.py` | 372 | 0 |  | 1 |
| `evaluation/rq2_v3_scientific_source_inventory.py` | 272 | 3 |  | 2 |
| `evaluation/rq2_v3_scientific_source_release_gate.py` | 294 | 2 |  | 1 |
| `evaluation/rq2_v4_scientific_ledger.py` | 561 | 1 |  | 2 |
| `evaluation/rq2_v4_scientific_single_stage_dispatcher.py` | 373 | 0 |  | 1 |
| `evaluation/rq2_v4_scientific_source_inventory.py` | 133 | 1 |  | 1 |
| `evaluation/rq2_v4_scientific_source_release_gate.py` | 285 | 1 |  | 2 |

