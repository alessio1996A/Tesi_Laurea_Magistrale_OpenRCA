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
- per le candidate nuove, categoria L1 (eseguibile, formalizzabile) **solo** se L1 si può eseguire senza ground truth con il codice congelato; sarebbe un'analisi esplorativa. **L2 non si ripete**: gli incidenti sigillati sono già stati aperti e non sono più ciechi.

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
