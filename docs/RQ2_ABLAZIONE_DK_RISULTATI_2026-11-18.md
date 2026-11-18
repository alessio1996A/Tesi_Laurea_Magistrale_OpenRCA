# RQ2 — ablazione D→K: risultati (18 novembre 2026)

**Protocollo:** `docs/RQ2_ABLAZIONE_DK_PROTOCOLLO_2026-11-18.md` (congelato prima dell'esecuzione).
**Esecuzione:** Colab, commit `784277c`, 60 K in `data/rq2_dk_ablation_v1` (Drive), manifest `manifest_dk_v1.json`. Prova su 3 stadi (Haiku, A0), poi i restanti 57: nessun orfano, nessun errore di provider, esecuzione completa in circa 9 minuti.
**Natura:** esplorativa, 4 incidenti, una esecuzione per cella. Nessuna inferenza statistica.

## 1. Esiti dei 60 K

| | Con la causa di C (run congelato) | Senza C (ablazione) |
|---|---|---|
| `candidate` | 8 | 8 |
| `insufficient_evidence` | 49 | 51 |
| `INVALID_OUTPUT` | 3 | 1 |
| Gemini | 4 candidate, 16 astensioni | 0 candidate, 20 astensioni |
| Sonnet | 3 candidate, 17 astensioni | 7 candidate, 13 astensioni |
| Haiku | 1 candidate, 16 astensioni, 3 non validi | 1 candidate, 18 astensioni, 1 non valido |

Conformità di formato senza C: strict 59 su 60 (Gemini 20/20, Sonnet 20/20, Haiku 19/20).

Per harness (candidate): A0 4→4, A1 1→2, A1_8R 1→1, A1_8R_Planning 2→1, A1_PAVE 0→0. A0 resta la condizione con più candidate in entrambe le versioni.

## 2. Confronto cella per cella

- 50 celle su 60 hanno la stessa etichetta con e senza C; 10 celle cambiano.
- **Solo 3 delle 8 celle candidate coincidono** (tutte Sonnet: A1_8R_Planning su q032, A0 su q050, A1 su q045). Le altre 5 candidate del run congelato (4 Gemini, 1 Haiku) senza C diventano astensioni; 5 celle astensione diventano candidate (4 Sonnet, 1 Haiku).
- Il cambio più marcato è per modello: Gemini passa da 4 candidate a 0, Sonnet da 3 a 7.

## 3. Che cosa si può e non si può dire

**Si può dire:**
1. Togliere il passo C non riduce il numero di candidate prodotte (8 su 60 in entrambe le versioni).
2. L'insieme delle celle candidate cambia molto (3 su 8 in comune), quindi la produzione di una candidata in una cella specifica è poco stabile.
3. A1_PAVE non produce candidate in nessuna delle due versioni (0 su 12): l'harness non aumenta le candidate.

**Non si può dire:**
- che C aiuti o danneggi la produzione di candidate: senza repliche la variazione tra le due esecuzioni non è separabile dalla variabilità del modello e dalla frase cambiata nel prompt;
- perché Gemini smetta di proporre candidate e Sonnet ne proponga di più;
- che le 8 candidate senza C siano corrette: non sono state verificate.

## 4. Lettura per la tesi

D→C→K e D→K producono lo stesso numero di candidate, ma non le stesse. Il passo C non risulta necessario per ottenere candidate; non risulta nemmeno dannoso. Resta una scelta di progetto che serve alla spiegazione della causa richiesta dal relatore, non alla produzione di regole.

## 5. Prossimi passi possibili (non eseguiti)

- ~~Leggere (L1, senza ground truth) le 8 candidate nuove~~ **Fatto il 18 novembre** (Emendamento 1, `RQ2_ABLAZIONE_DK_L1_L2_RISULTATI_2026-11-18.md`): 1 formalizzabile, 0 ammesse a L2, L2 non applicabile. Il testo originale diceva «L2 non si ripete», superato dall'emendamento.
- Una replica dei 60 K senza C, per stimare la variabilità tra due esecuzioni dello stesso passo: costerebbe di nuovo 60 chiamate.
