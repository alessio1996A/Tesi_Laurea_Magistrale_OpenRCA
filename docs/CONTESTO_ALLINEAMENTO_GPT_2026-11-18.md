# Contesto di allineamento per un secondo assistente (GPT) — 18 novembre 2026

Scopo: dare a un altro assistente lo stesso quadro che ho io, con **solo fatti verificati** e
con i punti non verificati dichiarati. Aggiorna `CONTESTO_ALLINEAMENTO_GPT_2026-11-16.md`
(da quel documento restano validi i dettagli del runner V5; qui sotto lo stato è riscritto).
Ogni affermazione sul repository va controllata nei file, non data per buona. La fonte di ogni
numero è indicata come «riga N» del registro `docs/REGISTRO_DECISIONI_RQ2.md` o come documento.

## 1. Chi, cosa, quando

- Tesi magistrale di Alessio, Università di Catania, ingegneria informatica. Relatore:
  Giovanni Morana.
- Titolo: *Harness Engineering for LLM-based Root Cause Analysis*, benchmark OpenRCA, telemetria
  **solo Market** (cloudbed-1 e cloudbed-2, 148 query). Il relatore ha detto no a Telecom.
- **Consegna: 5 dicembre 2026** (il «1 dicembre» di contesti precedenti era un errore, riga 34).
  Dal 18 novembre restano 17 giorni.
- Alessio attende dal relatore la conferma per passare alla scrittura della tesi (prevista il
  18 novembre). Fino ad allora il riordino del repository è rimandato.
- Budget API: il relatore ha detto di non preoccuparsene. Non esiste un tetto rigido lato
  provider; se serve va impostato dal pannello del provider.
- Il repository è `https://github.com/alessio1996A/Tesi_Laurea_Magistrale_OpenRCA`. Alessio testa
  su PyCharm (Windows PowerShell) ed esegue le celle su Colab; Claude scrive codice e documenti.

## 2. Le due domande di ricerca

- **RQ1 — completata e approvata dal relatore (10 novembre). Non si tocca.** Un harness
  deterministico (raccolta e selezione delle evidenze, 8 regole R01, R02, R06–R11, verifica
  ispirata a PAVE) migliora accuratezza ed efficienza di un agente LLM. Cinque varianti: A0, A1,
  A1_8R, A1_8R_Planning, A1_PAVE. Punteggio con lo scorer ufficiale Microsoft. I numeri
  principali di RQ1 non sono ripetuti qui; vanno cercati in `docs/PRESENTAZIONE_RELATORE.md` e
  `docs/ARCHITETTURA_E_RISULTATI_V3.md` (**non riletti** per questo documento).
- **RQ2 — fase sperimentale chiusa il 16 novembre, poi un'ablazione esplorativa il 18.** Le 8
  regole coprono 8 delle 15 classi di guasto. Si studia se un agente LLM sappia investigare le
  **4 classi escluse** (CPU spike del nodo, carico di scrittura I/O del container, terminazione di
  processo del container, packet loss del container) e se la conoscenza ottenuta possa diventare,
  dopo verifica, una **nuova regola deterministica**. Ciclo per ogni incidente: **D** (diagnosi con
  tool) → **C** (spiegazione della causa) → **K** (regola candidata, contratto
  `rq2_candidate_rule_v0`). Human-in-the-loop e integrazione automatica nell'harness: **solo
  lavoro futuro**, non si implementano.
- Conteggio delle classi: 8 coperte + 4 escluse = 12 su 15. Le 3 restanti sono, per quanto
  verificato, di rete (packet retransmission, packet corruption, network latency; riga 40, letta
  da `record.csv` su 5 incidenti di EVALUATION20). Che siano **tutte e sole** le 3 classi mancanti
  è una deduzione (15 − 12), **non verificata** sul catalogo completo. La tesi deve dichiarare il
  perimetro.
