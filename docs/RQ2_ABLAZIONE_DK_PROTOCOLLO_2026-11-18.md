# RQ2 — ablazione D→K (K senza il passo C): protocollo

**Data:** 18 novembre 2026. **Branch:** `claude/rq2-ablazione-dk-2026-11-18` (da `feature/rq2a-offline-scoring-2026-11-17`).
**Stato:** codice e test offline pronti; **nessuna chiamata a modelli eseguita**. Questo protocollo si congela PRIMA di eseguire i 60 K.
**Natura:** esperimento nuovo, esplorativo, separato dal run congelato (`data/rq2_v5_format_fair_v1`, commit `ddb2ca49…`). Non modifica né sostituisce alcun risultato esistente.

## 1. Domanda

Nel run congelato K riceve (a) le evidenze raccolte da D (la traiettoria degli strumenti) e (b) la causa scritta da C. Che cosa cambia se K riceve solo (a)?

La domanda nasce dal dubbio, emerso il 18 novembre, che il passo C sia una scelta di progetto non dimostrata: non esiste una variante senza C con cui confrontarla. **Nessuna direzione è ipotizzata**: K senza causa può dare più candidate, meno o lo stesso numero.

## 2. Che cosa cambia (e solo questo)

| Elemento | Run congelato D→C→K | Ablazione D→K |
|---|---|---|
| Dati di D | record D congelati | **gli stessi record D, riletti** (nessuna nuova chiamata) |
| Passo C | eseguito | **non eseguito** |
| Evidenze che K vede | traiettoria degli strumenti di D | identiche |
| Causa di C nel pacchetto di K | sì (`unverified_model_cause_probe`) | **no** |
| Risposta (diagnosi) di D | mai passata a K | mai passata a K (invariato) |
| Prompt di sistema di K | `RULE_SYSTEM` | `RULE_SYSTEM` con **una sola frase** sostituita (vedi sotto) |
| Contratto di output, politica di formato V5.1, retry, claim create-only | — | identici |
| Modelli, harness, incidenti | 3 × 5 × 4 | 3 × 5 × 4 (stessi) |

Frase sostituita nel prompt (SHA-256 del nuovo prompt: `7ffe92fa…6b63`, fissato nei test e nel manifest):

- prima: «Use ONLY the observed tool evidence and the model's own previously frozen cause probe (which may be wrong); it is NOT ground truth.»
- dopo: «Use ONLY the observed tool evidence. No prior cause analysis is provided and none must be assumed.»

**Attenzione a come si dice:** questa NON è una variante in cui K vede la diagnosi di D. Nel run congelato la risposta di D non arriva né a C né a K, per non ancorare i passi successivi, e qui resta così. Una variante «K con la diagnosi di D» sarebbe un'altra ablazione; **non** è eseguita e non è prevista prima della consegna.

## 3. Esecuzione

- 60 stadi K (4 incidenti di discovery × 3 modelli × 5 harness), una esecuzione per cella, in `data/rq2_dk_ablation_v1`, un file per claim e uno per record, a sola creazione.
- Politica di retry identica al run congelato (al più un secondo tentativo, solo per errore di trasporto senza output).
- Un D non completo nel run congelato blocca il K corrispondente, senza chiamate.
- Un claim senza record è un orfano: non si riesegue da soli.
- Nessun incidente sigillato, nessun ground truth, nessuno scorer ufficiale, nessuna nuova esecuzione di D, C, L1 o L2.
- Le 60 chiamate sono a pagamento: **partono solo dopo la risposta del relatore e l'approvazione esplicita del budget da parte di Alessio.**

## 4. Che cosa si riporta

Solo descrittivo, per modello e per harness, affiancato al run congelato (`rq2_dk_run_cli compare`):

