# RQ2 V2 — Sonnet C: postmortem EMPTY_RESPONSE e successore ContentBlocks V2

**Data:** 2026-11-13. **Stato:** `OFFLINE_CODE_NOT_YET_TESTED`, `NO_NEW_API_RELEASE`, `NO_RETRY_ORIG_C`, `OOD_TEST_LOCKED`.
**Contesto:** tesi magistrale, harness/RCA OpenRCA, consegna 2026-12-01.

## Evidenza reale (frozen, NON modificabile)

Stage `rq2_v2_sonnet_q050_c_sourcebound_v1:cloudbed-1_q050:sonnet:A1:C`, Sonnet 5.5, A1, q050; 1 API; release SHA `a98dd76b962cf6ae37978c9fc362fa354ec375fd1f69f5d6ab605963c7f7853c`.
C real status: `INVALID_OUTPUT`, `C_JSON_CONTRACT`, record SHA256 `39364800134f3713302a6f314822930b501a4300af6d62a12f7ce376a93f0579`, claim SHA256 `071ab6c3b860b875bcf9fd2b2ac21a0e10c3cc80a7a6f79aaf64e33c78aac3a5`. 1 provider call, input 7702, output 1019, stimato $0.025594. D parent record SHA `521ed45b3dfefe6fd6c21427ca1c4ac0d03edbb1608bf80cbc424109c9f1a009`, D bundle `f63f1f0fd744497acc92814d8aabf80fb30cb08d8e5244ec62501d29052154d6`.

Audit Colab read-only successivo `SONNET_V2_C_INVALID_READONLY_AUDIT_OK`:
```text
STAGE_STATUS: INVALID_OUTPUT
CONTRACT_ERROR_CATEGORY: EMPTY_RESPONSE
RAW_RESPONSE_CHARS: 0
RESPONSE_EMPTY: True
STARTS_WITH_MARKDOWN_FENCE: False
STARTS_WITH_JSON_OBJECT: False
JSON_PARSEABLE: False
JSON_IS_OBJECT: False
RECORD_SHA256: 39364800134f3713302a6f314822930b501a4300af6d62a12f7ce376a93f0579
API_CALLS_DURING_AUDIT: 0
FILES_WRITTEN_DURING_AUDIT: FALSE
K_EXECUTED: FALSE
OOD_TEST: LOCKED
```

## Bug sorgente dimostrato e limite della prova

Il modulo frozen C V1 (`src/evaluation/rq2_v2_sonnet_c_sourcebound.py`, commit `d1d1d2eb20d030a2bb0da76ebc3c1d9f82e469ce`) estrae la risposta con:

```python
if type(response.content) is str:
    raw = response.content
else:
    raw = ""
```

Questo perde **qualunque lista** di content blocks LangChain, anche se include un blocco Anthropic `{"type":"text","text":"..."}`. Il progetto ha già una funzione verificata in `agent.graph_engine.testo_messaggio(...,solo_testo=True)` per estrarre il testo senza thinking/signature/tool-use; la copertura esiste in `test_anthropic_content_block_extraction.py`.

**Non sappiamo quale forma effettiva abbia avuto la risposta della singola C V1**, poiché il record salva `raw_response=""` ma non la forma originale di `response.content`. I 1019 output token non provano testo visibile né correttezza; quindi la relazione causale tra bug e INVALID_OUTPUT reale e' **plausibile, non accertabile retroattivamente**. In nessun caso il parser V1 o la classifica V1 vanno modificati.

## Nuovo protocollo engineering V2 (futuro, separato)

Branch: `feature/rq2-v2-sonnet-c-contentblocks-v2-offline-2026-11-13`, base frozen `d1d1d2e...`.

Nuovo modulo `src/evaluation/rq2_v2_sonnet_c_contentblocks_v2.py` derivato dall'esecutore C V1 per **un solo esperimento tecnico** su q050/A1/Sonnet, con:
- Nuovo `PROTOCOL=rq2_v2_sonnet_q050_c_contentblocks_v2`, nuovo `STAGE_ID`, nuovo root `data/rq2_v2_provenance/sonnet_q050_c_contentblocks_v2`.
- La release C originale **non autorizza** questo protocollo: nuovo release hash e `CONTENT_EXTRACTION_POLICY=text_blocks_only_v1`, pin source/head, hash parent D, pacchetto C identico, SDK pin, 1 request, no retry, no K/OOD.
- `extract_visible_response` usa `testo_messaggio(...,solo_testo=True)` per `AIMessage.content` in lista, esclude thinking/signature, non ripara JSON e lascia `""` se non c'e' testo visibile.
- Nuovo record con `response_content_kind`, `text_blocks_observed`, `nontext_blocks_observed` per distinguere output string/lista/unsupported, non serializza reasoning/signature.
- Ripete gli stessi freeze SHA parent D, 8 evidenze, 3 troncamenti, pacchetto C `49422ee1f91909514acc3cdf5868aa5c4e73990392804fe7b1fa8dec950e333f`.
- L'output C originale `INVALID_OUTPUT` deve restare nel denominatore del protocollo originale; **un successore dopo analisi dell'errore non e' una prova indipendente** né un retry del medesimo stage. Documentarlo come targeted engineering correction.

Test nuovi: `src/tests/test_rq2_v2_sonnet_c_contentblocks_v2_offline.py` con **21 test** (16 casi V1 adatti al namespace nuovo + 5 controlli di blocchi). Tutto esclusivamente sintetico/mock; nessuna API e nessuna lettura GT.

## Gate PyCharm, non ancora verificato

```powershell
git status --short
git fetch origin
git switch --track origin/feature/rq2-v2-sonnet-c-contentblocks-v2-offline-2026-11-13
git log -1 --format="%h %s"
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_sonnet_c_contentblocks_v2_offline.py" -v
```

Se `21/21 OK`, suite completa `python -m unittest discover -s src/tests -p "test_*.py" -v`, **904 test attesi** (883 + 21), da confermare.

Solo dopo: preflight Colab read-only su HEAD nuova, con Drive parent D immutato, vecchia C invalid immutable, source C nuovo, pacchetto C old hash; **poi** decisione esplicita se autorizzare una nuova release e **un solo esperimento tecnico** C ContentBlocks V2. La nuova esecuzione non e' automaticamente autorizzata da questa nota.

**K resta blocked_dependency per la C V1 invalida; OOD test mai sbloccati.**