- Il file `2606.27154v2.pdf` del Project è OpenRCA 2.0 (PAVE, altri sistemi), **non** il benchmark
  usato: i dati sono OpenRCA 1.0, sistema Market. PAVE è la fonte dei principi di verifica
  (strutturale, statistico, temporale) di A1_PAVE.
- **RQ1 e RQ2 sono separate** (riga 36): le 4 classi non compaiono in development (0 su 92) né in
  evaluation (0 su 23). Stanno in `ood_holdout` (15 su 15) e in `mixed_quarantine` (9 su 18), che
  RQ1 non ha usato. Limite: il controllo guarda la riga di `record.csv`, non i guasti aggiuntivi
  dei multiguasto.

## 3. Che cosa dice RQ1 sulla copertura delle regole (riga 38)

Stratificazione per copertura sui 20 incidenti di EVALUATION20: 15 con classe coperta dalle 8
regole, 5 con classe di rete, 0 misti, nessuno con una delle 4 classi di RQ2. Differenze medie di
punteggio (Gemini / Sonnet / Haiku):

| Confronto | Strato coperto | Strato non coperto |
|---|---|---|
| A1 − A0 | +0,167 / +0,339 / +0,150 | −0,100 / +0,100 / −0,100 |
| A1_8R − A1 | −0,091 / +0,050 / +0,128 | 0 / 0 / −0,200 |

Lettura di Claude: il risultato robusto è lo **strato delle evidenze** (A1 contro A0 nelle classi
coperte); l'effetto marginale delle 8 regole è incerto e dipende dal modello; l'ipotesi che il
vantaggio delle regole si concentri dove esistono **non è sostenuta**. Post hoc, strati piccoli,
una replica, nessun intervallo. Non si scrive che le regole «non servono».

## 4. Perimetro sperimentale RQ2

- 5 harness × 3 modelli (`gemini-3.5-flash-lite`, `claude-sonnet-5-5`, `claude-haiku-5-5`) ×
  4 incidenti di discovery × 3 stadi (D, C, K) = **180 stage**.
- Discovery (4): `cloudbed-1_q032`, `cloudbed-1_q050`, `cloudbed-2_q026`, `cloudbed-2_q045`.
- Test **sigillati** (11, mai usati in discovery): `cloudbed-1_q014, q021, q030, q059`;
  `cloudbed-2_q014, q021, q040, q041, q058, q076, q077`. Raggruppati in **10 gruppi temporali**
  W01–W10 (finestre semiaperte). Con n così piccolo i risultati sono una dimostrazione di
  fattibilità, non una stima statistica.
- `cloudbed-2_q026` è un compito di solo orario (task_1): 10 testi D su 15 sono vuoti per
  costruzione (riga 44).

## 5. Formato delle risposte, politica V5.1 e retry

- In V4 le risposte valide di Gemini erano JSON puro; quelle di Sonnet e Haiku avevano un JSON
  valido ma **avvolto in un blocco Markdown**, rifiutato dal parser strict. Audit di sola lettura
  (commit `8b64be7`): difetto di **formato**, non di contenuto.
- Politica `rq2_v5_single_json_fence_v1` (riga 4): se l'intera risposta è un solo blocco
  Markdown di tipo json, il contenuto interno passa **inalterato** al parser strict; altrimenti la risposta
  resta originale e viene rifiutata. Nessuna riparazione, nessuna estrazione da testo libero.
  Politica V5.1 (riga 5): un fence valido con testo fuori è letto, il testo è scartato ma
  registrato. Retry unico (riga 6): un solo secondo tentativo, solo per errore di trasporto senza
  output, primo tentativo conservato. **Entrambe motivate a posteriori, dopo il pilota**;
  nel registro risultavano «da confermare» al momento della scrittura, e il run è stato poi
  eseguito con esse.
- Ogni risposta registra `deviation`, hash SHA-256 e testo originale. Si riportano sempre sia la
  conformità strict sia quella tollerante.
- Nel run (riga 13): Gemini 60/60 strict; Haiku 45 strict + 12 con fence accettato + 3 non
  validi; Sonnet 59 strict + 1 fence. Un solo retry (Gemini C, q045 A0), recuperato.

