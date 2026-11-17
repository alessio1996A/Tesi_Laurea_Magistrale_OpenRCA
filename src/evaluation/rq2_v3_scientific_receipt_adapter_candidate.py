"""Adattatore PROPOSTO, puro, delle ricevute scientifiche V3 D/C/K (SOLO OFFLINE).

NESSUN SDK, API, I/O su file, ground truth, claim, release o dispatcher di produzione.
Le righe del piano si risolvono SEMPRE dal piano V3 GT-free, distinto da quello V2. La logica
del contratto scientifico rigoroso e' riusata dai validatori V2 congelati, MA NON la loro
ricerca degli ID di stage V2 ne' il loro namespace create-only. Il ledger V3 finale dovra'
validare in modo indipendente sorgenti, release, commit, byte canonici, dipendenze, regola
"claim prima" (il claim si scrive prima del record), ripartenza e buste di provenienza.

Contenuto
---------
- `STATUSES`, `D_FIELDS`, `D_ERROR_CODE`: stati registrabili, campi dei metadati di D e forma
  del codice d'errore redatto di D;
- `V3ScientificReceiptBlocked`: errore "ricevuta ambigua, corrotta o con ID di stage V2";
- `_row`: riga del piano V3 per uno stage;
- `_validate_d_meta`, `_validate_d_identity`, `_validate_v3_base`: controlli parziali;
- `validate_v3_scientific_artifact`: validatore puro dell'artefatto, pronto per la rilettura;
- `_receipt`: busta comune della ricevuta;
- `normalize_v3_d_capture`, `normalize_v3_ck_call`: i due punti d'ingresso, per D e per C/K.
"""
from __future__ import annotations

import hashlib
import re

from evaluation.rq2_v2_ck_text_extraction_candidate import (
    POLICY, MAX_BLOCKS,
)
from evaluation.rq2_v2_unified_provider_result_adapter import (
    ERROR_CODE, UnifiedProviderReceiptBlocked,
    _from_metrics, _from_usage, _classify_with_ledger,
)
from evaluation.rq2_v2_unified_provenance_gate import audit_captured_v2_d
from evaluation.rq2_v2_unified_scientific_ledger import (
    UnifiedScientificLedgerBlocked, _validate_artifact,
)
from evaluation.rq2_v3_ck_provenance_receipt_candidate import (
    CKProvenanceReceiptBlocked,
    META_SCHEMA, _strict_metadata,
)
from evaluation.rq2_v3_d_final_stream_candidate import D_META_SCHEMA
from evaluation.rq2_v3_d_runner_capture_candidate import VERSION as D_CAPTURE
from evaluation.rq2_v3_unified_gtfree_discovery_plan import (
    VERSION as V3_PROTOCOL, build_offline_v3_discovery_plan,
)

VERSION = "rq2_v3_scientific_receipt_adapter_candidate_v0"
# Campi (esatti) dei metadati di estrazione del testo finale di D.
D_FIELDS = frozenset(("schema", "policy", "content_kind",
                      "text_blocks", "nontext_blocks"))
# Stati con cui una ricevuta puo' essere registrata.
STATUSES = frozenset(("RECORDED_COMPLETE", "INVALID_OUTPUT", "PROVIDER_ERROR"))
# Errore di D redatto: prefisso fisso piu' 16 caratteri esadecimali dell'hash del testo
# originale (il testo dell'errore non si salva mai).
D_ERROR_CODE = re.compile(r"RUNNER_EXECUTION_ERROR_SHA256_[0-9a-f]{16}\Z")


class V3ScientificReceiptBlocked(ValueError):
    """Una ricevuta e' ambigua, corrotta o usa un ID di stage V2 congelato."""


