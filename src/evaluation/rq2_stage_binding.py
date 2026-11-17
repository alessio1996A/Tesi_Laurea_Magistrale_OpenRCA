"""Collegamento (binding) SOLO OFFLINE dei pacchetti di prompt C/K di RQ2 agli stadi della bozza di workflow.

Nessun client di modelli, nessun I/O su file, nessuno scoring, nessuna telemetria e nessun ground
truth. E' un *controllo preliminare* di integrita' su un piano BOZZA_NON_ESEGUIBILE
(`DRAFT_NOT_EXECUTABLE`), NON l'autorizzazione a eseguire alcuno stadio. Accetta soltanto un
dizionario di esecuzione D gia' registrata, fornito dal chiamante; non chiama mai la funzione
storica `run_experiment`.

Un SHA coincidente dei byte forniti prova solo la coerenza interna, non che il manifest sorgente
senza ground truth sia stato davvero letto e verificato. Un futuro esecutore RQ2 DEVE imporre
gli ID dei modelli congelati, gli hash dei byte sorgente, l'approvazione dei costi, la
persistenza a sola creazione e una regola di congelamento da discovery a test scientificamente
valida.

Contenuto:
- costanti: versione del binding, strumenti ammessi, fornitore di ogni modello, insiemi esatti
  di chiavi richieste per esecuzione, piano, voce di stadio e partizione;
- `StageBindingError`: errore "stadio, sorgente o provenienza non verificabili offline";
- `_canonical`, `_sha`: JSON canonico e suo SHA-256;
- `_validate_plan`: convalida rigorosa del piano bozza (204 voci: D 90, C 90, K 24) e
  restituzione delle voci per `stage_id`;
- `_run_identity`: coerenza fra l'esecuzione D fornita e lo stadio pianificato;
- `_binding`: costruzione del record di binding con il suo hash;
- `prepare_bound_c`, `prepare_bound_k`: preparano i pacchetti di prompt di C e di K collegati
  allo stadio (K solo in discovery e solo con lo STESSO input D e il C corrispondente).
"""
from __future__ import annotations

import hashlib
import json

from evaluation.rq2_dryrun_plan import (
    HARNESSES, MODELS, PLAN_STATUS, VERSION, MAX_TOOL_ROUNDS,
)
from evaluation.rq2_probe_adapter import (
    prepare_cause_probe, prepare_candidate_rule, ProbeInputError,
)

VERSION_BIND = "rq2_offline_stage_binding_v0"
# Gli unici strumenti ammessi nei pacchetti di prompt (stessi nomi dell'harness RQ1).
ALLOWED_TOOLS = (
    "tool_get_service_metrics", "tool_get_container_metrics",
    "tool_get_node_metrics", "tool_get_logs", "tool_get_traces",
)
# Fornitore atteso per ciascun modello logico.
MODEL_PROVIDERS = {
    "gemini": "google",
    "sonnet": "anthropic",
    "haiku": "anthropic",
}
# Chiavi obbligatorie in un dizionario di esecuzione D registrata.
REQUIRED_RUN_KEYS = {
    "case_id", "variant", "variant_scheme", "model",
    "model_provider", "max_tool_rounds", "raw_response",
    "tool_trajectory", "error",
}
# Insieme ESATTO di chiavi del piano bozza (nessuna in piu', nessuna in meno).
PLAN_KEYS = {
    "protocol", "status", "preview_only", "source_verified",
    "split_sha256", "manifest_sha256", "partition",
    "logical_models", "harnesses", "provider_model_versions_frozen",
    "api_budget_approved", "can_execute_api", "cross_phase_gate",
    "stages", "total_stage_entries", "model_api_calls",
    "files_written", "reads_ground_truth", "reads_predictions",
    "reads_telemetry", "limitations", "preview_sha256", "entries",
}
# Insieme esatto di chiavi di ogni voce di stadio: solo campi senza ground truth.
ENTRY_KEYS = {
    "stage_id", "case_id", "cloudbed", "task_index",
    "start_unix", "end_unix", "phase", "logical_model",
    "harness", "max_tool_rounds_for_D", "stage", "dependencies",
    "execution_status",
}
# Insieme esatto di chiavi della partizione discovery/test.
PARTITION_KEYS = {
    "discovery_case_ids", "test_case_ids", "discovery_cases",
    "test_cases", "discovery_windows", "test_windows",
    "min_cross_phase_same_cloudbed_gap_seconds",
    "discovery_by_cloudbed", "test_by_cloudbed",
}