## 6. Run congelato D→C→K

Namespace `data/rq2_v5_format_fair_v1`, commit congelato `ddb2ca499c4b41aa32a36fdc2f9850cb09bb75c3`
(branch `release/rq2-v5.1-discovery-v1`, non si modifica più).

- 180/180 stage registrati, **0 orfani**; 177 `RECORDED_COMPLETE`, 3 `INVALID_OUTPUT` (tutti
  Haiku, stadio K; sono `insufficient_evidence` nella sostanza ma hanno la chiave `combination`
  duplicata: il parser strict li rifiuta; nessuna riparazione).
- K, 60 stadi: **8 `candidate`** (Gemini 4, Sonnet 3, Haiku 1), 49 `insufficient_evidence`,
  3 non validi. Le regole da verificare sono 8 (molteplicità reale), non 60.
- Integrità (riga 19): 180/180 record e 180/180 claim con hash valido, `source_commit` = `ddb2ca4`
  ovunque.
- Motivo dominante di astensione citato da Haiku e Sonnet (riga 43): evidenze marcate «unità non
  verificate» e «diagnosi non verificata», quindi nessuna soglia giustificabile. È un'ipotesi di
  tensione di progetto **non testata**.

## 7. L1 e L2: verifica delle 8 candidate (esplorativa)

Protocollo e parametri congelati prima di leggere i sigillati; soglie H_pre = 60 s, H = 300 s,
copertura minima dei negativi 2/3 come **convenzioni di progetto**, non tolleranze certificate
dallo scorer Microsoft. I criteri di ammissione sono stati scritti dopo aver visto il preflight
(non ciechi).

- **L1 (senza ground truth, 4 incidenti di discovery)** — è una classificazione, non un test che
  si supera. Delle 8 candidate: 5 non formalizzabili (2 con `mrt_max` di servizio, 2 su log,
  1 su trace), 3 eseguibili (2 **non classificabili**: `system.cpu.iowait` del nodo e throttling
  CFS del container; 1 **formalizzabile**: `container_start_time_seconds` con `delta` su 600 s,
  classe container process termination). Ammessa a L2: 1 (formalizzabile + unità + storia +
  condizioni).
- **Regola ammessa**: `container_start_time_advance_restart_detector`. In L1 positiva in q032
  (1 componente, 10/1200 celle) e q045 (1 componente, 2/1200), negativa in q050 e q026; popolazione
  40/42. Il positivo di q032 non è una prova: la regola è stata scritta sull'evidenza di q032.
  Cautela: la metrica rileva un riavvio osservabile, non prova la causa della terminazione.
- **L2 (11 sigillati, 10 gruppi)**: due processi, L2a senza ground truth (decisioni sigillate con
  hash), L2b con ground truth dopo verifica della catena freeze → addendum → L2a.
  **Verdetto congelato `NON_VERIFICATA`** (commit `ce10737`): TP 0, FN 0, TN 5, FP 2; falsi
  positivi **2 su 7** (IC95% esatto 0,037–0,710); copertura minima dei negativi 0,952; 3 positivi
  non osservabili (W01 e W10 `paymentservice`, W06 `recommendationservice-1`); 8 regole provate
  (molteplicità). Non è «refutata»: è non verificata, e con **una sola regola** è un caso di
  studio, senza generalizzazione.
- **Limite scoperto leggendo il risultato** (riga 30): il valutatore confronta per **nome esatto**
  il componente di riferimento con quelli della telemetria, che hanno il prefisso del nodo. I
  riferimenti stanno a tre livelli (nodo, servizio, pod). Con qualunque corrispondenza dei nomi la
  rilevazione sarebbe 0/3 e i FP resterebbero 2/7 (riga 31). **Non corretto**, per non cambiare il
  protocollo dopo i dati.