def _row(stage_id: str, logical_model: str, stage: str) -> dict:
    """Riga del piano V3 per `stage_id`, dopo aver verificato modello logico e stage.

    L'ID deve cominciare col nome del protocollo V3 (cosi' un ID V2 viene rifiutato) e lo
    stage deve essere D, C o K. Solleva `V3ScientificReceiptBlocked` se la riga non esiste o
    se modello e stage non coincidono.
    """
    if (
        type(stage_id) is not str or
        not stage_id.startswith(V3_PROTOCOL + ":") or
        type(logical_model) is not str or
        stage not in ("D", "C", "K")
    ):
        raise V3ScientificReceiptBlocked("V3 stage/model identity required")
    plan = build_offline_v3_discovery_plan()
    row = next((r for r in plan["entries"] if r["stage_id"] == stage_id), None)
    if row is None or row["logical_model"] != logical_model or row["stage"] != stage:
        raise V3ScientificReceiptBlocked("Wrong V3 arm, model or stage")
    return row


def _validate_d_meta(meta: object, raw: object, error: object) -> None:
    """Controlla i metadati `meta` di estrazione del testo finale di D rispetto a `raw`.

    Regole: 1) campi, schema e politica esatti; 2) conteggi dei blocchi interi e limitati da
    `MAX_BLOCKS`; 3) il tipo di contenuto e' coerente con testo e conteggi ("not_observed" =
    niente di osservato, "str" = al piu' un blocco, "list" = almeno un blocco di testo se c'e'
    testo, "unsupported" = tutto vuoto); 4) il testo, se c'e', e' una stringa; 5) senza errore
    e con testo, il tipo di contenuto deve essere "str" o "list". `error` e' l'errore del
    runner D (o None).
    """
    if type(meta) is not dict or set(meta) != D_FIELDS:
        raise V3ScientificReceiptBlocked("Missing/unexpected D text provenance")
    if meta["schema"] != D_META_SCHEMA or meta["policy"] != POLICY:
        raise V3ScientificReceiptBlocked("Wrong D final-text policy/schema")
    n, other, kind = (
        meta["text_blocks"], meta["nontext_blocks"], meta["content_kind"]
    )
    if (
        type(n) is not int or type(other) is not int
        or n < 0 or other < 0 or n + other > MAX_BLOCKS
    ):
        raise V3ScientificReceiptBlocked("Invalid D block counts")
    if kind == "not_observed":
        if n or other or raw is not None:
            raise V3ScientificReceiptBlocked("Unobserved D metadata contradiction")
    elif kind == "str":
        if other or (raw is not None and n != int(bool(raw))):
            raise V3ScientificReceiptBlocked("D string provenance contradiction")
    elif kind == "list":
        if type(raw) is str and raw and not n:
            raise V3ScientificReceiptBlocked("D text without text blocks")
    elif kind == "unsupported":
        if raw not in (None, "") or n or other:
            raise V3ScientificReceiptBlocked("Unsupported D envelope contradiction")
    else:
        raise V3ScientificReceiptBlocked("Unexpected D content kind")

    if raw is not None and type(raw) is not str:
        raise V3ScientificReceiptBlocked("D final response must be text")
    if error is None and raw is not None and kind not in ("str", "list"):
        raise V3ScientificReceiptBlocked("D final response provenance missing")
    # Se il grafo fallisce DOPO aver osservato un messaggio finale, il runner puo' scartare il
    # testo grezzo, ma i conteggi dei blocchi osservati restano veritieri. Questi errori non
    # sono mai etichettati RECORDED_COMPLETE.


def _validate_v3_base(
    row: dict, status: str, base: dict, diagnostic_run: dict | None,
) -> None:
    """Valida l'artefatto di base (senza i metadati V3) con il validatore V2 del ledger.

    Per C e K il genitore D e' costruito dal `diagnostic_run` ricevuto. Un rifiuto del
    validatore V2 diventa `V3ScientificReceiptBlocked`.
    """
    parent = (
        {"status": "RECORDED_COMPLETE",
         "artifact": {"diagnostic_run": diagnostic_run}}
        if row["stage"] != "D" else None
    )
    try:
        _validate_artifact(row, status, base, parent)
    except UnifiedScientificLedgerBlocked as exc:
        raise V3ScientificReceiptBlocked(
            "Underlying diagnosis/evidence/status contract mismatch"
        ) from exc


