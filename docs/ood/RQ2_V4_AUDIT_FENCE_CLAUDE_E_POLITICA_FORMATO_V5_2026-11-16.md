# RQ2 — Audit offline dei due D Claude V4 e politica di formato V5 (16 novembre 2026)

**Tipo di evidenza:** output Colab fornito dall'utente (`AUDIT_RETURN_CODE=0`), script `src/evaluation/rq2_v5_fence_audit_readonly.py` al commit `8b64be7`. Zero API, zero scritture, zero GT. **Non modifica né riclassifica alcun record V4**: Sonnet e Haiku D restano `INVALID_OUTPUT`.

## Esito dell'audit (solo flag strutturali, nessun testo)

| Controllo | Sonnet | Haiku |
|---|---|---|
| Record SHA / raw SHA / lunghezza coincidono con l'handoff | sì | sì |
| `json.loads` strict sulla risposta intera | fallisce, posizione 0 | fallisce, posizione 0 |
| Risposta = un solo blocco fenced, nessun testo fuori | sì | sì |
| Lingua dichiarata | `json` | `json` |
| JSON interno parsabile, senza chiavi duplicate | sì | sì |
| Numero guasti / chiavi consecutive da "1" | 1 / sì | 1 / sì |
| Campo richiesto da `task_2` (`root cause reason`) presente e non vuoto | sì | sì |
| Campi extra | `root cause component`, `root cause occurrence datetime` | nessuno |
| Ledger V4 invariato (9 record) | sì | sì |

## Interpretazione

- Per entrambi i Claude il fallimento V4 è **solo di formato**: dentro il fence c'è JSON conforme al contratto del task. Questo NON dice nulla sulla correttezza causale della diagnosi (non valutata, nessuna GT).
- Il prompt vietava già il Markdown (due volte): è un problema di aderenza del modello all'istruzione di formato, non di prompt ambiguo né di estrazione (`text_blocks=1`).
- Il blocco non testuale (`nontext_blocks=1`) è plausibilmente un blocco di thinking (vedi `FASE2_CLAUDE_CONTENT_BLOCK_V3`), ma il ledger conserva solo i conteggi: è un'inferenza, non verificata.
- Sonnet ha aggiunto due campi extra non richiesti: ammessi dal contratto V2.4, ma è una seconda deviazione dal prompt, da riportare.
- Continuità con RQ1: nella relazione EVALUATION20, 68 delle 80 risposte non conformi a V2 lo erano per il solo wrapper Markdown.

## Politica di formato V5 (BOZZA, non ancora congelata)

Modulo `src/evaluation/rq2_v5_response_normalization.py`: se l'intera risposta è esattamente un solo blocco ```` ```json … ``` ```` (o senza lingua), si passa al parser strict il contenuto interno inalterato; altrimenti la risposta originale. Nessuna riparazione. Stessa funzione per tutti i modelli, senza parametro modello.

- Ogni stage registra `deviation` (`NONE` / `SINGLE_JSON_FENCE` / `REJECTED_WRAPPER`) e l'hash della risposta originale.
- Si riportano **entrambi** i tassi per tutti i modelli: conformità strict (nessuna deviazione) e conformità tollerante.
- I record V4 non vengono ritentati né sovrascritti. I nuovi stage V5 hanno identificativi propri.
- **Trasparenza:** la politica è motivata da un'osservazione sui dati V4 ed è dichiarata prima di qualunque stage V5. Va scritto così nel capitolo sperimentale.
