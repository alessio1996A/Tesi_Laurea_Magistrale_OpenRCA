# RQ2 — Sonnet q050, entrambi gli harness: verifica causale tecnica offline

**Data:** 13 novembre 2026. **Fonte:** output Colab dell'audit di sola
lettura `SONNET_CONT01_READ_ONLY_AUDIT`, comunicato dall'utente.
GIT_HEAD `06a054ca790eee3c46ca9b55043321714ed76719`.

## Integrità e perimetro

- `claims=31`; `finished_with_matching_result=31`;
  `unresolved_manual_review=0`.
- `result_archive_discovery_count=34`.
- **24 record Gemini e 10 record Sonnet** verificati con SHA.
- `sonnet_unattempted_stages=14` e `haiku_unattempted_stages=24`.
- C e K `cloudbed-1_q050 / Sonnet / A1` sono state verificate
  come `BLOCKED_DEPENDENCY`, create-only offline, nessun claim.
- `test_unlocked=false`.
- Audit: `PROVIDER_API_REQUESTS=0`;
  `DATA_FILES_WRITTEN=0`.

## Confronto dell'anomalia D sulla coorte q050

| Metadato | Sonnet / A1 / D | Sonnet / A1_8R / D |
|---|---|---|
| Record SHA-256 | `03c51f1260d0981a691bc8af381b1ed736220a54883919033250e14d37f66d10` | `d6d3c14cc1359b010b9320d17655c0a2b3db893235922cf9c7369bc2fdac6eea` |
| Esito | INVALID_OUTPUT | INVALID_OUTPUT |
| Causa `reason_code` | `AMBIGUOUS_TOOL_RESULT` | `AMBIGUOUS_TOOL_RESULT` |
| Eccezione evidence bundle | `EvidenceBundleError` | `EvidenceBundleError` |
| Stato JSON finale D | `valid_json` | `valid_json` |
| Errore provider | false | false |
| Eventi traiettoria | 24 | 12 |
| Tool calls | 12 | 6 |
| Tool results | 12 | 6 |

### Interpretazione rigorosa

La funzione congelata `build_evidence_bundle` richiede che il
risultato telemetrico sia associato univocamente alla rispettiva
chiamata tool. Il medesimo errore **per entrambe** le D Sonnet
su q050 documenta un problema di tracciabilità
dell'evidence bundle; la corrispondenza dei conteggi
calls/results da sola **non** prova un abbinamento univoco.

Il JSON D finale è valido in entrambe le esecuzioni.
Questo **non** dimostra correttezza rispetto alla GT.
Non sappiamo dai soli metadati se il problema derivi dalla
concorrenza dei tool, dai call ID legacy o da un'altra
specifica condizione di sequenziamento: non inferire oltre
la diagnosi tecnica `AMBIGUOUS_TOOL_RESULT`.
Non è corretto interpretarlo come una vittoria di A1 o A1_8R.

Il risultato originale INVALID_OUTPUT conserva il proprio
peso nel denominatore sperimentale. Nessun retry, riparazione
o modifica del parser è consentito all'interno della
campagna scientifica congelata.

## Conseguenze operative

1. La D Sonnet q050/A1_8R è archiviata e non richiamabile.
2. C e K dello stesso arm non potranno essere invocate;
   devono essere registrate come `BLOCKED_DEPENDENCY`
   offline, senza creare claim API.
3. L'arm indipendente successivo in ordine congelato:
   `cloudbed-2_q026 / sonnet / A1 / D`.
4. Servono prima un nuovo preflight integrità su 34 record
   e 31 claim, poi registrazione offline C/K, quindi
   continuazione create-only dei soli stage mai tentati.
5. L'accesso agli undici casi OOD di test rimane vietato
   prima di freeze e verifica indipendente della conoscenza.

Alla data di questo report i 34 file restano memorizzati
su Google Drive; il presente documento è soltanto
una registrazione testuale su GitHub.