def validate_v3_scientific_artifact(
    *, stage_id: str, logical_model: str, status: str,
    artifact: dict, diagnostic_run: dict | None = None,
) -> None:
    """Validatore puro dell'artefatto, pronto per la rilettura; non e' un gate di ledger/release.

    Argomenti (per nome): `stage_id`, `logical_model`, `status`, `artifact` e, per C/K,
    `diagnostic_run` (il D genitore, immutabile). Solleva `V3ScientificReceiptBlocked`.

    Per D: campi dell'artefatto esatti (piu' `d_final_text_extraction`); con errore, un codice
    redatto e nessuna esecuzione sorgente; altrimenti identita' e metadati del run D. Per C/K:
    D genitore con identita' e provenienza dei tool verificate, campi esatti (piu'
    `text_extraction`), codice d'errore sicuro, metadati coerenti e testo visibile se
    completo. In entrambi i casi l'artefatto di base supera anche il validatore V2.
    """
    stage = stage_id.rsplit(":", 1)[-1] if type(stage_id) is str else ""
    row = _row(stage_id, logical_model, stage)
    if status not in STATUSES or type(artifact) is not dict:
        raise V3ScientificReceiptBlocked("Invalid status/artifact type")

    if stage == "D":
        required = (
            {"provider_error", "stage_meter"} if status == "PROVIDER_ERROR"
            else {"diagnostic_run", "stage_meter"}
        )
        if set(artifact) != required | {"d_final_text_extraction"}:
            raise V3ScientificReceiptBlocked("D V3 artifact schema mismatch")
        if status == "PROVIDER_ERROR":
            if diagnostic_run is not None:
                raise V3ScientificReceiptBlocked("D error has untrusted source")
            d_error = artifact["provider_error"]
            if (
                type(d_error) is not str
                or not (D_ERROR_CODE.fullmatch(d_error)
                        or d_error == "SDK_CONSTRUCTION_ERROR")
            ):
                raise V3ScientificReceiptBlocked("Unredacted/untrusted D error")
            # Un errore del runner D deve aver scartato il testo grezzo; i metadati restano
            # legati ai sorgenti solo sotto un futuro ledger V3.
            _validate_d_meta(
                artifact["d_final_text_extraction"], raw=None,
                error=artifact["provider_error"],
            )
        else:
            d = artifact["diagnostic_run"]
            if type(d) is not dict:
                raise V3ScientificReceiptBlocked("D runner payload missing")
            _validate_d_identity(row, d)
            _validate_d_meta(
                artifact["d_final_text_extraction"],
                raw=d.get("raw_response"), error=d.get("error"),
            )
        # Artefatto di base D (senza i metadati V3): validazione V2.
        base = {k: artifact[k] for k in required}
        _validate_v3_base(row, status, base, None)
        return

    # Da qui in poi: C/K. Serve il D genitore, con identita' e provenienza dei tool attendibili.
    if type(diagnostic_run) is not dict:
        raise V3ScientificReceiptBlocked("Immutable parent D run required")
    _validate_d_identity(row, diagnostic_run)
    try:
        audit_captured_v2_d(
            run=diagnostic_run, case_id=row["case_id"],
            model=row["logical_model"], harness=row["harness"],
        )
    except (ValueError, TypeError, KeyError) as exc:
        raise V3ScientificReceiptBlocked("Untrusted D tool provenance") from exc
    required = (
        {"provider_error", "stage_meter"} if status == "PROVIDER_ERROR"
        else {"raw_response", "stage_meter"}
    )
    if set(artifact) != required | {"text_extraction"}:
        raise V3ScientificReceiptBlocked("C/K V3 artifact schema mismatch")
    if status == "PROVIDER_ERROR":
        error_code = artifact["provider_error"]
        if type(error_code) is not str or not ERROR_CODE.fullmatch(error_code):
            raise V3ScientificReceiptBlocked("Unredacted/untrusted C/K error")
    meta = artifact["text_extraction"]
    try:
        _strict_metadata(
            meta, raw=artifact.get("raw_response"),
            error=status == "PROVIDER_ERROR",
        )
    except CKProvenanceReceiptBlocked as exc:
        raise V3ScientificReceiptBlocked("Untrusted C/K text metadata") from exc
    if status == "RECORDED_COMPLETE" and meta["content_kind"] not in ("str", "list"):
        raise V3ScientificReceiptBlocked("Complete C/K lacks visible text")
    base = {k: artifact[k] for k in required}
    _validate_v3_base(row, status, base, diagnostic_run)


