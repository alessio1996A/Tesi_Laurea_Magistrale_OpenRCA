# RQ2-V2 — Rubrica K preregistrata: misure verificabili senza GT

**Data:** 15 novembre 2026, **prima delle 180 esecuzioni RQ2-V2 con provider reali**.  
**Stato:** schema di valutazione preregistrato e indipendente dai risultati futuri.  
**Scopo:** confronto esplorativo 5 harness × 3 LLM × 4 incidenti *discovery* (60 D + fino a 60 C + fino a 60 K), senza ottimizzare il criterio sui risultati.  
**Vincolo:** nessuna modifica ai prompt D/C/K o ai contratti JSON; nessuna lettura di ground truth, fault labels ufficiali, scorer, predizioni storiche o 11 casi OOD. La fase Opzione B resta separata e locked.

## 1. Unita' di analisi, denominatori

L'unita' primaria per confronti e' (incidente discovery, modello, harness), con i tre stage dipendenti D → C → K. Ogni arm/caso rimane nel denominatore preregistrato, anche se D o C fallisce e K e' `BLOCKED_DEPENDENCY`; nessuna selezione delle sole risposte valide per il risultato principale. Raggruppamenti temporali e incidenti vanno rispettati nell'incertezza statistica; n=4 e' esplorativo.

La rubrica **non modifica** lo stato scientifico G4F del ledger. Opera solo su snapshot auditati della K gia' registrata, con il tool trajectory D originale, usando `build_evidence_bundle` e `validate_candidate_rule` esistenti. Le analisi per modello/harness includeranno separatamente:
- D: completamento, invalidita', errori provider, provenance;
- C: diagnosis, abstain, invalidita', blocked;
- K: candidate, insufficient_evidence, invalid_output, blocked;
- per K candidate: misure strutturali e meccaniche qui fissate;
- costo/latency/usage completeness con errori e denominatori espliciti.

## 2. Esiti di K: distinzione obbligatoria

| `k_outcome` | Interpretazione |
| --- | --- |
| `BLOCKED_DEPENDENCY` | D/C upstream non rendono K eseguibile; deriva dal ledger, mai da parser inventato |
| `PROVIDER_ERROR` | Il provider non ha restituito un output utilizzabile; deriva dal ledger |
| `INVALID_OUTPUT` | Stringa K non conforme al JSON contract rigoroso; non riparare |
| `INSUFFICIENT_EVIDENCE` | Astensione legittima esplicita della K, *non* regola errata |
| `CANDIDATE` | JSON K strutturalmente valido, **non** correttezza diagnostica |

La valutazione pura di `raw_response` si applica solo alle K che hanno una risposta. `BLOCKED_DEPENDENCY` e `PROVIDER_ERROR` devono essere ricostruiti dal ledger, senza simulare risposte inesistenti.

## 3. Indicatori deterministici conservativi per le sole K candidate

1. `cited_evidence_count`: numero di riferimenti E### validi nella allowlist del **bundle costruito dalla traiettoria D**. Il JSON validator fail-closed respinge riferimenti inesistenti/duplicati.
2. `cited_nonempty_observations`: quanti E### puntano a osservazioni non vuote. Le osservazioni sono non fidate e una presenza non dimostra veridicita'.
3. `cited_truncated_observations`: quanti E### sono troncati; `False` non significa che il log originale fosse completo.
4. `required_signal_count` e `condition_count`, insieme alla presenza obbligatoria di `abstain_when`, `counterexamples`, `limitations` secondo il contratto vigente (non aggiungere reward per prolissita').
5. `signal_metric_literal_matches`: per ciascun `required_signal`, verificare se il nome metrico compare **letteralmente** nel testo di almeno una osservazione citata, con confronto case-insensitive e delimitatori per non confondere sottostringhe. Un match non dimostra l'esistenza semantica della metrica.
6. `signal_metric_unit_literal_matches`: lo stesso criterio per metrica **e unita' nello stesso testo citato**. Una semplice co-occorrenza di parole non certifica l'unita' ne' che la misura sia stata osservata.
7. `contradictory_all_conditions`: per `combination=all`, identificare su uno stesso segnale vincoli numerici matematicamente incompatibili (per esempio `x>10` insieme a `x<=10`; uguaglianze diverse). Per `any`, non trattare come contraddizione globale condizioni alternative.
8. `formalizability_review`: `NOT_FORMALIZABLE_CONTRADICTION` soltanto per contraddizione matematica dimostrabile nel caso `all`; altrimenti `REQUIRES_VERIFICATION`. Non attribuire mai automaticamente `VERIFIED_FORMALIZABLE` dalla sola struttura. Per `INSUFFICIENT_EVIDENCE`/`INVALID_OUTPUT` usare `NOT_APPLICABLE`.
9. Campi sempre falsi: `physical_units_verified`, `thresholds_empirically_validated`, `diagnostic_correctness_verified`, `causal_transfer_verified`, `ood_test_performed`. Nessun pseudocodice K viene eseguito.

Il codice deve **fail closed** quando la provenance D e' ambigua/incompleta, senza convertire l'assenza di prova in K invalida. In output niente testo grezzo sensibile o query/ground truth, solo indicatori e digest del bundle. La valutazione e' *meccanica*, non una validazione semantica indipendente.

## 4. Scoring e confronto (prima degli output)

Il report principale e' una tabella dei conteggi con denominatore intero fissato: 60 arm/caso per D; 60 C e 60 K pianificate, inclusi eventuali blocked. Report secondari condizionati alle K candidate possono mostrare le distribuzioni degli indicatori meccanici senza assumerli come accuratezza o costruire un punteggio arbitrario unico.

Confronti appaiati tra gli harness **sullo stesso incidente + modello** e tra LLM **sullo stesso incidente + harness**; evitare selezione post-hoc del migliore e non dichiarare significativita' forte con quattro incidenti. Conservare astensioni, errors, token e tempi.

**L'assenza di regole verificabili e' un risultato scientificamente accettabile.** Non adattare la rubrica in base ai risultati RQ2-V2. Per valutare davvero generalizzazione, servira' una futura preregistrazione separata dell'Opzione B, con regole congelate e 11 OOD intatti.

## 5. Separazione dal software live

Questo strumento e' *solo per analisi post-run*: non entra nella costruzione di D/C/K, non usa provider/API e non cambia metering, ledger, stage o prompt. Va incluso in source fingerprint della futura release o pinning equivalente dichiarato. Non alterare codice o score RQ1. `LIVE_API_ENABLED=False`, nuova V2 `0/180`, OOD test locked.

## 6. Ultima fase di manutenzione

Solo **dopo** esperimenti e audit: refactoring del repository su branch dedicata, commenti/docstring in italiano, eliminazione ragionata di file superflui con tracciabilita' Git/manifest preservati. Non modificare a posteriori le metriche preregistrate.
