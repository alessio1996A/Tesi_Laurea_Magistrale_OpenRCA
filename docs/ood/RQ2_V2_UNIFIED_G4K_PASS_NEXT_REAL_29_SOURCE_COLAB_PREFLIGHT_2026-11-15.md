# RQ2-V2 unificata — G4K 18 PASS; Colab GT-free 29-source READ-ONLY

Data 15/11/2026. Branch: `feature/rq2-v2-unified-five-harness-three-models-2026-11-14`.

## Gate locali verificati
Output utente dopo fix sintattico della sola fixture G4K:
```text
Ran 18 tests in 6.276s

OK
```
**G4K 18/18 PASS**. Il precedente `SyntaxError` riga 185
nella fixture con `patch.object(... ) as factory` impediva del
tutto l'import del test; fix nel solo test commit
`e4c3e29187f5aaa199da17e19b2a57beb7e3e042`.
Il dispatcher reale mantiene `LIVE_API_ENABLED=False`.
**G4A inventory 19/19 PASS**: `Ran 19 tests in 0.379s; OK`,
`SOURCE_PATHS` include ora 29 sorgenti.
G4F 22 + G4G 17 + G4H 20 + G4I 24 + G4J 25 + G4K 18 +
G4A 19 = **145** metodi offline testati, NON casi OpenRCA reali.

## Perché nuova verifica Colab
L'audit G4C reale del 14/11 era su 15 sorgenti e commit
`33d5d8b28494d5bf41168d0a709854aa3134ea6a`.
Dopo G4F–G4K quel digest è storico, **non** valida la nuova
release. Sul branch GitHub risultano presenti tutti i 29
`SOURCE_PATHS`, ma occorre verificare gli hash **dal checkout
Colab clean pin al commit** contro i **due CSV GT-free originali**.

## Checklist unica cella Colab (no SDK)
Usare `/content/Tesi_OpenRCA_RQ2_Unified_Preflight` come checkout
separato, `/content/drive/MyDrive/Tesi_OpenRCA` per dati.
I soli CSV letti sono
`data/processed/split_market_v1.csv` e
`data/processed/benchmark_inputs_market.csv`.
La cella è fornita nel messaggio ChatGPT dopo l'ultimo commit docs,
con `EXPECTED_COMMIT` = **SHA esterno** del branch congelato
per questo audit (non derivare il pin automaticamente dal HEAD).

Cella: `git status --porcelain` clean, fetch e confronto
`FETCH_HEAD == EXPECTED_COMMIT`, checkout detached, nuova verifica
HEAD clean. Eseguire in sottoprocesso `python -B`,
`PYTHONPATH=REPO/src`:
`preview_unified_source_bound(DATA, REPO/src)` →
`build_unified_release_blueprint`. Assert:
`len(SOURCE_PATHS)==source_file_count==29`, set SHA per ogni file,
4 discovery × 5 harness × 3 modelli × D/C/K = 180 stage,
11 OOD locked, source RQ1 frozen verified, ground_truth_read=False,
`can_execute_api=False`, blueprint non autorizzante.
Stampare il JSON report con commit, source plan SHA, blueprint SHA,
split e manifest SHA, SHA C/K prompt, digest aggregato 29 sorgenti,
stage counts e flags NO API.

**Vietato** aprire `Market.zip`, `record.csv`, `query.csv`,
scorer, GT o telemetrie OOD; non fare pip/provider API;
non scrivere in Drive, non creare release/claim/output;
non riusare release e marker fake. Clone e fetch scrivono solo
nel filesystem temporaneo Colab `/content`.
Il check dello split utilizza solo metadata di allocazione
degli 11 OOD, non il contenuto dei relativi casi.

## Dopo output reale
1. Audit JSON e hash del codice finale. STOP su mismatch.
2. Provare semantica lock multiprocesso su Drive/FUSE in
   namespace scratch separato, senza toccare archivi storici.
3. Verificare runtime/SDK pin, tariffe attuali, limite operativo e
   consenso esplicito per **un solo stage D**. Budget operativo non
   è hard cap fattura/HTTP; 492 è limite di invocazioni graph candidate,
   NON numero HTTP massimo garantito.
4. Solo dopo nuova release verificata con SHA esterno, nuovo commit
   autorizzativo e stage approvato, pilot pagato (non ora).
5. Opzione B e tutti gli **11 OOD** restano locked.

Stato attuale: RQ2-V2 unificata **0/180 stage API**,
**0 release live firmate**, **nessun permesso API**.