class StageBindingError(ValueError):
    """Stadio, sorgente o provenienza dell'output precedente non verificabili offline."""


def _canonical(value: object) -> bytes:
    """Serializza `value` in JSON canonico (chiavi ordinate, senza spazi, UTF-8); errore se non serializzabile."""
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True,
            allow_nan=False, separators=(",", ":"),
        ).encode("utf-8")
    except (ValueError, TypeError, RecursionError) as exc:
        raise StageBindingError("Unserializable package") from exc


def _sha(value: object) -> str:
    """SHA-256 (esadecimale) del JSON canonico di `value`."""
    return hashlib.sha256(_canonical(value)).hexdigest()


def _validate_plan(plan: dict) -> dict[str, dict]:
    """Convalida in modo rigoroso il piano bozza `plan` e restituisce le sue voci indicizzate per `stage_id`.

    Solleva `StageBindingError` se il piano non e' ESATTAMENTE la bozza bloccata e senza ground
    truth attesa.

    Passi: 1) insieme di chiavi esatto, protocollo, stato bozza, nessuna API/budget/chiamata/file
    scritto/lettura di ground truth, 204 voci con la ripartizione D 90, C 90, K 24, modelli e
    harness attesi, gate fra le fasi chiuso; 2) l'hash di anteprima coincide con quello ricalcolato;
    3) partizione con 4 casi di discovery e 11 di test, tutti diversi; 4) per ogni voce: campi
    ammessi, id e fase coerenti, nessun K nei test, stato "bloccato", id di stadio e dipendenze
    attesi (D nessuna, C da D, K da C); 5) l'insieme degli stadi coincide con la coorte 4+11.
    """
    if type(plan) is not dict or set(plan) != PLAN_KEYS or (
        plan.get("protocol") != VERSION
        or plan.get("status") != PLAN_STATUS
        or plan.get("preview_only") is not True
        or plan.get("can_execute_api") is not False
        or plan.get("api_budget_approved") is not False
        or plan.get("model_api_calls") != 0
        or plan.get("files_written") is not False
        or plan.get("reads_ground_truth") is not False
        or plan.get("reads_predictions") is not False
        or plan.get("reads_telemetry") is not False
        or plan.get("provider_model_versions_frozen") is not False
        or plan.get("total_stage_entries") != 204
        or plan.get("stages") != {"D": 90, "C": 90, "K": 24}
        or plan.get("logical_models") != list(MODELS)
        or plan.get("harnesses") != list(HARNESSES)
        or plan.get("cross_phase_gate")
        != "TEST_BLOCKED_UNTIL_DISCOVERY_RULES_FREEZE"
    ):
        raise StageBindingError("Only blocked GT-free draft preview is admissible")
    entries = plan.get("entries")
    if type(entries) is not list or len(entries) != 204:
        raise StageBindingError("Expected 204 draft stage entries")
    summary = {
        key: val for key, val in plan.items()
        if key not in ("preview_sha256", "entries")
    }
    expected = _sha({"summary": summary, "entries": entries})
    if plan.get("preview_sha256") != expected:
        raise StageBindingError("Plan preview SHA256 mismatch")
    partitions = plan.get("partition")
    if type(partitions) is not dict or set(partitions) != PARTITION_KEYS:
        raise StageBindingError("Missing/unknown discovery/test partition fields")
    discovery = partitions.get("discovery_case_ids")
    test = partitions.get("test_case_ids")
    if (type(discovery) is not list or type(test) is not list
            or len(discovery) != 4 or len(test) != 11
            or any(type(cid) is not str for cid in discovery + test)
            or len(set(discovery + test)) != 15):
        raise StageBindingError("Invalid phase lists")
    phase_map = {
        **{cid: "discovery" for cid in discovery},
        **{cid: "test" for cid in test},
    }
    by_id = {}
    observed = set()
    for item in entries:
        if type(item) is not dict or set(item) != ENTRY_KEYS:
            raise StageBindingError("Stage must contain only GT-free fields")
        sid = item.get("stage_id")
        cid = item.get("case_id")
        phase = item.get("phase")
        model = item.get("logical_model")
        harness = item.get("harness")
        stage = item.get("stage")
        if (
            type(sid) is not str or sid in by_id
            or cid not in phase_map or phase != phase_map[cid]
            or model not in MODELS or harness not in HARNESSES
            or stage not in ("D", "C", "K")
            or (phase == "test" and stage == "K")
            or item.get("execution_status") != "BLOCKED_DRAFT"
            or item.get("max_tool_rounds_for_D") != MAX_TOOL_ROUNDS
        ):
            raise StageBindingError("Malformed or unauthorized draft stage")
        prefix = f"{VERSION}:{cid}:{model}:{harness}"
        if sid != f"{prefix}:{stage}":
            raise StageBindingError("Stage ID does not match case/model/harness")
        expected_dependency = (
            [] if stage == "D" else
            [prefix + ":D"] if stage == "C" else
            [prefix + ":C"]
        )
        if item.get("dependencies") != expected_dependency:
            raise StageBindingError("Unexpected D/C/K dependencies")
        by_id[sid] = item
        observed.add((cid, model, harness, stage))
    expected_stages = {
        (cid, model, harness, stage)
        for cid, phase in phase_map.items()
        for model in MODELS for harness in HARNESSES
        for stage in (("D", "C", "K") if phase == "discovery" else ("D", "C"))
    }
    if observed != expected_stages or len(by_id) != len(expected_stages):
        raise StageBindingError("Stage set differs from 4+11 draft cohort")
    return by_id


