"""Contratto di ricevuta C/K PROPOSTO (solo successore) con provenienza verificabile del testo.

SOLO CONTRATTO OFFLINE. Questo modulo non scrive record, non istanzia un LLM, non legge la
ground truth e non autorizza nessuna esecuzione live. Il sorgente V2, la release e il ledger
create-only esistenti non vanno mai modificati ne' riutilizzati come V3.

Il vecchio adattatore V2 fornisce classificazione scientifica e contatore con controlli
rigorosi. Questa ricevuta successore aggiunge SOLO una busta di metadati limitata, che un
futuro *ledger V3 separato e legato ai sorgenti* dovra' validare e salvare.

Contenuto
---------
- `META_SCHEMA`, `META_KEYS`, `RECORDABLE`: schema e campi dei metadati, stati registrabili;
- `CKProvenanceReceiptBlocked`: errore "provenienza mancante o contraddittoria";
- `_strict_metadata`: controlla che i metadati di estrazione del testo siano coerenti;
- `candidate_ck_record_receipt`: normalizza C/K con il validatore V2 e AGGIUNGE i metadati;
- `validate_candidate_ck_artifact`: rivalida l'artefatto arricchito (anche dopo la rilettura
  da disco).
"""
from __future__ import annotations

from evaluation.rq2_v2_ck_text_extraction_candidate import MAX_BLOCKS, POLICY
from evaluation.rq2_v2_unified_provider_result_adapter import (
    normalize_ck_call,
    _row,
)
from evaluation.rq2_v2_unified_scientific_ledger import (
    UnifiedScientificLedgerBlocked,
    _validate_artifact,
)

VERSION = "rq2_v3_ck_provenance_receipt_candidate_v0"
# Nome dello schema dei metadati di estrazione del testo e campi che devono avere (esatti).
META_SCHEMA = "rq2_v3_ck_text_extraction_meta_v0"
META_KEYS = frozenset((
    "schema", "policy", "content_kind", "text_blocks", "nontext_blocks",
))
# Stati con cui una ricevuta C/K puo' essere registrata (niente stato "bloccato" qui).
RECORDABLE = frozenset(("RECORDED_COMPLETE", "INVALID_OUTPUT", "PROVIDER_ERROR"))


class CKProvenanceReceiptBlocked(ValueError):
    """Blocco (fail closed) se la provenienza del trasporto manca o e' contraddittoria."""


def _strict_metadata(meta: object, *, raw: object, error: bool) -> None:
    """Controlla i metadati `meta` di estrazione del testo rispetto al testo grezzo `raw`.

    `error` e' True per una ricevuta di errore del provider. Regole: 1) campi, schema e
    politica esatti; 2) i conteggi dei blocchi sono interi limitati da `MAX_BLOCKS`; 3) con
    errore, niente contenuto osservato e niente testo; 4) senza errore, il testo e' una
    stringa e il tipo di contenuto e' coerente con i conteggi ("str" = un solo blocco se non
    vuoto, "list" = almeno un blocco di testo se c'e' testo, "unsupported" = tutto vuoto).
    Solleva `CKProvenanceReceiptBlocked` al primo scostamento.
    """
    if type(meta) is not dict or set(meta) != META_KEYS:
        raise CKProvenanceReceiptBlocked("Missing or unexpected extraction metadata")
    if meta["schema"] != META_SCHEMA or meta["policy"] != POLICY:
        raise CKProvenanceReceiptBlocked("Wrong candidate extraction policy/schema")

    kind = meta["content_kind"]
    texts, others = meta["text_blocks"], meta["nontext_blocks"]
    if type(texts) is not int or type(others) is not int:
        raise CKProvenanceReceiptBlocked("Block counts must be integers")
    if not (0 <= texts <= MAX_BLOCKS and 0 <= others <= MAX_BLOCKS
            and texts + others <= MAX_BLOCKS):
        raise CKProvenanceReceiptBlocked("Unbounded content block counts")

    if error:
        if kind != "not_observed" or texts != 0 or others != 0:
            raise CKProvenanceReceiptBlocked("Error receipt has unexpected content")
        if raw is not None:
            raise CKProvenanceReceiptBlocked("Error receipt must not carry raw text")
        return

    if type(raw) is not str:
        raise CKProvenanceReceiptBlocked("Successful invoke lacks text string")
    if kind == "str":
        if texts != int(bool(raw)) or others != 0:
            raise CKProvenanceReceiptBlocked("String block counts inconsistent")
    elif kind == "list":
        if raw and texts == 0:
            raise CKProvenanceReceiptBlocked("Visible text without observed text blocks")
    elif kind == "unsupported":
        if raw != "" or texts or others:
            raise CKProvenanceReceiptBlocked("Unsupported content must be empty")
    else:
        raise CKProvenanceReceiptBlocked("Unknown successful content kind")


