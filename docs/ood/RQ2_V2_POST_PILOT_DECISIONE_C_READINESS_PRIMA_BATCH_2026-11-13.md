# RQ2 V2 — Decisione post-pilot: C readiness offline prima di nuove chiamate API

**Data:** 2026-11-13. **Stato:** `PROPOSED_NEXT_GATE_GT_FREE` / `NO_API_RELEASE_FOR_CK` / `OOD_LOCKED`.

## Fatto tecnico

Il pilot V2 source-bound `cloudbed-1_q050/sonnet/A1/D` ha prodotto un record autentico `RECORDED_COMPLETE`, hash `521ed45b3dfefe6fd6c21427ca1c4ac0d03edbb1608bf80cbc424109c9f1a009`; successivo audit read-only `SONNET_V2_REAL_PILOT_READONLY_AUDIT_OK`, 8/8 tool call-result matched da 8 ID nativi unici, 7 richieste LLM, 139155 token totali, costo stimato $0.301102, `same_name_parallel=False`. D da conservare senza retry. Nessuna C/K o OOD eseguita.

## Decisione metodologica proposta

**Non** ripetere D e non partire ancora da un batch di 5-10 nuove API.
Prima ricavare un pacchetto C deterministico e **GT-free** dalle evidenze gia' congelate:
1. leggi solo il manifest GT-free, confronta l'hash della instruction originale con il source binding;
2. rileggi claim/record source-bound, verifica l'hash di record e l'assenza di errori;
3. ricostruisci il bundle da `diagnostic_run.tool_trajectory` con `build_evidence_bundle` e verifica `bundle_sha256=f63f1f0fd744497acc92814d8aabf80fb30cb08d8e5244ec62501d29052154d6`;
4. prepara C con `prepare_cause_probe`, che usa soltanto instruction ed evidenze, **non** il raw della diagnosi D; verifica dimensione, schema, package SHA, no API;
5. stampa SOLO hash e conteggi, **non** prompt/telemetria/GT/chiavi. Non creare claim o file, non invocare provider.

Se C package supera `MAX_PAYLOAD_CHARS=45000`, non troncare né alterare a posteriori il validatore: fermare la preview e documentare il limite per deliberare un protocollo nuovo.

## Roadmap sperimentale condizionata (da non eseguire automaticamente)

- **Gate A:** C readiness su q050/Sonnet/A1, read-only.
- **Gate B:** definire e congelare, **su nuovo namespace/protocollo**, C dipendente dal record D originale, con release, claim create-only e nuovo output validato da `validate_cause_probe`. Una C è una nuova stage con un provider call; non riutilizzare l'autorizzazione della D passata.
- **Gate C:** solo dopo C valida, definire K con `prepare_candidate_rule`, `validate_candidate_rule`, formalizability GT-free e parent SHA D+C. Se C invalid, K bloccata senza claim/provider. K candidata NON è automaticamente eseguibile e non è una prova di transfer.
- **Gate D:** se i risultati sono utili e le tempistiche lo permettono, nuove D/C/K discovery Sonnet a confronto A1 e A1_8R su casi predefiniti (4 discovery), con blocchi **sequenziali di al massimo 5 stage**, SHA e readback tra blocchi, mai 5 retry. Haiku solo con ipotesi e costi approvati separati. Non aggregare V1 e V2 come protocollo comparabile.
- **Gate E:** verificare GT-free la formalizzabilità delle due K Gemini V1 gia' candidate (q026/A1 e q045/A1) senza rianimare record V1. Solo dopo freeze delle regole deterministiche, eventuale test OOD su 11 query/10 gruppi richiederebbe protocollo/scorer isolati e consenso scientifico.
- In ogni passaggio: stop su errore, origine dati GT-free, non human-in-the-loop. Solo dopo freeze esperimenti: refactoring/commenti in italiano/pulizia, poi stesura tesi. Termine 1 dicembre 2026.

**Nota:** pianificare batch non significa averne autorizzato o realizzato alcuno. Il budget ampio comunicato dall'utente non rende validi claim riutilizzati, scorers in runtime o nuovi test OOD prima del freeze.
