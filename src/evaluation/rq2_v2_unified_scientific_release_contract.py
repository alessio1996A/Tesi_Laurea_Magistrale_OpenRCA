"""G4E RQ2 V2: contratto della FUTURA release scientifica, solo dati.

Non crea release, claim, record, client o richieste API; non legge file.
Una release candidata NON e' un permesso di esecuzione. Il pin SHA
deve essere ricevuto dall'esterno, insieme a esplicita approvazione
economica. La futura produzione dovra' verificare ulteriori gate
(runtime, GT-free, lock concorrente, richiesta HTTP effettiva).

Tutti gli hash in questo modulo sono identificatori di integrita', non
firme crittografiche di una persona e non autorizzano pagamenti.

Contenuto
---------
- `REQUIRED_KEYS`: l'insieme esatto dei campi che una release deve avere (ne' di piu' ne' di meno);
- `UnifiedReleaseContractError`: errore "requisito della release non verificabile";
- `canonical_release`, `release_digest`: forma canonica JSON della release e suo SHA-256;
- `_money`: valida il massimale in dollari (testo decimale, al massimo al centesimo);
- `validate_future_release`: la verifica completa, che confronta la release con piano,
  preview delle sorgenti e blueprint e restituisce un esito SENZA alcun permesso di esecuzione.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import hashlib
import json
import re

from evaluation.rq2_v2_unified_discovery_plan import (
    DISCOVERY, HARNESSES, MODELS, TEST, VERSION as PROTOCOL,
    build_offline_discovery_plan,
)
from evaluation.rq2_v2_unified_release_blueprint import (
    VERSION as BLUEPRINT_VERSION,
)
from evaluation.rq2_v2_unified_release_preflight import (
    VERSION as SOURCE_VERSION,
)

VERSION = "rq2_v2_unified_scientific_release_contract_v0"
# Nome dello schema della release e cartella dei dati scientifici a cui si riferisce.
RELEASE_SCHEMA = "rq2_v2_unified_scientific_discovery_release_v1"
RELEASE_NAMESPACE = "data/rq2_v2_unified_scientific_v1"
# Forme ammesse: hash di commit git (SHA-1, 40 caratteri) e hash SHA-256 (64 caratteri).
_SHA1 = re.compile(r"[0-9a-f]{40}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
# Campi obbligatori della release: identita' del codice e dei dati, modelli e harness, limiti,
# politiche di trasporto e di scrittura, approvazione economica. Un campo in piu' o in meno
# invalida la release.
REQUIRED_KEYS = frozenset({
    "schema", "protocol", "phase", "source_commit", "blueprint_sha256",
    "source_plan_sha256", "split_sha256", "manifest_sha256",
    "source_files_sha256", "C_system_prompt_sha256",
    "K_system_prompt_sha256", "logical_models", "model_ids", "harnesses",
    "discovery_cases", "stage_counts", "logical_stage_count",
    "d_output_contract", "max_tool_rounds", "planning_checks",
    "proposed_scientific_namespace", "runtime_versions",
    "transport_retries_proven_no_implicit_http_retry",
    "per_request_timeout_verified", "usage_meter_fail_closed",
    "single_writer_policy_proven", "max_graph_invocations_candidate",
    "max_http_attempts_guaranteed", "api_budget_approved",
    "approved_total_usd_limit", "approval_reference", "ood_test_locked",
    "authorization", "scientific_protocol_frozen",
})


class UnifiedReleaseContractError(ValueError):
    """Uno o piu' requisiti della futura release non sono verificabili."""