- I due FP (W02, W08) scattano su `cartservice2-0`, mentre i guasti etichettati sono su altri
  servizi e altre classi (packet loss su `emailservice`; write I/O load su
  `productcatalogservice-0`). Il contatto temporale W07–W08 non è provato come causa del positivo
  di W08.
- **L2 non è cieco**: i sigillati sono già stati aperti. Va detto in tesi.
- Descrittive solo L1 (nessun verdetto): iowait del nodo positivo in 3 casi su 4; throttling CFS
  positivo in tutti e 4 con 15–21 container su 40 che scattano (poco selettivo).
- Conclusione per la tesi (riga 39): 0 candidate verificate su 8; *generare non equivale a
  validare*; ciò motiva la supervisione ma **non dimostra** la necessità di un umano.

## 8. RQ2-A e letture qualitative dei testi (17 novembre)

- **Scoring offline di D e C** (riga 33; modulo `rq2_a_offline_scoring.py`, 120 record in sola
  lettura, scorer ufficiale con hash verificato, 0 chiamate a provider). D: 0 in tutte le celle
  tranne `cloudbed-2_q026` (solo orario), dove Sonnet e Haiku con A1, A1_8R, A1_8R_Planning e
  A1_PAVE fanno 1,0 (8 celle su 8), con A0 0, Gemini sempre 0; i tre incidenti task_2 (motivo): 0
  in 45 celle su 45; A1_8R contro A1: 12 pareggi su 12. C: 0 corrette su 60, 13 astensioni
  (Gemini 10, Haiku 3, Sonnet 0), 47 testi liberi non mappati.
- **Limite**: scorer ufficiale a stringa esatta, prompt di D senza l'elenco delle etichette,
  politica di C senza il vocabolario delle 4 classi. L'identificazione della classe **non è
  misurabile** con questi strumenti. Nella lettura qualitativa (post hoc, non cieca, senza
  rubrica) l'etichetta esatta compare in 6 celle C su 60, tutte di Sonnet.
- **Griglia C1–C5 sul testo libero di D** (righe 41, 42, 44), congelata prima di leggere i testi,
  applicata ai 60 testi: dettaglio medio Sonnet 2,70, Haiku 2,35, Gemini 1,35 (senza q026:
  3,40 / 3,13 / 1,47). Nessun andamento ordinato per harness (A1 2,58 il più alto, Planning 1,75
  il più basso). Passata 1 non del tutto cieca (le classi di q032 e q050 erano note a Claude da
  `record.csv`). La rilettura cieca di 12 testi da parte di Alessio è stata **abbandonata** il
  17 novembre (non aveva capito il compito): l'accordo tra lettori non è stato misurato.
- K1–K4 valgono 1 per costruzione dello schema (strumento non discriminante); K5 varia solo su
  2 candidate su 8 (riga 43).
- Trasferimento attribuito all'**agente con harness** (riga 39); A0 riportato come condizione di
  riferimento: A0 4/12 stage K candidate, harness 4/48. Nessuna affermazione che l'harness sia
  necessario per generare candidate.

## 9. Ablazione D→K (18 novembre, esplorativa, post hoc)

Dopo un dubbio di Alessio sulla scelta del passo C, in un branch separato
(`claude/rq2-ablazione-dk-2026-11-18`) si è rieseguito solo K **senza la causa di C**: i record D
sono riletti con verifica dell'hash, il prompt K differisce per **una frase**, 60 nuovi K in
`data/rq2_dk_ablation_v1`, commit di esecuzione `784277c`. Protocollo congelato prima
dell'esecuzione (`RQ2_ABLAZIONE_DK_PROTOCOLLO_2026-11-18.md`). Nessun errore di provider, nessun
orfano.

- **K senza C** (riga 46): 8 `candidate` (Gemini 0, Sonnet 7, Haiku 1), 51 `insufficient_evidence`,
  1 `INVALID_OUTPUT`. Strict 59/60. 50 celle su 60 con la stessa etichetta; **solo 3 delle 8
  celle candidate coincidono** (Sonnet: A1_8R_Planning su q032, A0 su q050, A1 su q045). A1_PAVE
  0 candidate su 12 in entrambe le versioni.