def _validate_d_identity(row: dict, run: dict) -> None:
    """Verifica che il run D `run` appartenga alla riga `row` del piano (caso, harness, modello).

    Richiede anche schema delle varianti "current", provider, contratto di output "v2_enforce"
    e 6 turni di tool; qualsiasi scostamento solleva `V3ScientificReceiptBlocked`.
    """
    required = {
        "case_id": row["case_id"],
        "variant": row["harness"],
        "variant_scheme": "current",
        "model": row["model_id"],
        "model_provider": row["model_provider"],
        "output_contract_mode": "v2_enforce",
        "max_tool_rounds": 6,
    }
    if type(run) is not dict or any(
        run.get(key) != value for key, value in required.items()
    ):
        raise V3ScientificReceiptBlocked("D case/model/harness/output drift")


def _receipt(stage_id: str, status: str, artifact: dict) -> dict:
    """Busta comune della ricevuta: nessuna API, nessuna scrittura, costo sconosciuto."""
    return {
        "version": VERSION,
        "stage_id": stage_id,
        "status": status,
        "artifact": artifact,
        "can_execute_api": False,
        "can_write_scientific_records": False,
        "usd_cost_known": False,
        "observed_requests_are_http_hard_cap": False,
    }


def normalize_v3_d_capture(
    *, stage_id: str, logical_model: str, captured: dict,
) -> dict:
    """Ricevuta D dall'output del runner a testo finale esatto, GIA' ottenuto.

    Argomenti (per nome): `stage_id`, `logical_model` e `captured` (la ricevuta della cattura
    `rq2_v3_d_runner_capture_candidate`). Restituisce la ricevuta normalizzata.

    Passi: 1) riga V3 del piano; 2) busta di cattura attendibile (versione e dichiarazioni
    "nessuna API/scrittura"); 3) identita' del run D e rappresentazione dell'errore;
    4) metadati e contatore dalle metriche; 5) con errore: codice redatto con hash;
    senza errore: stato COMPLETO o OUTPUT NON VALIDO a seconda del validatore V2; 6) l'artefatto
    finale supera il validatore V3.
    """
    row = _row(stage_id, logical_model, "D")
    if (
        type(captured) is not dict
        or captured.get("version") != D_CAPTURE
        or captured.get("can_execute_api") is not False
        or captured.get("can_write_scientific_records") is not False
        or captured.get("scientific_release_frozen") is not False
    ):
        raise V3ScientificReceiptBlocked("Untrusted D capture envelope")
    run = captured.get("diagnostic_run")
    meta = captured.get("d_final_text_extraction")
    _validate_d_identity(row, run)
    error = run.get("error")
    if error is not None and (
        type(error) is not str or not error.strip()
    ):
        raise V3ScientificReceiptBlocked("Invalid D error representation")
    _validate_d_meta(meta, raw=run.get("raw_response"), error=error)
    try:
        meter = _from_metrics(
            run.get("metrics"), can_be_zero=(error is not None)
        )
    except UnifiedProviderReceiptBlocked as exc:
        raise V3ScientificReceiptBlocked("Bad D usage") from exc

    # Con errore si registra solo un'impronta (hash) del testo, mai il testo stesso.
    if error is not None:
        fingerprint = hashlib.sha256(error.encode("utf-8")).hexdigest()[:16]
        status = "PROVIDER_ERROR"
        artifact = {
            "provider_error": "RUNNER_EXECUTION_ERROR_SHA256_" + fingerprint,
            "stage_meter": meter,
            "d_final_text_extraction": dict(meta),
        }
    else:
        # Si prova prima come COMPLETO, poi come OUTPUT NON VALIDO; se nessuno dei due e'
        # coerente, la ricevuta e' ambigua e si blocca.
        base = {"diagnostic_run": run, "stage_meter": meter}
        try:
            _validate_artifact(row, "RECORDED_COMPLETE", base, None)
        except UnifiedScientificLedgerBlocked:
            try:
                _validate_artifact(row, "INVALID_OUTPUT", base, None)
            except UnifiedScientificLedgerBlocked as exc:
                raise V3ScientificReceiptBlocked(
                    "Inconsistent D task/evidence status"
                ) from exc
            status = "INVALID_OUTPUT"
        else:
            status = "RECORDED_COMPLETE"
        artifact = {**base, "d_final_text_extraction": dict(meta)}
    validate_v3_scientific_artifact(
        stage_id=stage_id, logical_model=logical_model,
        status=status, artifact=artifact,
    )
    return _receipt(stage_id, status, artifact)


