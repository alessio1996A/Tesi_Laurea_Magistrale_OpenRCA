# RQ2 — Driver D per il runner RQ1 reale, bloccato fino al release scientifico

**12 novembre 2026** · Branch `feature/ood-knowledge-transfer-audit-2026-11-10`. Documento di controllo del **percorso reale preparato ma NON abilitato**. Nella produzione la costante `RELEASE_SHA256=None`; **nessuna chiamata API RQ2 è stata avviata**.

## 1. Risultato confermato

L'utente ha riportato:

```
Ran 15 tests in 5.476s

OK
```

per `src/tests/test_rq2_ck_provider_transport.py`, dopo la correzione dell'helper chiamato `run` che interferiva con `unittest.TestCase.run`. **15/15 test superati**, con l'SDK sostituito da fake e release sintetico esclusivamente nel processo unittest. Il recorder additivo era già passato 20/20. Il budget economico non è limitato, per indicazione del relatore riferita dall'utente.

## 2. Nuovo modulo: `rq2_discovery_d_provider_transport.py`

Ingresso designato per un futuro esperimento reale D, con firma:

```python
run_one_claimed_discovery_d(
    data_dir=Path(...), repo_dir=Path(...),
    stage_id="rq2_dryrun_workflow_preview_v0:<caso>:<modello>:<harness>:D",
    confirm_paid_api=True,
)
```

La funzione segue questo ordine **fail-closed**:

1. Rifiuta ogni richiesta senza conferma specifica. Chiama `_read_release()` del trasporto C/K, che nella versione corrente rifiuta SEMPRE perché il file scientifico non è ancora congelato e la costante `RELEASE_SHA256=None`. Dopo un eventuale freeze autorizzato sarà comunque obbligatorio `enable_discovery_D=true` nel release **immobilizzato tramite SHA-256 nel codice**.
2. Controlla cartella repository e presenza non-symlink di `Market.zip`. Non legge il contenuto di `Market.zip` nel preflight (il motore RQ1 lo leggerà **soltanto durante la run**).
3. Esegue `preview_protocol_identity(src_root=repo_dir/"src")`: parità esatta dei blob RQ1 congelati, modalità D `v2_enforce` e SHA dei prompt di sistema C/K. Nessuna API.
4. Istanzia `RQ2DiscoveryStageRecorder` e `RQ2DiscoveryClaimJournal` **sulle sole fonti GT-free vere**, poi verifica hash del piano, split e manifest contro il release. Richiede uno stage **D discovery** pianificato, con zero dipendenze; i test OOD sono vietati.
5. Ri-esegue `preview_discovery_d_config(...output_contract_mode="v2_enforce")` per ricollegare il caso alla **finestra e all'istruzione originali**: non basta che il case ID sia nella lista. Verifica l'identità esatta modello/provid-er/harness e i sei round.
6. Costruisce una `ExperimentConfig` vera con `variant_scheme="current"`, `output_contract_mode="v2_enforce"`, `max_tool_rounds=6`, `recursion_limit=30`, indirizzi espliciti `repo_dir` e `data_dir`. Non aggiunge prompt, detector o regole alla RQ1.
7. **Prima della possibile chiamata API**, crea il claim esclusivo e persistente. Soltanto dopo chiama **l'originale `run_experiment(config,verbose=False,salva=False)`**: quindi nessun secondo motore RCA, nessuna scrittura nei risultati V3/RQ1.
8. Verifica che il dizionario ritornato contenga modello, caso, variante e modalità corretti. Se l'originale runner genera un'eccezione o una risposta con provenienza incoerente, **non inventa un record**: resta un claim senza artifact, `unresolved_manual_review`, e **non fa retry**.
9. Se il risultato ha identità congruente, passa il risultato **integro** a `RQ2DiscoveryStageRecorder.record_d`, che salva un file create-only con `tool_trajectory`, `metrics`, `raw_response`, `json_status` e stato; C userà solo evidenze E### ricavate dai tool. Non considera il solo JSON valido come prova di correttezza causale.

Le scelte `v2_enforce`, 6 round, recursion 30 e `current` derivano dal sorgente RQ1 Evaluation20 congelato (commit `e4845e7`). I modelli sono `gemini-3.5-flash-lite`, `claude-sonnet-5-5`, `claude-haiku-5-5`. Nessun hard cap USD, ma token e errori registrati.

**Limite importante:** il backend Gemini originale di RQ1 conserva i default della libreria: occorre verificare e preregistrare prima delle API la politica effettiva di retry e timeout delle dipendenze Google, senza modificare silenziosamente RQ1. La presenza di Market.zip non ne prova l'integrità interna; il preflight reale split+manifest e un futuro controllo di telemetria/source coverage restano necessari. Un claim lasciato senza risultato va esaminato con procedura operativa prima di qualsiasi reinvio, NON usato per modificare diagnosi (nessun human-in-the-loop diagnostico).

## 3. Test sintetici nuovi, non ancora eseguiti

`src/tests/test_rq2_discovery_d_provider_transport.py`: **12 metodi unittest predisposti**.

Nel test si riusano il `RQ2DiscoveryStageRecorder` e il `RQ2DiscoveryClaimJournal` su temp dir con due CSV sintetici. Il release finto viene creato e il relativo hash viene sostituito via monkeypatch **soltanto nel processo test**. `preview_protocol_identity` è simulato per i 13 blob storici, mentre il vero `preview_discovery_d_config` esercita il controllo sui CSV sintetici con checksum test-only. Il vero `run_experiment` è l'unico componente sostituito dal mock; la sua integrazione con LangGraph reale **era già stata verificata in una suite distinta 13/13**.

I 12 casi coprono: configurazione reale RQ1 invariata, source-bound D, claim prima della funzione runner, risultato salvato con metriche; richiesta senza conferma; release non congelato; attivazione D mancante; stage test rifiutato; Market.zip assente; manifest modificato; drift sorgenti RQ1; risultato che dichiara `legacy` respinto con claim non risolto; eccezione del runner senza retry; duplicato bloccato; errore provider restituito dal runner e conservato.

**Comandi PyCharm (dalla root):**

```powershell
git status
git pull --ff-only origin feature/ood-knowledge-transfer-audit-2026-11-10
$env:PYTHONPATH="src"
python -m unittest discover -s src/tests -p "test_rq2_discovery_d_provider_transport.py" -v
```

**Attesi 12 test, NON ancora confermati.** Non chiamare da terminale `run_one_claimed_discovery_d` con veri dati/credenziali adesso: il release non esiste. Non disattivare il gate per far passare una suite.

## 4. Prossimo passo — ultimo necessario prima del pilot

Dopo il verde:
- preparare una sola specifica **scientifica create-only** per le discovery (4 casi, 2 harness, 3 modelli, 24 D +24 C +24 K; le 11 test restano chiuse), con hash dei due CSV, RQ1 frozen, C/K system+builder, criteri KPI K e di errore/astensione; fissare un piano di scoring rigorosamente offline;
- documentare chiaramente le scelte di policy ancora aperte e i rischi (retry SDK, OOD class leakage, caso D con JSON invalido ma evidenze tool valide);
- validare l'identità del release in Colab preflight senza chiamate; **soltanto dopo** un'approvazione esplicita dell'avvio del pilot fissare hash, commit e lanciarlo sulla discovery, senza limite economico imposto;
- non toccare RQ1, non leggere GT nei prompt/tool e non usare gli 11 casi test prima del congelamento delle pseudoregole.

La campagna RQ2 è ancora `DRAFT_NOT_EXECUTABLE`, che è corretto fino al freeze.