- **L1 sulle 8 candidate D→K** (Emendamento 1, righe 47–48; codice `rq2_dk_l1_l2.py`, 35 test
  sintetici; verifica degli hash del codice congelato prima di eseguire). Criteri di «risultato
  concreto» fissati prima di leggere i dati: livello 1 eseguibile e formalizzabile; livello 2
  ammessa a L2; livello 3 verdetto `VERIFICATA_OPERATIVAMENTE`. Esito: **stessa ripartizione
  L1** (8 candidate, 5 non formalizzabili, 3 eseguibili, 2 non classificabili, 1 formalizzabile)
  ma **0 ammesse a L2** contro 1, quindi L2 non eseguito. Hash identici: 0.
- **Perché 0 ammesse** (riga 49, lettura dei due record K della cella q032 / Sonnet /
  A1_8R_Planning, via Drive, sola lettura): la candidata formalizzabile ha **condizioni identiche**
  alla regola congelata (metrica `container_start_time_seconds`, operatore `>`, soglia 0,
  aggregazione `delta`, finestra 600 s, combinazione `all`). Cambiano nome, testo e **unità
  dichiarata**: `seconds` nella congelata, `unverified (values look like Unix epoch seconds)` senza
  C. Il controllo di ammissione sull'unità guarda solo la coerenza dell'etichetta col nome del KPI
  e blocca la seconda con `unita_incoerente`. L'esecutore non legge il campo unità (0 occorrenze
  nel sorgente). I numeri L1 per incidente sono identici (10 / 0 / 0 / 2 celle vere su 1200;
  1 / 0 / 0 / 1 componenti che scattano).
- Anche il throttling CFS ha numeri L1 identici alla regola congelata (503/503/366/279 celle vere;
  21/20/20/15 componenti). **Non ho letto le sue condizioni dai record**: l'equivalenza si basa sui
  12 numeri, non sul testo. La terza eseguibile D→K (picco di `system.io.util` e salto di
  `system.disk.used` sul nodo, Sonnet A1, q026) è nuova e diversa dall'iowait dei nodi del run
  congelato; non classificabile.
- **Decisione di Claude** (riga 49, contestabile): D→K non produce un risultato concreto in più;
  L2 su D→K darebbe per costruzione lo stesso `NON_VERIFICATA` (2 FP su 7). Questa è una
  **deduzione dal codice e dai record, non una misura**. Si omette un Emendamento 2 di
  sensibilità, perché non aggiungerebbe informazione. Limite da dichiarare: il controllo
  sull'unità premia l'etichetta uguale al nome del KPI, non la prudenza.
- **Non si può dire** che C sia utile o inutile (4 incidenti, una esecuzione per cella, nessuna
  replica, frase del prompt cambiata), né perché Gemini smetta di proporre candidate e Sonnet ne
  proponga di più. Le 8 candidate senza C non sono state verificate.
- Opzionale, non eseguita: replica dei 60 K senza C (60 chiamate a pagamento) per stimare la
  variabilità tra due esecuzioni dello stesso passo.

## 10. Stato del repository e dei test

- Branch: `main`; `claude/refactor-commenti-lotto1-2026-11-17` (refactoring dei commenti, solo
  commenti e docstring); `claude/rq2-ablazione-dk-2026-11-18` (ablazione D→K, ultimo commit di
  risultati `93f3679`). Il branch del run congelato è `release/rq2-v5.1-discovery-v1`.
- **25 file protetti da hash non si modificano.** Nel branch di
  refactoring: solo commenti e docstring; L2b non si riesegue mai lì.