def _run_identity(run: dict, entry: dict) -> None:
    """Controlla che l'esecuzione D `run` sia coerente con lo stadio pianificato `entry`.

    Verifica chiavi richieste, caso, harness, schema di variante, numero massimo di round,
    fornitore e che il nome logico del modello compaia nell'identificativo registrato.
    """
    if type(run) is not dict or REQUIRED_RUN_KEYS - set(run):
        raise StageBindingError("Incomplete D run metadata")
    model = run["model"]
    logical = entry["logical_model"]
    if (
        run["case_id"] != entry["case_id"]
        or run["variant"] != entry["harness"]
        or run["variant_scheme"] != "current"
        or run["max_tool_rounds"] != MAX_TOOL_ROUNDS
        or run["model_provider"] != MODEL_PROVIDERS[logical]
        or type(model) is not str
        or logical not in model.lower()
    ):
        raise StageBindingError("D identity inconsistent with planned stage")
    # Le versioni esatte dei modelli e la temperatura NON sono congelate nella fase di bozza.
    # Il confronto per sottostringa sul nome del modello e' una guardia preliminare, non una
    # certificazione dell'identita'.


def _binding(plan: dict, entry: dict, package: dict) -> dict:
    """Costruisce il record di binding fra `package` e lo stadio `entry`, con il proprio hash.

    Il record dichiara esplicitamente: sorgente NON verificato qui, versioni dei modelli e regole
    scientifiche NON congelate, nessuna API eseguibile, zero chiamate. Restituisce il record con
    l'aggiunta di `binding_sha256`.
    """
    bound = {
        "binding_version": VERSION_BIND,
        "stage_id": entry["stage_id"],
        "phase": entry["phase"],
        "case_id": entry["case_id"],
        "harness": entry["harness"],
        "logical_model": entry["logical_model"],
        "dependency_ids": entry["dependencies"],
        "plan_preview_sha256": plan["preview_sha256"],
        "underlying_package": package,
        "source_verified_in_this_function": False,
        "provider_model_versions_frozen": False,
        "scientific_rules_frozen": False,
        "can_execute_api": False,
        "model_api_calls": 0,
    }
    return {**bound, "binding_sha256": _sha(bound)}


