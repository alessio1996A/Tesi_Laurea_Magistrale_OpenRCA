# RQ2 — Audit Gemini V1 di sola lettura: 8/8 test PASS

**Data di registrazione:** 13 novembre 2026.
**Branch:** `experiment/rq2-provenance-v2-offline-2026-11-13`.
**Fonte:** riepilogo eseguito in PyCharm e riportato dall'utente.
**Stato:** gate mirato del nuovo modulo; **non** ancora eseguito contro gli artefatti Gemini reali di Google Drive.

## Esito osservato

```text
Ran 8 tests in 0.011s

OK
```

File: `src/tests/test_rq2_v1_gemini_readonly_audit.py`.

La precedente esecuzione degli otto test aveva riportato **7 PASS / 1 FAIL** a causa della
verifica errata `assertNotIn("ground_truth", str(result))`, che intercettava il flag
legittimo `"read_ground_truth": False`. La sola asserzione è stata cambiata nel
commit `1cbcd88d838cbbeacfb012c8b33f35765641a543` per controllare la presenza
della **chiave** esatta nel report e nei singoli riepiloghi.
Il codice di lettura, il report Gemini e la persistenza V1 non sono stati modificati.

## Verifica statica di compatibilità con V1

Ispezionati i sorgenti originali:
- `rq2_stage_artifact_store.py:_check_record`: i record contengono
  `logical_model`, `phase`, `stage_id`, `model_id_proposed`,
  `dependency_record_hashes`, `status`, `artifact`; lo store
  controlla digest, source hash, identità e stage dependencies.
- `rq2_discovery_claim_journal.py:_read_claim`: i claim contengono
  `model_id_proposed`, `dependency_record_hashes`, `attempt_number`
  e `authority`, e sono verificati dal journal.
- L'audit Gemini invoca il `RQ2DiscoveryClaimJournal` reale in
  modalità read-only e legge **solo i 24 stage Gemini discovery**,
  senza aprire Market.zip, ground truth o i casi OOD test.
- L'audit legge tutti i claim/record indirettamente per
  riconciliare il journal; l'output è soltanto aggregato
  e non stampa dati raw del modello né diagnosi/GT.

La compatibilità **statica** non sostituisce il readback su Drive.
Non dichiarare le categorie reali delle otto K senza eseguire
l'audit su archivio originale verificato.

## Prossimo gate

Eseguire la suite globale aggiornata:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_*.py" -v
```

L'ultima suite globale confermata era `844/844 PASS`;
sono stati aggiunti **8** test specifici, quindi il nuovo
totale previsto è **852**, da confermare localmente.
Dopo il PASS globale: preparare/eseguire in Colab
una **singola cella di audit read-only** che fissi
la SHA di branch/code, controlli i sorgenti GT-free V1
e chiami:

```python
from pathlib import Path
from evaluation.rq2_v1_gemini_readonly_audit import audit_real_gemini_discovery
result = audit_real_gemini_discovery(data_dir=Path("/content/drive/MyDrive/Tesi_OpenRCA"))
```

La cella non deve eseguire provider o scrivere su Drive:
non servono chiavi API. Usare un checkout isolato,
non sovrascrivere la vecchia cartella Colab RQ2 V1,
e non modificare i risultati dei tentativi già registrati.

**Stato scientifico inalterato:** Gemini V1 24/24 stage registrati
(22 complete, 1 invalid C, 1 blocked K); le K `candidate`
restano `requires_verification`, e non vi è freeze/permesso OOD.