- Test sul PC di Alessio prima dell'ablazione: `2 failed, 1877 passed, 2 skipped, 1 warning,
  1 error` (3 test obsoleti noti). Con i +24 test dell'ablazione e i +35 di L1/L2 il PC dovrebbe
  dare 1936 passed: **atteso, non verificato**. Nella sandbox di Claude (senza LangChain) i test
  falliti sono gli stessi insiemi di prima delle modifiche (confrontati per identificativo).

## 11. Cosa è verificato e cosa no

Verificato (con la fonte indicata sopra):
- Integrità dei 180 record, esiti dei 60 K, L1 e L2 congelati, scoring RQ2-A, stratificazione RQ1,
  separazione RQ1/RQ2, 60 K senza C, L1 sulle 8 candidate D→K, equivalenza delle condizioni della
  regola di riavvio nei due record letti.

**Non** verificato:
- Che L2 su D→K darebbe `NON_VERIFICATA`: è una deduzione.
- Le condizioni (non i numeri) del throttling CFS D→K.
- Che le 3 classi non coperte siano tutte e sole di rete.
- Il conteggio dei test sul PC di Alessio dopo le ultime aggiunte.
- La causa del `PROVIDER_ERROR` di Gemini in un K di V4 (messaggio sanitizzato).
- Il conteggio dei token tra provider non è confrontabile alla pari: Claude ha `max_tokens=4096`
  condiviso con l'eventuale ragionamento esteso.
- La risposta del relatore sul perimetro finale di RQ2 e sulla conferma per scrivere la tesi.

## 12. Cosa manca

1. Conferma del relatore, poi **scrittura della tesi**: prima i capitoli 1–2; capitolo RQ2 con
   struttura già concordata (L1/L2 come sezione breve, protocollo in appendice, soglie dichiarate
   come convenzioni, riga 34); capitolo di lavoro futuro su human-in-the-loop e architettura
   duale, solo come concetto.
2. Dopo la conferma o dopo la scrittura: pulizia di cartelle, branch e file inutili, potatura dei
   branch remoti già integrati, correzione dei 3 test obsoleti, commento dei gruppi B1 (8 moduli)
   e B2 (12 moduli).
3. Eventuale replica dei 60 K senza C (non necessaria per la tesi).

## 13. Regole di lavoro condivise

- **Decide Claude, GPT affianca.** Le decisioni di protocollo che cambiano cosa la tesi può
  affermare le approva Alessio. Si seguono le **direttive del relatore**, non quelle di GPT.
- Un solo agente scrive su un branch. Chi altro vuole proporre codice usa un branch proprio
  (`gpt/<tema>`) e lo dice ad Alessio.
- Non modificare i file V2/V3/V4/V5 congelati né i risultati RQ1. Mai riscrivere un record o un
  report create-only.
- Mai leggere ground truth o sigillati nella discovery. Nessun retry nascosto, nessuna
  riparazione del JSON del modello, nessun cambio di soglia dopo aver visto i dati.
- Nessuna email a nome di Alessio senza il suo permesso: solo bozze.
- Si resta nel tema: miglioramento della root cause analysis tramite harnessing.
- Ogni numero porta la sua fonte; se non è verificato, scrivere «non verificato».
- Risposte in italiano. I comandi vanno sempre dati sia per PyCharm (PowerShell su Windows) sia per
  Colab.

## 14. Dove un revisore indipendente aiuta di più

1. **Lettura D→K**: l'equivalenza esecutiva giustifica di non eseguire L2? Il limite del controllo
   sull'unità è descritto in modo onesto? C'è una lettura alternativa trascurata?
2. **Struttura e linguaggio del capitolo RQ2**: come presentare un esito sostanzialmente negativo
   (0 regole verificate su 8) senza gonfiarlo né svalutarlo; come dichiarare i limiti (n piccolo,
   una esecuzione per cella, L2 non cieco, difetto dei nomi, scorer a stringa esatta, rilettura
   cieca abbandonata).
3. **Affermazioni più forti dei dati** nei documenti: cercarle e segnalarle.
4. **Indice della tesi e ordine di scrittura**, con 17 giorni disponibili.
5. **Revisione di sola lettura** di `rq2_dk_l1_l2.py` (adapter che riusa senza modificarli i moduli
   congelati): bug, condizioni di corsa, casi limite.
