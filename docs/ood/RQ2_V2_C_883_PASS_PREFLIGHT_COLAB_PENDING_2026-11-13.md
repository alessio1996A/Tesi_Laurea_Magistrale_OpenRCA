# RQ2 V2 Sonnet C — gate PyCharm 883/883 PASS, prossimo preflight reale Colab

Data: 13 novembre 2026. Documento di continuità in branch separato dal commit scientifico, **nessuna modifica a V1/D**.

## Risultati verificati dall'utente

- Nuovo branch C: `feature/rq2-v2-sonnet-c-sourcebound-2026-11-13`.
- HEAD GitHub verificata: `d1d1d2eb20d030a2bb0da76ebc3c1d9f82e469ce`.
- Prima esecuzione 16 mirati: 15 OK, 1 ERROR fixture mancante `schema_version`, corretto soltanto nel test e rieseguito.
- Riesecuzione: `Ran 16 tests in 0.601s / OK`.
- Suite regressione completa: **`Ran 883 tests in 87.286s / OK`**.
- I test sono *software*, non 883 diagnosi/provider run.

## Parent D reale, congelata e verificata

- Commit D: `bf2b0a0a67977a65c79d47ada4b07e825eaf8dff`
- D release: `c07e0aaa19b6cc1826e532c7da89e856c68e73975be84f572a727c09c7580813`
- D source binding: `05c1c12072432e6ee7332802142dd709a6a9adfbf71845615274bbd927240f0b`
- D claim: `ec058cb6f061f9c342b4a54a7aa037b1d8de7242ba6b91c17cf22976a66dc29e`
- D record: `521ed45b3dfefe6fd6c21427ca1c4ac0d03edbb1608bf80cbc424109c9f1a009`
- D evidence bundle: `f63f1f0fd744497acc92814d8aabf80fb30cb08d8e5244ec62501d29052154d6`
- D unica nuova run `cloudbed-1_q050/sonnet/A1/D`, `RECORDED_COMPLETE`, 8 paired tools, no parallel same-name observed, 7 invocazioni LLM, input 136306, output 2849, USD stimati 0.301102, 0 C/K/ODD.

## Readiness C su commit D precedente, GT-free

```text
STATUS: SONNET_V2_C_READINESS_OK
EVIDENCE_COUNT: 8
EVIDENCE_TRUNCATED: 3
C_PACKAGE_SHA256: 49422ee1f91909514acc3cdf5868aa5c4e73990392804fe7b1fa8dec950e333f
C_SYSTEM_PROMPT_SHA256: 81a5800500b3fafc23af4b7643e79a3d206c3ca6c80f6924514001ec85dc2a42
C_PROMPT_CHARS: 18084
API_CALLS: 0
FILES_WRITTEN: FALSE
OOD_TEST: LOCKED
```

## Gate successivo

- Clone su checkout temporaneo separato `/content/Tesi_OpenRCA_Sonnet_V2_C_Preflight`, pin HEAD C esatta e working tree pulito;
- riusa le dipendenze Colab in directory `/content/rq2_sonnet_v2_preflight_deps` dopo verifica marker SHA e runtime SDK;
- senza credenziali provider invoca `preview_c(data_dir=Drive,repo_dir=checkout)` sul record D esistente, controlla tutti i digest parent e il package C;
- controlla che il namespace indipendente `data/rq2_v2_provenance/sonnet_q050_c_v1` non esista ancora;
- stampa solo nuovo `c_binding_sha256`, `code_commit`, `parent_record_sha256`, `c_package_sha256`, nessun raw, nessuna API, nessuna scrittura.

Se fallisce, fermarsi e non creare release/claim. Se passa, congelare una nuova C release canonica create-only (solo `cloudbed-1_q050/sonnet/A1/C`, max 1 richiesta, zero retry, soglia USD proposta 5 non hard cap), leggere/validare SHA, poi ottenere autorizzazione alla singola C reale. La release D non autorizza C. K e test OOD ancora LOCKED. Mai rielaborare i 39 record V1 o ritentare D.

Scadenza tesi: 1 dicembre 2026; dopo il freeze risultati, refactoring/commenti italiani/pulizia, quindi scrittura.
