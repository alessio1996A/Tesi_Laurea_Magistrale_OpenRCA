"""Impronte RQ2 offline prima del congelamento, con parita' rispetto ai sorgenti RQ1 congelati.

Legge SOLO file sotto l'albero `src/` di questo repository: nessun benchmark, ground truth,
telemetria dei tool, LLM, credenziali, rete, SDK di modelli o output di esperimenti.

I riferimenti SHA-1 dei blob Git di RQ1 sono stati controllati rispetto al sorgente al commit
congelato e4845e7fe9a399e10dd2db6f320dfeaeeddf3379. I digest dei blob Git qui sono controlli di
provenienza, non una protezione contro manomissioni malevole del repository.

Questo rapporto registra la modalita' di output dei task di D di RQ1, 'v2_enforce', osservata
nel codice ufficiale di preregistrazione e di imposizione della campagna, rimasto invariato.
NON congela nessun NUOVO protocollo RQ2 e non autorizza l'uso delle API.

Contenuto
---------
- `RQ1_BLOB_SHA1`: i 13 file sorgente RQ1 congelati con il loro hash git (valori che NON vanno
  mai cambiati: sono il motivo per cui quei file non si possono modificare);
- `RQ2_FINGERPRINT_PATHS`: i file RQ2 di cui si registra l'impronta SHA-256 corrente;
- `ProtocolIdentityError`: errore "sorgente, prompt o configurazione cambiati";
- `git_blob_sha1`, `_sha256`, `_read_source`, `_check_frozen_blob`: hash e lettura dei sorgenti;
- `preview_protocol_identity`: la verifica completa e il rapporto di anteprima;
- `main`: stampa il rapporto in JSON.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from agent.model_factory import (
    ANTHROPIC_MAX_OUTPUT_TOKENS_PER_REQUEST,
    ANTHROPIC_MODELS,
)
from evaluation.experiment_config import ExperimentConfig
from evaluation.rq2_budget_preflight import CANDIDATE_MODELS
from evaluation.rq2_dryrun_plan import (
    EXPECTED_MANIFEST_SHA256, EXPECTED_SPLIT_SHA256, HARNESSES,
    MAX_TOOL_ROUNDS, MODELS,
)
from evaluation.rq2_probe_adapter import (
    CAUSE_SYSTEM, RULE_SYSTEM, VERSION as PROBE_ADAPTER_VERSION,
)

VERSION = "rq2_protocol_identity_preflight_v0"
# Commit di RQ1 a cui si riferiscono gli hash sotto, e modalita' di output di D usata in RQ1.
RQ1_FROZEN_REFERENCE_COMMIT = "e4845e7fe9a399e10dd2db6f320dfeaeeddf3379"
RQ1_D_OUTPUT_MODE = "v2_enforce"
# Hash git dei blob (SHA-1) dei file RQ1 congelati. Un file diverso da questi hash blocca il
# preflight: per questo quei file non si modificano nemmeno con un commento.
RQ1_BLOB_SHA1 = {
    "evaluation/evaluation20_preregister.py": "80bd3b0cac7150c76c2ba102329708e3ddb544ef",
    "evaluation/evaluation20_campaign.py": "e65603acc7fc26a62e7f5534af2fcf5d359eda9d",
    "evaluation/experiment_runner.py": "32f4a870a52b65edc66c52e5a5932cf87b42de56",
    "evaluation/experiment_config.py": "a488d180ae7891f4370c2d7dbc932161e1b187ae",
    "agent/model_factory.py": "05308d5740763db0444556dcb7330d8fb4c308ec",
    "agent/prompts.py": "f68eee79a2382828a11b446c19972e73794db9a3",
    "agent/graph_engine.py": "415bad3feaf77cd70da72308ec2219c05ca1b956",
    "agent/tool_factory.py": "70b6612d4438d7ebcf3b363bf712817854ae3e28",
    "agent/tools.py": "6e4617770d49476ebd4112d486d6cd1f4d079d34",
    "output/v2_task_contract.py": "9be3002a9e7d6d0d733662d953d462b4ee828c0d",
    "harness/evidence_builder.py": "fc9d05a9f6562823170cc6ed7ed29a2452c0eb1e",
    "harness/signal_catalog.py": "c1fec771c9d8876bc2e33eb49e7ddef067bb3963",
    "harness/rules/rule_container_cpu.py": "b7e560a4bd08dd5677c81774650205ff3b7ec8d7",
}
# File RQ2 non ancora congelati scientificamente: se ne registra l'impronta SHA-256 corrente, cosi'
# un congelamento finale potra' fissarla.
RQ2_FINGERPRINT_PATHS = (
    "evaluation/rq2_probe_adapter.py",
    "evaluation/rq2_output_contracts.py",
    "evaluation/rq2_evidence_bundle.py",
    "evaluation/rq2_stage_binding.py",
    "evaluation/rq2_discovery_stage_recorder.py",
    "evaluation/rq2_discovery_claim_journal.py",
    "evaluation/rq2_stage_artifact_store.py",
)


class ProtocolIdentityError(ValueError):
    """Un sorgente, un prompt o una configurazione attesi sono cambiati."""


def git_blob_sha1(content: bytes) -> str:
    """SHA-1 dell'oggetto git, identico a quello riportato dalla Contents API di GitHub.

    E' lo SHA-1 di `blob <lunghezza>\\0` seguito dai byte del contenuto.
    """
    if type(content) is not bytes:
        raise ProtocolIdentityError("Source content must be bytes")
    header = b"blob " + str(len(content)).encode("ascii") + b"\x00"
    return hashlib.sha1(header + content).hexdigest()


def _sha256(content: bytes) -> str:
    """SHA-256 (esadecimale) dei byte `content`."""
    return hashlib.sha256(content).hexdigest()


def _read_source(src_root: Path, relative: str) -> bytes:
    """Byte del file `relative` sotto `src_root`; errore se manca, e' un link o non si legge."""
    # I percorsi vengono solo da elenchi statici di file, mai dall'output di un modello.
    src = src_root / relative
    if src.is_symlink() or not src.is_file():
        raise ProtocolIdentityError("Missing/symlink source: " + relative)
    try:
        return src.read_bytes()
    except OSError as exc:
        raise ProtocolIdentityError("Cannot read source: " + relative) from exc


