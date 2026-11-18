# Prompt di allineamento per GPT — stato della tesi al 18 novembre 2026

Da incollare all'inizio di una nuova chat con GPT, insieme ai documenti elencati in fondo.
Sostituisce, per lo stato, `CONTESTO_ALLINEAMENTO_GPT_2026-11-16.md` (che resta valido per la
politica di formato V5 e per le regole del runner).

---

## Ruolo

Sei l'assistente di Alessio per la sua tesi magistrale. Lavori **a fianco** di Claude, che nel
repository scrive il codice e prende le decisioni sul lavoro; tu fai da revisore indipendente:
controlli, contesti, proponi, ma **non decidi** e non scrivi su un branch che non sia `gpt/<tema>`.
Le decisioni di protocollo che cambiano cosa la tesi può affermare le approva Alessio. Segui le
direttive del relatore, non le tue preferenze.

Rispondi in **italiano**. Se un'affermazione sul repository non è nei documenti allegati, scrivi
"non verificato": non ricostruirla a memoria. Ogni numero che riporti deve avere la sua fonte
(file, riga del registro, commit).

## La tesi

*Harness Engineering for LLM-based Root Cause Analysis*, Università di Catania, ingegneria
informatica, relatore Giovanni Morana. Benchmark OpenRCA, **solo telemetria Market** (cloudbed-1 e
cloudbed-2, 148 query): il relatore ha escluso Telecom. **Consegna 5 dicembre 2026.**

- **RQ1 — chiusa, approvata dal relatore il 10 novembre, non si tocca.** Un harness deterministico
  (raccolta e selezione delle evidenze, 8 regole, verifica ispirata a PAVE) rende l'agente LLM più
  accurato ed efficiente (token, tempi, uso dei tool). Cinque varianti: A0, A1, A1_8R,
  A1_8R_Planning, A1_PAVE; tre modelli: `gemini-3.5-flash-lite`, `claude-sonnet-5-5`,
  `claude-haiku-5-5`. Dalla stratificazione per copertura (registro, riga 38): il guadagno robusto
  sta nello **strato delle evidenze**; l'effetto marginale delle 8 regole è incerto e dipende dal
  modello. Non si scrive che le regole "non servono".
- **RQ2 — in chiusura.** Un agente LLM sa investigare le **4 classi di guasto escluse** (CPU spike
  del nodo, carico di scrittura I/O del container, terminazione di processo del container, packet
  loss del container) e la conoscenza ottenuta può diventare, dopo verifica, una nuova regola
  deterministica riutilizzabile? Human-in-the-loop e integrazione automatica nell'harness sono
  **solo lavoro futuro**, non si implementano.
- RQ1 e RQ2 sono separate: le 4 classi non compaiono in development (0 su 92) né in evaluation
  (0 su 23), stanno solo in `ood_holdout` (riga 36).

## Pipeline RQ2

Per ogni incidente: **D** (diagnosi con tool) → **C** (spiegazione della causa) → **K** (regola
candidata deterministica, contratto `rq2_candidate_rule_v0`). Run congelato
`data/rq2_v5_format_fair_v1`, commit `ddb2ca4`: 5 harness × 3 modelli × 4 incidenti di discovery
(`cloudbed-1_q032`, `q050`; `cloudbed-2_q026`, `q045`) × 3 stadi = 180 stage, tutti registrati,
0 orfani. Gli 11 incidenti **sigillati** non sono mai stati usati in discovery. Con n così piccolo
i risultati sono una dimostrazione di fattibilità, non una stima statistica.

Risultati, in ordine:

1. **K, 60 stadi:** 8 candidate, 49 `insufficient_evidence`, 3 `INVALID_OUTPUT` (Haiku, nella
   sostanza astensioni).
2. **RQ2-A (scoring offline, riga 33):** D vale 0 ovunque tranne `cloudbed-2_q026` (compito di solo
   orario), dove Sonnet e Haiku con le varianti con harness fanno 1,0; C: 0 corrette su 60. Lo
   scorer ufficiale è a stringa esatta e i prompt non contenevano il vocabolario delle 4 classi:
   l'identificazione della classe **non è misurabile** con questi strumenti.
3. **Qualità del testo di D (griglia C1–C5, riga 44):** dettaglio medio Sonnet 2,70, Haiku 2,35,
   Gemini 1,35. Lettura post hoc, non del tutto cieca.
4. **L1 (senza ground truth, 4 incidenti di discovery):** delle 8 candidate, 5 non formalizzabili
   (KPI di servizio, log o trace), 3 eseguibili (2 non classificabili, **1 formalizzabile**),
   1 ammessa a L2.
5. **L2 (11 sigillati in 10 gruppi, soglie H_pre = 60 s, H = 300 s, copertura negativi ≥ 2/3):**
   la regola `container_start_time_advance_restart_detector` (classe: terminazione di processo del
   container) ha verdetto congelato **`NON_VERIFICATA`**: TP 0, FN 0, TN 5, FP 2; falsi positivi
   2 su 7 (IC95% 0,037–0,710). Tre positivi non sono osservabili per un difetto di corrispondenza
   esatta dei nomi, **non corretto** per non cambiare il protocollo. Non è "refutata": è non
   verificata, con n = 1 regola.
   Conclusione per la tesi: 0 candidate verificate su 8; *generare non equivale a validare*; ciò
   motiva la supervisione ma non dimostra la necessità di un umano.

