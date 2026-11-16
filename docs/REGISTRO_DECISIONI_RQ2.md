# Registro delle decisioni RQ2

Serve a rispondere, in tesi e davanti alla commissione, a "chi ha deciso cosa,
quando, perché e con quale prova". Una riga per decisione. Le decisioni di
protocollo cambiano che cosa la tesi può affermare, quindi le approva Alessio;
i dettagli di implementazione (codice, test, struttura) li decide Claude e li
documenta qui o nei commit.

Legenda approvazione: **esplicita** = Alessio l'ha scritto; **implicita** =
Alessio ha proseguito senza obiezioni; **da confermare** = serve un "ok".

| # | Data | Decisione | Proposta da | Motivo / prova | Approvazione | Reversibile? |
|---|---|---|---|---|---|---|
| 1 | nov 2026 | RQ2 minima: 4 classi escluse, D→C→K, verifica su incidenti sigillati; human-in-the-loop e integrazione automatica solo come lavoro futuro | Relatore + Alessio | Feedback del relatore: resta solo RQ2; l'integrazione automatica non è implementabile nei tempi | esplicita | n/a |
| 2 | nov 2026 | Stessa valutazione per 3 modelli (Gemini, Sonnet, Haiku) e 5 harness (A0, A1, A1_8R, A1_8R_Planning, A1_PAVE); budget non vincolante | Alessio | "per tutti e 3 i modelli va benissimo"; il relatore ha detto di non preoccuparsi del budget | esplicita | sì |
| 3 | 16 nov | Runner leggero (opzione B): claim create-only, nessun retry automatico (poi vedi #6), blocco D→C→K, riesecuzione sempre vietata | Claude | Meno cerimonie del ledger V4, stesse garanzie di non sovrascrittura | esplicita ("se mi consigli B facciamo B") | sì |
| 4 | 16 nov | Policy di formato V5: unwrap di un singolo fence json, uguale per tutti i modelli | Claude | Audit V4: Sonnet e Haiku avvolgono JSON valido in Markdown, Gemini no. Motivata **a posteriori** | implicita | sì, prima del run |
| 5 | 16 nov | Policy V5.1: un fence json valido con testo fuori è letto (testo scartato ma registrato) | Claude | Pilota V5: Sonnet A1_PAVE D = fence valido + commento; con V5 si perdeva C/K della cella. Motivata **a posteriori** | **da confermare** | sì, finché non parte il run vero |
| 6 | 16 nov | Retry unico: un solo secondo tentativo, solo per errore di trasporto senza output; primo tentativo conservato | Claude | Pilota V5: Gemini A0 K in PROVIDER_ERROR (0 token); stesso input rifatto 3/3 con successo (diagnostica). Precedente: OpenRCA 2.0 ritenta le chiamate API | **da confermare** | sì, finché non parte il run vero |
| 7 | 16 nov | Il pilota (archivi `rq2_v5_pilot_*`) non entra nei risultati | Claude | Evitare di usare stage di prova come dati | implicita | n/a |
| 7b | 16 nov | Pilota V5.1 (`rq2_v5_pilot_v2`, 9 stage, A1_PAVE, q032): 9/9 completi, nessun retry scattato, 0 fence+testo (Sonnet ha prodotto un fence semplice, mentre nel pilota V5 aveva aggiunto un commento: stessa cella, esito diverso). 3 K su 3 = insufficient_evidence | Claude | Osservazione, non decisione: conferma il limite "una sola esecuzione per cella" e che il percorso di retry reale non e' stato ancora esercitato | n/a | n/a |
| 7c | 16 nov | Congelamento del run di discovery: tutti i lotti usano lo stesso commit, fissato per SHA (`ddb2ca499c4b41aa32a36fdc2f9850cb09bb75c3`, branch `release/rq2-v5.1-discovery-v1` che non si modifica piu'), non la testa del branch di lavoro; aggiunto `release-orphan` (sblocco esplicito e motivato di uno stage interrotto) | Claude | Il branch continuera' a cambiare (esecutore K); i lotti del run devono girare sullo stesso codice | implicita | no, dopo il primo stage del run |
| 8 | da fare | Semantica dell'esecutore K: applicazione su ogni entità con il KPI; finestre scorrevoli; KPI assente = abstain; classe della regola = classe dell'incidente di discovery | Claude | Il formato K non fissa componente, finestra né classe | **da confermare** | sì |
| 9 | da fare | Criterio di "regola verificata", scritto **prima** di toccare gli incidenti sigillati | Claude | Evitare di scegliere il criterio guardando i risultati | da confermare | no, dopo l'apertura dei sigillati |

## Limiti dichiarati (da riportare nella tesi)

- Le decisioni #4, #5 e #6 sono motivate a posteriori su un pilota. Sono
  dichiarate, uguali per tutti i modelli, congelate prima del primo stage
  scientifico e non toccano contratti, parser, prompt né dati.
- Il codice è scritto da Claude Sonnet 5.5, che è anche uno dei tre modelli
  valutati: conflitto di interesse da elencare tra le minacce alla validità.
- Un incidente di discovery per classe e una sola esecuzione per cella:
  risultati descrittivi, nessuna affermazione statistica.
- Il refactoring finale non deve cambiare il comportamento del codice che ha
  prodotto i risultati: si lavora su un branch separato e il commit dei
  risultati viene etichettato con un tag.