def normalize_v3_ck_call(
    *, stage_id: str, logical_model: str,
    call: dict, diagnostic_run: dict,
) -> dict:
    """Ricevuta C/K con identita' V3, evidenze originali e parser rigoroso.

    Argomenti (per nome): `stage_id`, `logical_model`, `call` (dizionario del trasporto C/K
    gia' ottenuto) e `diagnostic_run` (il D genitore). Restituisce la ricevuta normalizzata.

    Passi: 1) lo stage deve essere C o K del piano V3; 2) il D ha identita' e provenienza dei
    tool attendibili e il contatore e' coerente; 3) metadati di estrazione del testo dal
    trasporto, verificati; 4) con errore: codice sicuro e nessun testo; senza errore: una sola
    chiamata e un testo, poi classificazione dell'esito con il validatore V2; 5) l'artefatto
    finale supera il validatore V3.
    """
    if type(stage_id) is not str:
        raise V3ScientificReceiptBlocked("V3 stage ID required")
    stage = stage_id.rsplit(":", 1)[-1]
    if stage not in ("C", "K"):
        raise V3ScientificReceiptBlocked("C/K stage required")
    row = _row(stage_id, logical_model, stage)
    if type(call) is not dict or type(diagnostic_run) is not dict:
        raise V3ScientificReceiptBlocked("Missing C/K transport or D source")
    _validate_d_identity(row, diagnostic_run)
    try:
        audit_captured_v2_d(
            run=diagnostic_run, case_id=row["case_id"],
            model=row["logical_model"], harness=row["harness"],
        )
        meter = _from_usage(
            call.get("usage"), attempts=call.get("api_attempts")
        )
    except (ValueError, TypeError, KeyError, UnifiedProviderReceiptBlocked) as exc:
        raise V3ScientificReceiptBlocked("CK evidence/usage contract mismatch") from exc
    # Metadati di estrazione del testo, presi dal trasporto e verificati.
    error, raw = call.get("provider_error"), call.get("raw_response")
    meta = {
        "schema": META_SCHEMA,
        "policy": call.get("content_extraction_policy"),
        "content_kind": call.get("response_content_kind"),
        "text_blocks": call.get("text_blocks_observed"),
        "nontext_blocks": call.get("nontext_blocks_observed"),
    }
    try:
        _strict_metadata(meta, raw=raw, error=error is not None)
    except CKProvenanceReceiptBlocked as exc:
        raise V3ScientificReceiptBlocked("C/K extraction metadata mismatch") from exc
    if error is not None:
        if (
            type(error) is not str or not ERROR_CODE.fullmatch(error)
            or raw is not None
        ):
            raise V3ScientificReceiptBlocked("Untrusted provider error")
        status = "PROVIDER_ERROR"
        base = {"provider_error": error, "stage_meter": meter}
    else:
        if call.get("api_attempts") != 1 or type(raw) is not str:
            raise V3ScientificReceiptBlocked("Unambiguous C/K call required")
        base = {"raw_response": raw, "stage_meter": meter}
        try:
            status = _classify_with_ledger(
                row=row, artifact=base,
                d_record={"status": "RECORDED_COMPLETE",
                          "artifact": {"diagnostic_run": diagnostic_run}},
            )
        except UnifiedProviderReceiptBlocked as exc:
            raise V3ScientificReceiptBlocked("C/K status ambiguous") from exc
    artifact = {**base, "text_extraction": meta}
    validate_v3_scientific_artifact(
        stage_id=stage_id, logical_model=logical_model,
        status=status, artifact=artifact,
        diagnostic_run=diagnostic_run,
    )
    return _receipt(stage_id, status, artifact)