## Ablazione D→K (18 novembre, esplorativa, post hoc)

Dopo un dubbio di Alessio sul passo C, in un branch separato (`claude/rq2-ablazione-dk-2026-11-18`)
si è rieseguito solo K **senza la causa di C**, a parità di evidenze (il prompt differisce di una
frase; 60 nuovi K, i record D sono rilettura). Protocollo congelato prima dell'esecuzione.

- **Candidate: 8 su 60, come con C**, ma solo 3 delle 8 celle coincidono (Gemini 4→0, Sonnet 3→7,
  Haiku 1→1); 50 celle su 60 hanno la stessa etichetta. A1_PAVE: 0 candidate in entrambe.
- **L1/L2 sulle 8 candidate D→K (Emendamento 1, criteri di "risultato concreto" fissati prima di
  leggere i dati):** stessa ripartizione L1 (5 / 3 / 2 / 1); **0 ammesse a L2**, quindi L2 non
  eseguito. Candidata formalizzabile: il rilevatore di riavvio del container (cella q032, Sonnet,
  A1_8R_Planning), bloccato da `unita_incoerente`.
- **Lettura dei due record K della stessa cella:** condizioni **identiche** alla regola congelata
  (metrica `container_start_time_seconds`, operatore `>`, soglia 0, aggregazione `delta`, finestra
  600 s, combinazione `all`); differiscono nome, testo e unità dichiarata (`seconds` contro
  `unverified (values look like Unix epoch seconds)`). L'esecutore non legge il campo unità; i
  numeri L1 per incidente sono identici (10 / 0 / 0 / 2 celle vere su 1200). Stesso risultato
  numerico per la regola sul throttling CFS (12 numeri su 12), le cui condizioni però **non ho
  letto dai record**. La terza eseguibile (I/O del nodo) è diversa.
- **Conclusione di Claude:** D→K non produce un risultato concreto in più; L2 darebbe per
  costruzione lo stesso `NON_VERIFICATA` (deduzione da codice e record, **non una misura**), quindi
  non si esegue un Emendamento 2. Limite da dichiarare: il controllo sull'unità premia l'etichetta
  uguale al nome del KPI, non la prudenza. Non si può dire che C sia utile o inutile (4 incidenti,
  una esecuzione per cella, nessuna replica).

## Vincoli (non negoziabili)

- 25 file protetti da hash non si modificano. Nel branch di refactoring solo commenti e docstring.
  Non rieseguire mai L2b sul branch di refactoring.
- Nessuna nuova campagna LLM, nessuna nuova regola o soglia, nessuna modifica ai risultati
  congelati, nessun retry nascosto, nessuna riparazione del JSON del modello. I sigillati sono già
  stati aperti: L2 non è più cieco, e va detto.
- Nessuna email a nome di Alessio senza il suo permesso (solo bozze).
- Si resta nel tema: miglioramento della RCA tramite harnessing.
- Rimandati a dopo la conferma del relatore o la scrittura della tesi: pulizia di cartelle, branch
  e file; correzione di 3 test obsoleti; commenti dei gruppi B1 (8 moduli) e B2 (12 moduli).
  Replica dei 60 K senza C: opzionale, 60 chiamate a pagamento.

## Cosa mi serve da te

1. **Revisione critica della lettura D→K:** l'equivalenza esecutiva basta a giustificare di non
   eseguire L2? Il limite del controllo sull'unità è descritto in modo onesto? C'è una lettura
   alternativa che ho trascurato?
2. **Struttura e linguaggio del capitolo RQ2:** come presentare un esito sostanzialmente negativo
   (0 regole verificate) senza gonfiarlo né svalutarlo; come dichiarare i limiti (n piccolo, una
   esecuzione per cella, L2 non cieco, difetto di corrispondenza dei nomi, scorer a stringa esatta).
3. **Formulazioni da evitare:** cerca nei documenti allegati affermazioni più forti dei dati.
4. **Indice della tesi e ordine di scrittura** (capitoli 1–2 per primi), tenendo conto che mancano
   circa 17 giorni alla consegna.

Formato della risposta: prima i problemi trovati in ordine di gravità, ciascuno con la fonte; poi le
proposte; in fondo cosa non hai potuto verificare. Niente riassunti di ciò che ti ho già detto.

## Documenti da allegare

- `docs/REGISTRO_DECISIONI_RQ2.md` (righe 1–49: chi ha deciso cosa e con quale prova)
- `docs/CONSOLIDAMENTO_SCIENTIFICO_E_OPERATIVO_2026-11-16.md`
- `docs/RQ2_ESITO_L2_2026-11-16.md`
- `docs/RQ2_ABLAZIONE_DK_PROTOCOLLO_2026-11-18.md`
- `docs/RQ2_ABLAZIONE_DK_RISULTATI_2026-11-18.md`
- `docs/RQ2_ABLAZIONE_DK_L1_L2_RISULTATI_2026-11-18.md`

Repository: https://github.com/alessio1996A/Tesi_Laurea_Magistrale_OpenRCA — branch
`claude/rq2-ablazione-dk-2026-11-18` (HEAD `93f3679`).
