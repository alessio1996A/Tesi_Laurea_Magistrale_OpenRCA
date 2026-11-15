# Handoff RQ2 V3 — equità D/C/K e piano GT-free (15 novembre 2026)

## Stato scientifico e identità congelate

Tesi magistrale OpenRCA / Harness Engineering per RCA. RQ1 è congelata (Evaluation20: 300 tentativi, 295 complete, cinque errori provider). Non ripetere esperimenti o riscrivere scoring.

RQ2-V2 source commit: f0b64a36b08c2ae5db424b544965db5362190377. Release SHA256: af1867e2539edbb42cf27ae92c602dfacca1c12968475235955fb1cf0ed2dac4. Pilot Gemini A0 cloudbed-1_q032: D completo; C INVALID_OUTPUT (record SHA 51946d926aa2a5a0f9dd2ba997d8565116ef8158a2af44df5d0051d73ee3f4b1); K BLOCKED_DEPENDENCY. Non alterare i record, non rifare il pilot, non riclassificare C.

La risposta C contiene una newline letterale non escapata nel valore schema_version. Il record conserva testo dopo l'estrazione, NON i content block originari: non sappiamo se l'errore reale sia nato nel modello o nell'adattatore. I test riproducono il rischio nel codice congelato, ma NON autorizzano una correzione retroattiva.

La discovery continua a mantenere 11 casi test/OOD bloccati, nessun accesso a GT/Market/scorer; niente human-in-the-loop operativo. Budget USD 100 operativo, NON hard cap. L'approvazione precedente della release V2 NON approva stage della futura V3.

## Test offline riportati da PyCharm

45/45 PASS comunicati dall'utente: 4 sul rischio originale; 9 sull'estrattore esatto; 6 sull'integrazione C/K simulata; 9 sul trasporto candidato; 3 sulla compatibilità con il ledger sintetico; 7 sul contratto di provenienza C/K; 7 sul journal create-only in TemporaryDirectory. Nessuno ha fatto API reali.

## Nuovo branch e file pre-release

Branch: feature/rq2-v3-gtfree-equal-comparison-design-2026-11-15. Derivato da audit/rq2-v2-ck-multiblock-fairness-2026-11-15.

- src/evaluation/rq2_v3_unified_gtfree_discovery_plan.py: piano OFFLINE con nuovo protocollo rq2_v3_unified_equal_ck_extraction_discovery_v0, namespace proposto data/rq2_v3_unified_scientific_v1, identità nuove per 180 stage su 4 incidenti discovery, 5 harness, 3 modelli e 3 fasi D/C/K. Mantiene stessa coorte, stesso budget D e stessi prompt C/K; non riutilizza vecchi D/C/K della V2.
- src/tests/test_rq2_v3_unified_gtfree_discovery_plan_offline.py: 8 test nuovi, ancora da eseguire in PyCharm. Verificano identità, SHA, pairing, OOD e blocchi API.
- src/tests/test_rq2_v3_d_contentblock_audit_offline.py: 5 test nuovi, ancora da eseguire in PyCharm. Verificano i due esecutori D con grafo simulato e content block frammentati, senza chiamate provider.

## Nuova scoperta metodologica: problema possibile anche in D

Gli esecutori agent/rq2_v2_graph_engine.py (A0/A1/A1_8R) e agent/verify_graph.py (A1_8R_Planning e A1_PAVE) estraggono il JSON finale D con la stessa funzione testo_messaggio(..., solo_testo=True). Se la risposta è frammentata in più blocchi, il codice può introdurre newline artificiale anche in D, non solo in C/K.

Dunque la politica finale deve diventare **uniforme su D e C/K** nel successore, senza modificare il comportamento storico del logger dei tool e senza toccare RQ1. Il piano V3 resta esplicitamente BLOCCATO perché l'integrazione D e la sua provenienza NON sono ancora state implementate.

## NO-GO attuale e passi successivi

1. Eseguire soltanto gli 8 test del piano e i 5 test sul D, attualmente PENDING. Nessuna ripetizione dei 45 test PASS.
2. Creare l'integrazione finale D e relativo schema di provenienza, **solo nella versione successore**, e fare un adattatore C/K capace di interpretare nuovi stage ID V3: il candidato attuale normalizza ancora ID V2 ed è incompatibile con un vero piano V3.
3. Preparare ledger, source inventory, release contract e dispatcher V3 rigorosamente distinti e source-bound (commit clean, SHA, namespace create-only, dipendenze, no automatic retry, singolo writer, audit restart).
4. Verificare uniformità SDK/runtime, conteggio token e no-GT. Preflight Colab read-only, freeze, autorizzazione separata, poi una sola stage reale.
5. Non mescolare i risultati delle due versioni nella stima primaria. Separare affidabilità provider, validità JSON, accuratezza diagnostica, astensione, K bloccata, costi e qualità delle regole.

**Stato conclusivo: nessun nuovo freeze, nessun stage pagato, nessuna release V3 attiva.**

## Audit V3 dei motori D dopo 58 test PASS — integrazione candidata non attiva

Il 15 novembre sono stati riportati altri 13/13 test PASS su PyCharm: 8 piano V3 GT-free e 5 audit dei due motori D. Totale dell'indagine: **58/58 test mirati PASS**, tutti offline e senza API.

Implementazione candidata: `src/evaluation/rq2_v3_d_final_stream_candidate.py`. Un delegatore monouso di `graph.stream()` opera esclusivamente sui messaggi finali AI, conserva l'originale e ne passa una copia con testo esatto a `esegui_grafo_rca_v2()` (ReAct) o `esegui_grafo_rca_verify()` (Planning/PAVE). Riusa lo stesso estrattore C/K e registra un envelope `d_final_text_extraction` (schema/policy/kind/text_blocks/nontext_blocks). Non modifica il codice dei grafi, le risposte tool, i budget o il metering. Non ripara JSON malformati. In caso di errori/ambiguità non inventa una diagnosi. Non è ancora collegato a experiment_runner o al ledger e non costituisce un nuovo protocollo attivo.

Test da eseguire in PyCharm: `src/tests/test_rq2_v3_d_final_stream_candidate_offline.py`, **9 nuovi test PENDING**: frammenti D sui due motori, preservazione di stringhe, mancata riparazione, esclusione thinking, tool native ID, errori di finalizzazione, duplicati finali, limite blocchi, single-use. Nessuna API; non ripetere i 58 test conclusi.

**Vincoli aperti per un futuro GO:** collegare D al runner sperimentale V3 in modo source-bound, includere la provenienza D nel contratto e ledger V3; separare stadi/namespace/release dalla V2. Il modello e l'SDK possono produrre forme diverse di content block; i mock dimostrano la correttezza del nostro adattatore su casi sintetici, non la causa della risposta Gemini V2. Nessun nuovo stage pagato è autorizzato.