def canonical_release(value: object) -> bytes:
    """Forma canonica della release in byte UTF-8: JSON con chiavi ordinate e senza spazi.

    Solleva `UnifiedReleaseContractError` se il valore non e' serializzabile (NaN, tipi non
    JSON, annidamento eccessivo) o se supera i 100.000 byte.
    """
    try:
        result = json.dumps(
            value, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")
    except (ValueError, TypeError, OverflowError, RecursionError) as exc:
        raise UnifiedReleaseContractError("Noncanonical release") from exc
    if len(result) > 100_000:
        raise UnifiedReleaseContractError("Release too large")
    return result


def release_digest(value: object) -> str:
    """SHA-256 (esadecimale) della forma canonica di `value`."""
    return hashlib.sha256(canonical_release(value)).hexdigest()


def _money(value: object) -> Decimal:
    """Converte il massimale in dollari (testo decimale) in `Decimal`, dopo averlo validato.

    Regole: una stringa non vuota di al massimo 32 caratteri, numero finito, maggiore di zero e
    non oltre 10.000, con al massimo due decimali (centesimi).
    """
    # USD e' un massimale operativo autorizzato, NON un hard-cap del
    # provider. L'uso di Decimal elimina ambiguita' binarie dei float.
    if type(value) is not str or not value or len(value) > 32:
        raise UnifiedReleaseContractError("Approved budget must be decimal text")
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise UnifiedReleaseContractError("Invalid USD budget") from exc
    if not amount.is_finite() or amount <= 0 or amount > Decimal("10000"):
        raise UnifiedReleaseContractError("Approved USD limit out of bounds")
    if amount.as_tuple().exponent < -2:
        raise UnifiedReleaseContractError("USD limit precision exceeds cents")
    return amount


def validate_future_release(
    *, release: dict, source_preview: dict, blueprint: dict,
    externally_approved_sha256: str | None, expected_source_commit: str,
) -> dict:
    """Verifica STRICT una release gia' approvata senza creare permessi API.

    Il chiamante successivo dovra' provare che source_preview proviene
    da verifica GT-free REALE, non da mock. Nemmeno l'esito OK di
    questa funzione autorizza una singola chiamata provider.

    Argomenti (tutti per nome): `release` (dizionario della release), `source_preview` (preview
    delle sorgenti), `blueprint` (blueprint G4B), `externally_approved_sha256` (SHA-256 della
    release ricevuto dall'esterno) e `expected_source_commit` (commit git atteso).
    Restituisce un riepilogo con stato "contenuto validato, nessuna autorita' di esecuzione".

    Passi: 1) pin esterni ben formati; 2) campi della release esatti; 3) l'hash della release
    coincide col pin; 4) ogni campo dichiarativo coincide con quello atteso (valore e tipo);
    5) preview e blueprint sono quelli attesi e coerenti con la release; 6) versioni di runtime
    fissate; 7) riferimento d'approvazione presente; 8) massimale in dollari valido.
    """
    # 1. Pin ricevuti dall'esterno: SHA-256 della release e commit git, entrambi ben formati.
    if (
        type(externally_approved_sha256) is not str
        or not _SHA256.fullmatch(externally_approved_sha256)
        or type(expected_source_commit) is not str
        or not _SHA1.fullmatch(expected_source_commit)
    ):
        raise UnifiedReleaseContractError("External digest/commit pin required")
    # 2. La release ha esattamente i campi richiesti; preview e blueprint sono dizionari.
    if type(release) is not dict or set(release) != REQUIRED_KEYS:
        raise UnifiedReleaseContractError("Unknown/missing release fields")
    if type(source_preview) is not dict or type(blueprint) is not dict:
        raise UnifiedReleaseContractError("Verified source and blueprint required")
    # 3. La release non e' stata modificata dopo l'approvazione esterna.
    if release_digest(release) != externally_approved_sha256:
        raise UnifiedReleaseContractError("Pinned release SHA mismatch")

    # 4. Valori attesi per i campi dichiarativi, ricavati dal piano e dai pin: il confronto
    # sotto richiede stesso tipo e stesso valore (un `True` non puo' sostituire un `1`).
    plan = build_offline_discovery_plan()
    matches = {
        "schema": RELEASE_SCHEMA,
        "protocol": PROTOCOL,
        "phase": "discovery",
        "source_commit": expected_source_commit,
        "blueprint_sha256": blueprint.get("blueprint_sha256"),
        "source_plan_sha256": plan["preview_sha256"],
        "split_sha256": plan["split_sha256_expected"],
        "manifest_sha256": plan["manifest_sha256_expected"],
        "source_files_sha256": source_preview.get("source_files_sha256"),
        "C_system_prompt_sha256": source_preview.get("C_system_prompt_sha256"),
        "K_system_prompt_sha256": source_preview.get("K_system_prompt_sha256"),
        "logical_models": list(MODELS),
        "model_ids": plan["model_ids"],
        "harnesses": list(HARNESSES),
        "discovery_cases": list(DISCOVERY),
        "stage_counts": {"D": 60, "C": 60, "K": 60},
        "logical_stage_count": 180,
        "d_output_contract": "v2_enforce",
        "max_tool_rounds": 6,
        "planning_checks": 2,
        "proposed_scientific_namespace": RELEASE_NAMESPACE,
        "transport_retries_proven_no_implicit_http_retry": True,
        "per_request_timeout_verified": True,
        "usage_meter_fail_closed": True,
        "single_writer_policy_proven": True,
        "max_graph_invocations_candidate": 492,
        "max_http_attempts_guaranteed": None,
        "api_budget_approved": True,
        "ood_test_locked": True,
        "authorization": "approved_option_a_discovery_only",
        "scientific_protocol_frozen": True,
    }
    for name, value in matches.items():
        if type(release.get(name)) is not type(value) or release[name] != value:
            raise UnifiedReleaseContractError("Release field mismatch: " + name)

    # 5. Preview e blueprint devono essere quelli attesi (versione, stato, hash del piano, 180
    # stage, nessuna API eseguibile) e coerenti fra loro e con la release.
    if (
        source_preview.get("version") != SOURCE_VERSION
        or source_preview.get("status") != "OFFLINE_SOURCE_BOUND_NO_RELEASE_NO_API"
        or source_preview.get("plan_preview_sha256") != plan["preview_sha256"]
        or source_preview.get("gt_free_source_verified") is not True
        or source_preview.get("frozen_rq1_source_identity_verified") is not True
        or source_preview.get("can_execute_api") is not False
        or source_preview.get("can_run_ood_test") is not False
        or blueprint.get("version") != BLUEPRINT_VERSION
        or blueprint.get("status") != "DRAFT_ALL_EXECUTION_BLOCKED_NO_API"
        or blueprint.get("source_plan_sha256") != plan["preview_sha256"]
        or blueprint.get("source_files_sha256") != source_preview.get("source_files_sha256")
        or blueprint.get("blueprint_sha256") != release["blueprint_sha256"]
        or blueprint.get("logical_stage_count") != 180
        or blueprint.get("can_execute_api") is not False
        or blueprint.get("can_run_ood_test") is not False
    ):
        raise UnifiedReleaseContractError("Untrusted source preview or blueprint")
    # 6. Versioni di runtime: dizionario non vuoto di stringhe brevi (nome -> versione).
    runtime = release["runtime_versions"]
    if (
        type(runtime) is not dict or not runtime
        or any(type(k) is not str or not k or type(v) is not str
               or not v or len(v) > 60 for k, v in runtime.items())
    ):
        raise UnifiedReleaseContractError("Unpinned runtime versions")
    # 7. Riferimento all'approvazione esterna: testo non vuoto, al massimo 200 caratteri.
    approval_ref = release["approval_reference"]
    if (
        type(approval_ref) is not str or not approval_ref.strip()
        or len(approval_ref) > 200
    ):
        raise UnifiedReleaseContractError("Explicit external approval reference required")
    # 8. Massimale in dollari valido (solo controllo: il valore non viene usato qui).
    _money(release["approved_total_usd_limit"])
    # Esito: tutti i campi "puo' fare / e' implementato" restano False o zero.
    return {
        "version": VERSION,
        "status": "RELEASE_CONTENT_VALIDATED_NO_EXECUTION_AUTHORITY",
        "release_sha256": externally_approved_sha256,
        "source_commit": expected_source_commit,
        "plan_sha256": plan["preview_sha256"],
        "logical_stages": 180,
        "ood_test_locked": True,
        "max_http_attempts_guaranteed": None,
        "usd_hard_cap_guaranteed": False,
        "approval_reference_present": True,
        "source_verification_repeated_here": False,
        "release_file_written": False,
        "scientific_claims_written": 0,
        "model_calls_sent": 0,
        "can_create_scientific_claim": False,
        "can_execute_api": False,
        "can_run_ood_test": False,
        "production_ledger_implemented": False,
        "production_dispatcher_implemented": False,
    }