def prepare_bound_c(
    *, plan: dict, c_stage_id: str, original_instruction: str,
    diagnostic_run: dict,
) -> dict:
    """Collega un prompt C a una *forma* approvata di coppia di stadi D/C della bozza.

    Argomenti (per nome): `plan` (piano bozza), `c_stage_id` (stadio C richiesto),
    `original_instruction` (istruzione originale della diagnosi), `diagnostic_run` (esecuzione D
    registrata). Restituisce il record di binding con il pacchetto di prompt di C.

    Passi: 1) convalida del piano; 2) lo stadio richiesto deve esistere ed essere di tipo C;
    3) coerenza dell'esecuzione D con lo stadio; 4) preparazione del pacchetto di prompt (un
    errore di input diventa `StageBindingError`); 5) costruzione del binding.
    """
    entries = _validate_plan(plan)
    entry = entries.get(c_stage_id)
    if entry is None or entry["stage"] != "C":
        raise StageBindingError("Requested stage is not an existing C stage")
    _run_identity(diagnostic_run, entry)
    try:
        package = prepare_cause_probe(
            original_instruction=original_instruction,
            diagnostic_run=diagnostic_run,
            allowed_tool_names=ALLOWED_TOOLS,
        )
    except ProbeInputError as exc:
        raise StageBindingError("Cannot prepare C input: " + str(exc)) from exc
    return _binding(plan, entry, package)


def prepare_bound_k(
    *, plan: dict, k_stage_id: str, original_instruction: str,
    diagnostic_run: dict, prior_c_binding: dict, cause_raw_json: str,
) -> dict:
    """K e' ammesso solo in discovery, con lo STESSO input D e il C corrispondente.

    Argomenti (per nome): `plan`, `k_stage_id`, `original_instruction`, `diagnostic_run`,
    `prior_c_binding` (binding di C gia' ottenuto) e `cause_raw_json` (risposta grezza della
    causa proposta in C). Restituisce il record di binding con il pacchetto di prompt di K.

    Passi: 1) convalida del piano; 2) lo stadio deve essere un K di discovery; 3) coerenza
    dell'esecuzione D; 4) ricostruisce il binding di C atteso e lo confronta con quello fornito
    (devono essere identici); 5) prepara il pacchetto di prompt della regola candidata; 6)
    costruisce il binding.
    """
    entries = _validate_plan(plan)
    entry = entries.get(k_stage_id)
    if entry is None or entry["stage"] != "K" or entry["phase"] != "discovery":
        raise StageBindingError("K stage unavailable outside discovery")
    _run_identity(diagnostic_run, entry)
    c_id = entry["dependencies"][0]
    reference = prepare_bound_c(
        plan=plan, c_stage_id=c_id,
        original_instruction=original_instruction,
        diagnostic_run=diagnostic_run,
    )
    if prior_c_binding != reference:
        raise StageBindingError(
            "C binding is not identical to planned D evidence and instruction"
        )
    try:
        package = prepare_candidate_rule(
            original_instruction=original_instruction,
            diagnostic_run=diagnostic_run,
            cause_raw_json=cause_raw_json,
            phase=entry["phase"],
            allowed_tool_names=ALLOWED_TOOLS,
        )
    except ProbeInputError as exc:
        raise StageBindingError("Cannot prepare K input: " + str(exc)) from exc
    return _binding(plan, entry, package)
