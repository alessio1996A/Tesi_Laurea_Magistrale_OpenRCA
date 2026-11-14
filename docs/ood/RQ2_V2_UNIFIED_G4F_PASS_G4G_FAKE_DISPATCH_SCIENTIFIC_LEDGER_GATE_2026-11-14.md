# RQ2-V2 unificata — G4F 22/22 PASS e G4G fake dispatcher → ledger scientifico

Data: 14 novembre 2026. Branch: `feature/rq2-v2-unified-five-harness-three-models-2026-11-14`.

## Risultato reale Windows/PyCharm

L'utente ha eseguito i nuovi test:
```text
Ran 22 tests in 22.053s

OK
```
Questo conferma il **G4F offline con ledger scientifico G4F vero su TemporaryDirectory**: claim O_EXCL, record create-only, SHA parent e readback, stati invalidi, no retry, release fake e lock locale. Non dimostra disponibilità/affidabilità lock su Google Drive/FUSE, né e' una release scientifica pagata.

Gates precedenti: G1 25, G2 9, G3A 23, G3B 9, G4A 18, G4B 18, G4D 17 eseguiti+2 skip symlink Windows, G4E 18; G4C verifica GT-free reale Colab `OK_NO_API`, hash completi documentati in `RQ2_V2_UNIFIED_G4C_G4E_VERIFIED_SHA_REPORT_2026-11-14.md`.

## G4G — nuovi file, NON ancora eseguiti

- `src/evaluation/rq2_v2_unified_dispatcher_offline.py`
- `src/tests/test_rq2_v2_unified_dispatcher_offline_e2e.py` (**17 metodi da eseguire**, uno comprende 15 combinazioni × D/C/K = 45 record).

Il dispatcher G4G **NON è il dispatcher API live**:
1. richiede marker fisico `.rq2_v2_unified_fake_dispatch_only` con byte fissi in una radice di test priva di Market, data/processed, data/rq2 e data/results;
2. richiede release dal ledger G4F con `approval_reference=SYNTHETIC_APPROVAL_NOT_REAL` e `approved_total_usd_limit="0.20"` — valori inventati e specifici per test; una release approvata sul serio viene RIFIUTATA;
3. richiede una classe `OfflineFakeGateway`; le sue implementazioni di test invocano i reali grafi LangGraph/ToolNode e il reale `run_experiment`, ma con `FakeDiagnosisLLM`, osservazioni inventate e SDK factory bloccata via patch;
4. ordine di stage e storage autentici: `claim D` prima del fake LLM, `record D` con provenance, prompt `prepare_cause_probe`→`claim C`→ fake C → record C → `prepare_candidate_rule`→`claim K`→ fake K → record K. Il journal usato è il **G4F SCIENTIFICO**, non il G3 sintetico;
5. errori fittizi `SimulatedProviderFailure` diventano `PROVIDER_ERROR` con meter completo dello stato *unknown*; dipendenze C/K `BLOCKED_DEPENDENCY`; malformed JSON/evidence IDs `INVALID_OUTPUT`, astensione C e `insufficient_evidence` K valide;
6. crash simulato `KeyboardInterrupt` non viene inghiottito, lascia claim irrisolto e impedisce nuovi tentativi; token receipt malformata non e' riparata e lascia claim per revisione; traiettorie con ID nativo incongruente devono essere invalide;
7. `can_execute_api` sempre falso, nessuna lettura Market/scorer/GT/cred, nessun Drive write.

**Criticità ancora aperte prima della prima API pagata**:
- Il gateway di produzione non esiste ancora; G4G è deliberatamente limitato a fixture fake. Il runner live dovrà integrare per-model SDK/provenance/error receipts senza filtri che cambino i denominatori.
- Il G4F ledger richiede release esterna; il test la crea sotto TemporaryDirectory con mock sorgenti e commit. Non chiamare questa release fittizia "frozen scientifico".
- La semantica di lock Windows locale non certifica Google Drive FUSE. Servono test multiprocesso/concorrenza e politica per orphan/partial artifact sulla destinazione.
- Meter e budget dovranno essere dimostrati per provider reali, incluso retry SDK e timeout; 492 è upper bound di graph invoke candidato, **NON** limite fatturabile di HTTP o USD.
- Codice G4F e futuro dispatcher live vanno aggiunti al nuovo inventario source-bound e congelati con SHA dopo i test; gli SHA G4C del commit precedente restano storici.

## Prossimo comando PyCharm

Assicurarsi che `git status --short` sia vuoto, quindi:
```powershell
git pull --ff-only
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_unified_dispatcher_offline_e2e.py" -v
```

**Attesi `Ran 17 tests` e `OK`, NON ancora attestati dall'utente**. Se emerge errore, correggere la sola fixture o il nuovo codice G4G con test negativo coerente; NON alterare codice RQ1 frozen, split, prompt C/K o il protocollo 180 stage.

Fasi seguenti: source binding del codice scientifico completo, controllo lock/FUSE e metering fake transport su provider, real dispatcher unificato, release immutable approvata, singolo pilot con consenso esplicito. Gli 11 OOD test restano bloccati per l'Opzione B dopo freeze discovery K.