- numero di K `candidate`, `insufficient_evidence`, non validi (strict), con `PROVIDER_ERROR` e `RECEIPT_REJECTED` a parte;
- conformità strict e tollerante del formato;
- per le candidate nuove, categoria L1 (eseguibile, formalizzabile) **solo** se L1 si può eseguire senza ground truth con il codice congelato; sarebbe un'analisi esplorativa. **L2 non si ripete**: gli incidenti sigillati sono già stati aperti e non sono più ciechi. *[Superato dall'Emendamento 1, sezione 8, scritto il 18 novembre dopo aver visto i risultati dei 60 K: a richiesta di Alessio L1 e L2 si applicano anche alle candidate nuove. Il testo originale di questa sezione non è stato modificato.]*

## 5. Che cosa si può e non si può affermare

**Si può dire:** con le stesse evidenze, K senza la causa di C ha prodotto N candidate contro 8 del run congelato (con la ripartizione per modello e harness).

**Non si può dire:**
- che C sia necessario o inutile (4 incidenti, una esecuzione per cella, 60 K: nessuna stima statistica);
- che un'eventuale differenza sia dovuta a C e non alla variabilità del modello (nessuna replica) né alla frase cambiata nel prompt;
- che le candidate nuove siano corrette o verificate.

Se il numero di candidate fosse uguale o simile, la conclusione è «nessuna evidenza che C serva alla produzione di candidate». Se fosse diverso, resta un risultato esplorativo su 4 incidenti.

## 6. Decisioni dichiarate prima dei dati

1. L'esito si riporta qualunque sia, compreso quello negativo o nullo.
2. Il numero di K, i modelli, gli harness e gli incidenti non cambiano dopo aver visto i risultati.
3. Nessuna soglia, nessun parametro del provider e nessun prompt vengono modificati dopo il primo K eseguito.
4. L'ablazione si presenta nella tesi come analisi aggiuntiva esplorativa del capitolo su RQ2, non come risultato centrale.
5. Se un lotto fallisce per cause di sistema (chiavi, pacchetti), si ferma e si ripara l'ambiente, mai il protocollo.

## 7. File

- `src/evaluation/rq2_dk_ablation.py` — prompt, pacchetto, esecutore, ciclo, confronto.
- `src/evaluation/rq2_dk_run_cli.py` — `check`, `run`, `summary`, `compare`.
- `src/tests/test_rq2_dk_ablation_offline.py`, `src/tests/test_rq2_dk_run_cli_offline.py` — 24 test senza API.
- Nessun file protetto da hash è stato toccato (verifica: `tools/refactoring/controlla_solo_commenti.py` non si applica, perché qui si aggiungono file nuovi; controllo con `git diff --stat` contro la base).

## 8. Emendamento 1 — L1 e L2 sulle candidate D→K (18 novembre 2026, scritto DOPO i risultati dei 60 K)

**Origine.** Dopo aver visto che i K senza causa hanno prodotto 8 candidate (Gemini 0, Sonnet 7, Haiku 1), Alessio ha chiesto di valutarle con gli stessi L1 e L2 del run congelato, per vedere se D→K ha prodotto risultati concreti rispetto a D→C→K. È una decisione **post hoc**: contraddice la frase «L2 non si ripete» della sezione 4, che resta com'era con un rinvio a questa sezione.

### 8.1 Che cosa si fa (e che cosa non cambia)

