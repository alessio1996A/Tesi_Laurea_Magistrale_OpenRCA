# RQ2-V2 unificata — G3A ottimizzato PASS; G3B runner→journal fake E2E

Data: 14 novembre 2026. Stato della ricerca: **OPZIONE A in corso**, B successiva e 11 casi OOD TEST LOCKED. Nessuna nuova campagna reale avviata dalla matrice unificata.

## 1. G3A: verifica utente riuscita

Output reale PyCharm dopo ottimizzazione bounded per-audit della lettura dei record:

```text
Ran 23 tests in 20.434s
OK
STATUS: OFFLINE_PROFILE_INTEGRITY_OK
ALL_STAGES_SEC: 3.448
FINAL_AUDIT_SEC: 0.096
PROFILE_TOTAL_SEC: 3.546
CLAIMS_AND_RECORDS: 15 / 15
UNRESOLVED_CLAIMS: 0
MODEL_API_CALLS: 0
```

Benchmark prima/dopo sulla stessa macchina Windows:
- Suite G3A: 250.763s per 20 test pre-patch → **20.434s per 23 test post-patch** (durata ~12.27x più breve, NON stessi test).
- Profilazione identica su 15 stage sintetici: 31.956s → **3.546s** (~9.0x più veloce).
- `pathlib.Path.stat`: 213431 → **17219** chiamate (~91.9% in meno).
- `audit_restart`: 31 invocazioni, tempo cumulativo 30.085s → 1.796s.
- `FINAL_AUDIT_SEC`: 2.067 → 0.096 (21.53x).
- 15 claim + 15 stage record integri, zero orfani, nessuna API, no GT, no dati Market reali.

**Interpretazione:** conferma concreta del costo della ricalcolazione ricorsiva degli stessi record nello stesso audit. La cache locale a un singolo `audit_restart` ha ridotto la ridondanza e i tre test antimanomissione di G3A sono PASS. **Non** implica protezione garantita contro processi concorrenti o prestazioni adeguate già misurate per 180 stage reali; quel dimensionamento rimane da valutare.

## 2. G3B: nuovi test di integrazione, NON ancora eseguiti

File aggiunto:
`src/tests/test_rq2_v2_unified_runner_to_journal_fake_e2e.py`

**9 metodi unittest scritti, non ancora eseguiti**. Uno copre le **15 combinazioni** (3 provider logici × 5 harness) e produce **45 stage sintetici D/C/K** nell'archivio temporaneo. I metodi supplementari verificano: origini `llm/planner`, D JSON invalida con C/K bloccati, C con `E999` falsa e K bloccata senza claim, K `E999` archiviata come `INVALID_OUTPUT`, astensione C + K `insufficient_evidence` validi, provider failure 503 puramente simulato con dipendenze bloccate, orphan claim dopo crash simulato, nessuna lettura Market/GT o destinazione storica.

Il percorso `run_experiment` e' quello RQ1 inalterato. Per A0/A1/A1_8R viene sostituito soltanto in RAM l'esecutore ReAct con `esegui_grafo_rca_v2`; Planning/PAVE usano `verify_graph` autentico con verifica deterministica. `prepara_esperimento` è stub con dati **inventati**, anche se il `case_id` è quello ammesso in discovery. `crea_modello` è esplicitamente bloccata e `llm` è `FakeDiagnosisLLM`. I tool sono veri oggetti ToolNode, ma i loro valori sono fixture. Per C e K vengono usati `rq2_probe_adapter` e validatori reali con output di `FakeToolFreeModel` (content blocks Sonnet/Haiku inclusi). Ogni stage eseguito crea **claim PRIMA della simulazione dell'invocazione** e salva record SHA e dipendenze in modo create-only. La prova verifica claim/record/parent SHA e impossibilità di retry.

**Non è ancora un dispatcher scientifico live**: l'orchestrazione e' contenuta nel test e non possiede un'API di produzione. Persistenza sempre e soltanto in `TemporaryDirectory` con marker synthetic-only, nessuna scrittura Drive, no API, no scorer o GT, zero OOD test.

## 3. Gate PyCharm proposto

Assicurarsi che lo stato `git status --short` sia vuoto, quindi eseguire:
```powershell
git pull --ff-only
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_unified_runner_to_journal_fake_e2e.py" -v
```

Attesi **9 metodi di test**, inclusa una prova a 15 sottotest, ma **non dichiarare G3B PASS prima dell'output reale dell'utente**. Se fallisce, preservare i risultati, diagnosticare la distinzione fra fake data, parser e journal, correggere tramite Git commit tracciabile senza modifiche alla RQ1 congelata.

Dopo eventuale PASS: audit di correttezza nel passaggio da questi test di integrazione ad un **dispatcher unico per la vera discovery** con **release source-bound** (SHA codice/manifest, repository atteso, modello, prompt C/K, timeout/quote, commit, no retry, budget, readback, fail closed). Verificare la gestione di concorrenti/claim orfani e compatibilità provider. Pilot pagato G4 non ancora autorizzato.