def _check_frozen_blob(src_root: Path, relative: str, expected: str) -> str:
    """Controlla che l'hash git del file `relative` sia `expected`; restituisce il suo SHA-256.

    Gli a-capo `\\r\\n` vengono normalizzati in `\\n` prima del calcolo, quindi il risultato e'
    lo stesso su Windows e su Linux.
    """
    body = _read_source(src_root, relative)
    # Su Windows, Git puo' estrarre questi sorgenti Python con a-capo CRLF anche se il blob nel
    # repository e' con LF. Si normalizza SOLO per il confronto dell'hash del blob Git.
    normalized = body.replace(b"\r\n", b"\n")
    if git_blob_sha1(normalized) != expected:
        raise ProtocolIdentityError("Frozen RQ1 source changed: " + relative)
    return _sha256(normalized)


def preview_protocol_identity(*, src_root: Path | None = None) -> dict:
    """Anteprima pre-congelamento in sola lettura, sui sorgenti esatti. Nessun permesso API ne' scritture.

    Argomento (per nome): `src_root`, cartella `src` (di default quella di questo modulo).
    Restituisce il rapporto: hash dei sorgenti RQ1, modalita' di output di D, modelli proposti,
    hash dei prompt di C e K, impronte dei file RQ2 e le dichiarazioni "nessuna API, nessun
    congelamento scientifico".

    Passi: 1) i 13 sorgenti RQ1 hanno l'hash git congelato; 2) il codice di preregistrazione e
    di campagna impone ancora la modalita' "v2_enforce"; 3) modelli, harness, turni di tool e
    configurazione sono quelli di RQ1; 4) impronta SHA-256 dei file RQ2; 5) assemblaggio del
    rapporto.
    """
    # 1. Sorgenti RQ1 congelati: l'hash git di ciascuno deve coincidere con quello atteso.
    root = Path(src_root) if src_root is not None else Path(__file__).resolve().parents[1]
    rq1_sha256 = {
        path: _check_frozen_blob(root, path, blob)
        for path, blob in RQ1_BLOB_SHA1.items()
    }

    # 2. La modalita' di output di D "v2_enforce" e' presente nel codice di preregistrazione e di campagna.
    prereg = _read_source(root, "evaluation/evaluation20_preregister.py").decode("utf-8")
    campaign = _read_source(root, "evaluation/evaluation20_campaign.py").decode("utf-8")
    if (
        '"output_contract_mode": "v2_enforce"' not in prereg
        or 'output_contract_mode=plan["output_contract_mode"]' not in campaign
        or 'result.get("output_contract_mode") == "v2_enforce"' not in campaign
    ):
        raise ProtocolIdentityError("RQ1 D contract mode cannot be established")

    # 3. Parita' con RQ1: harness, modelli, turni di tool, modello Gemini predefinito, modelli
    # Anthropic noti e token massimi in uscita.
    ids = {m: CANDIDATE_MODELS[m]["model_id"] for m in MODELS}
    if (
        set(HARNESSES) != {"A1", "A1_8R"}
        or set(MODELS) != {"gemini", "sonnet", "haiku"}
        or MAX_TOOL_ROUNDS != 6
        or ExperimentConfig.__dataclass_fields__["model_name"].default != ids["gemini"]
        or {ids["sonnet"], ids["haiku"]} - ANTHROPIC_MODELS
        or ANTHROPIC_MAX_OUTPUT_TOKENS_PER_REQUEST != 4096
    ):
        raise ProtocolIdentityError("Existing RQ1 model/config parity broken")
    # 4. A differenza dei sorgenti RQ1, questi nuovi file RQ2 non sono ancora stati congelati
    # SCIENTIFICAMENTE: se ne registra l'SHA-256 corrente cosi' che un congelamento finale possa fissarlo.
    rq2_sha256 = {
        path: _sha256(_read_source(root, path))
        for path in RQ2_FINGERPRINT_PATHS
    }
    # 5. Rapporto: nulla e' congelato, abilitato o scritto.
    return {
        "version": VERSION,
        "status": "SOURCE_PROVENANCE_CAPTURE_NOT_SCIENTIFIC_FREEZE",
        "rq1_reference_commit": RQ1_FROZEN_REFERENCE_COMMIT,
        "rq1_source_blob_sha1_match": True,
        "rq1_source_sha256": rq1_sha256,
        "rq1_D_output_contract_mode_verified": RQ1_D_OUTPUT_MODE,
        "rq2_D_output_contract_mode_proposed_from_RQ1": RQ1_D_OUTPUT_MODE,
        "D_variant_scheme": "current",
        "D_max_tool_rounds": MAX_TOOL_ROUNDS,
        "D_recursion_limit": 30,
        "D_harnesses": list(HARNESSES),
        "models_proposed": ids,
        "D_anthropic_max_output_tokens_per_request": 4096,
        "D_anthropic_temperature_top_p_top_k_explicitly_set": False,
        "D_google_sampler_explicitly_pinned": False,
        "probe_adapter_version": PROBE_ADAPTER_VERSION,
        "C_system_prompt_sha256": _sha256(CAUSE_SYSTEM.encode("utf-8")),
        "K_system_prompt_sha256": _sha256(RULE_SYSTEM.encode("utf-8")),
        "rq2_code_sha256": rq2_sha256,
        "source_split_sha256_expected": EXPECTED_SPLIT_SHA256,
        "source_manifest_sha256_expected": EXPECTED_MANIFEST_SHA256,
        "C_K_tool_calls_allowed": False,
        "read_market": False,
        "read_ground_truth": False,
        "read_model_predictions": False,
        "provider_issued_requests": 0,
        "files_written": False,
        "rq2_scientific_protocol_frozen": False,
        "rq2_discovery_api_enabled": False,
        "rq2_test_unlocked": False,
        "cost_ceiling_required": False,
        "limitations": [
            "Matches RQ1 Git blobs at the stated frozen commit; does not check all dependency versions.",
            "Model ID support in source is not confirmation of remote provider availability.",
            "C/K system SHA256 is computed but NOT pinned as scientific freeze yet.",
            "Request-level C/K provider parameters and retry policy still need preregistration.",
            "Source files are scanned; no OOD development/discovery/test data are opened.",
        ],
    }


def main() -> None:
    """Riga di comando: stampa in JSON il rapporto di `preview_protocol_identity`."""
    report = preview_protocol_identity()
    print(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