- **Stesso codice, stessi parametri.** Si riusano senza modificarli `rq2_k_l1_preflight`, `rq2_k_l1_protocol`, `rq2_k_rule_executor`, `rq2_k_l2_execute`, `rq2_k_l2_scoring` e `rq2_k_rule_evaluation`. Prima di ogni comando il nuovo modulo `src/evaluation/rq2_dk_l1_l2.py` verifica che gli hash dei sorgenti, della tabella semantica, dei parametri, dei moduli L2 e dei loader coincidano con quelli registrati nel freeze e nell'addendum del 16 novembre; se differisce anche un solo file, **nulla parte**.
- **Stessi dati di riferimento.** Catalogo dei KPI, 4 incidenti di discovery per L1, 11 incidenti sigillati raggruppati negli stessi 10 gruppi per L2, H_pre = 60 s, H = 300 s, soglia esplorativa 2/3 sui negativi: letti dai file del run congelato, mai riscritti.
- **Archivi nuovi, a sola creazione**, in `data/rq2_dk_l1_l2_v1`: `l1_report_dk.json`, `l2_addendum_dk.json`, `l2a_decisions_dk.json`, `l2b_evaluation_dk.json`. Il run congelato e l'archivio dei 60 K non vengono scritti.
- **Stessa separazione dei processi.** `l1` e `l2a` non leggono la ground truth (un test lo verifica); `l2b` è un processo a parte che la legge solo dopo aver verificato la catena di hash (freeze derivato → addendum derivato → decisioni L2a).
- Se L1 non ammette nessuna candidata, L2 **non si esegue** e il risultato è «L2: non applicabile (0 ammesse)».

### 8.2 Dichiarato prima di leggere L1 e L2 delle candidate nuove

1. Si riportano **tutte** le 8 candidate D→K, nessuna esclusa, con cella, regola, KPI citati ed esito L1.
2. **Che cosa si chiama «risultato concreto»** (fissato ora, non dopo):
   - livello 1, *intermedio*: la candidata è eseguibile e formalizzabile, cioè usa solo KPI di nodo o di container e ha una sola classe nella tabella semantica;
   - livello 2: è **ammessa a L2** (unità, storia, condizioni, L1 passato);
   - livello 3, *risultato concreto pieno*: verdetto L2 `VERIFICATA_OPERATIVAMENTE`. `NON_VERIFICATA` è un esito negativo da riportare, non un errore tecnico; `NON_VALUTABILE` indica una lacuna.
3. Una regola con **lo stesso hash** di una del run congelato si riporta come tale e non conta come evidenza indipendente: il suo esito L2 deve coincidere con quello congelato (controllo di determinismo).
4. Il **difetto di corrispondenza dei nomi** di L2b (nodo / servizio / pod) **non si corregge**: si riporta con lo stato del componente di riferimento, come nel run congelato.
5. Nessuna soglia, regola, parametro, tabella semantica o gruppo cambia dopo aver visto i risultati. Vale il punto 5 della sezione 6 (se si ferma per cause di sistema si ripara l'ambiente, non il protocollo).

### 8.3 Limiti, da riportare nella tesi

- **L2 non è cieco.** Gli 11 sigillati sono già stati aperti nel run congelato e sono noti a tutti (compreso l'esito di L2 sulla regola congelata e la natura dei tre positivi). Resta cieca solo la **produzione** delle candidate: il modello di K ha visto la traiettoria dei 4 incidenti di discovery e nient'altro.
- **Confronti multipli.** Le regole provate sono 8 in D→K e 16 contando le 8 del run congelato; non si applica nessuna correzione e il numero è riportato accanto a ogni verdetto.
- 4 incidenti, una esecuzione per cella, una sola classe ammissibile alla volta: nessuna stima statistica, nessun confronto causale tra «con C» e «senza C».
- Il codice dell'emendamento è scritto da Claude Sonnet 5.5, che è anche uno dei modelli valutati (conflitto già dichiarato nel registro).
- L'esito è un'analisi aggiuntiva esplorativa e non entra nel risultato principale.

### 8.4 Procedura

1. `l1` (offline, senza ground truth): legge i 60 K, classifica le 8 candidate, esegue le eseguibili sui 4 incidenti di discovery, stampa il confronto L1 con il run congelato.
2. `l2a --authorize-sealed-telemetry`: solo se L1 ammette almeno una candidata; scrive l'addendum derivato e le decisioni.
3. `l2b --authorize-ground-truth`: verdetto con i parametri congelati.
4. `compare`: tabella D→C→K contro D→K per L1 e L2, in sola lettura.