def candidate_ck_record_receipt(
    *, stage_id: str, logical_model: str, call: dict,
    diagnostic_run: dict,
) -> dict:
    """Normalizza C/K con il vecchio validatore rigoroso, poi AGGIUNGE la provenienza.

    Il risultato e' volutamente incompatibile con l'elenco di campi dell'artefatto V2: puo'
    essere salvato solo con uno schema successore definito a parte.

    Argomenti (per nome): `stage_id`, `logical_model`, `call` (dizionario del trasporto C/K)
    e `diagnostic_run` (il D di partenza). Restituisce la ricevuta V2 con versione cambiata e
    l'artefatto arricchito del campo `text_extraction`.

    Passi: 1) ricevuta di base dal normalizzatore V2; 2) metadati dai campi del trasporto e
    loro verifica; 3) artefatto = quello di base + metadati, rivalidato per intero.
    """
    if type(call) is not dict:
        raise CKProvenanceReceiptBlocked("Transport receipt must be a dict")

    # 1. Ricevuta di base: stessa classificazione e stesso contatore della V2.
    baseline = normalize_ck_call(
        stage_id=stage_id,
        logical_model=logical_model,
        call=call,
        diagnostic_run=diagnostic_run,
    )
    # 2. Metadati di estrazione del testo, presi dal trasporto e controllati subito.
    meta = {
        "schema": META_SCHEMA,
        "policy": call.get("content_extraction_policy"),
        "content_kind": call.get("response_content_kind"),
        "text_blocks": call.get("text_blocks_observed"),
        "nontext_blocks": call.get("nontext_blocks_observed"),
    }
    _strict_metadata(
        meta,
        raw=call.get("raw_response"),
        error=call.get("provider_error") is not None,
    )

    # 3. Artefatto arricchito, rivalidato come se fosse riletto da disco.
    artifact = {**baseline["artifact"], "text_extraction": meta}
    validate_candidate_ck_artifact(
        stage_id=stage_id, logical_model=logical_model,
        status=baseline["status"], artifact=artifact,
        diagnostic_run=diagnostic_run,
    )
    return {
        **baseline,
        "version": VERSION,
        "receipt_schema": VERSION,
        "artifact": artifact,
    }


def validate_candidate_ck_artifact(
    *, stage_id: str, logical_model: str,
    status: str, artifact: dict, diagnostic_run: dict,
) -> None:
    """Rivalida un artefatto arricchito, anche dopo la rilettura da disco.

    Un futuro ledger dovra' controllare ANCHE claim, release, dipendenze fra stage, hash dei
    sorgenti, byte canonici e commit fissato: questo validatore autonomo non li sostituisce
    ne' li implementa.

    Argomenti (per nome): `stage_id`, `logical_model`, `status`, `artifact` e
    `diagnostic_run`. Passi: 1) stato registrabile e tipi corretti; 2) i campi dell'artefatto
    sono quelli di base piu' `text_extraction`; 3) metadati coerenti, e un C/K completo deve
    avere testo visibile; 4) l'artefatto SENZA i metadati supera il validatore V2 del ledger.
    """
    if status not in RECORDABLE or type(artifact) is not dict:
        raise CKProvenanceReceiptBlocked("Unsupported candidate receipt/status")
    if type(diagnostic_run) is not dict:
        raise CKProvenanceReceiptBlocked("Missing diagnostic run")

    # Campi dell'artefatto di base (V2): con errore contatore + codice, altrimenti contatore +
    # risposta grezza.
    required_base = (
        {"stage_meter", "provider_error"} if status == "PROVIDER_ERROR"
        else {"stage_meter", "raw_response"}
    )
    if set(artifact) != required_base | {"text_extraction"}:
        raise CKProvenanceReceiptBlocked("Candidate artifact fields mismatch")

    meta = artifact["text_extraction"]
    _strict_metadata(
        meta,
        raw=artifact.get("raw_response"),
        error=status == "PROVIDER_ERROR",
    )
    if status == "RECORDED_COMPLETE" and (
        meta["content_kind"] not in ("str", "list")
    ):
        raise CKProvenanceReceiptBlocked("Complete C/K must have visible text")

    # Validazione V2 dell'artefatto di base (senza i metadati aggiunti dal successore).
    row = _row(
        stage_id=stage_id,
        logical_model=logical_model,
        stage=stage_id.rsplit(":", 1)[-1],
    )
    original = {name: artifact[name] for name in required_base}
    d_record = {
        "status": "RECORDED_COMPLETE",
        "artifact": {"diagnostic_run": diagnostic_run},
    }
    try:
        _validate_artifact(row, status, original, d_record)
    except UnifiedScientificLedgerBlocked as exc:
        raise CKProvenanceReceiptBlocked(
            "Underlying C/K evidence/status contract mismatch"
        ) from exc
