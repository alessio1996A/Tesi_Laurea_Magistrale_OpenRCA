"""Safe paired-run orchestration for the frozen GT-free development cohort.

NO API invocation happens during load/preflight. Execution is only entered
via execute_pair(), which requires an explicit case_id and confirmation.
It never invokes the benchmark scorer or reads the ground truth.
A permanent exclusive pair claim makes interrupted runs fail closed:
no automatic replay of potentially billed Gemini requests.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
from typing import Callable

from evaluation.experiment_config import ExperimentConfig
from evaluation.paired_cohort import (
    PROTOCOL,
    costruisci_piano_abbinato,
)

EXPECTED_SPLIT_COUNTS = {
    "development": 92,
    "evaluation": 23,
    "mixed_quarantine": 18,
    "ood_holdout": 15,
}
PLAN_FILENAME = f"{PROTOCOL}_cohort_v1.json"
RUN_ID_PATTERN = re.compile(
    rf"^{re.escape(PROTOCOL)}__cloudbed-[12]_q[0-9]+__(a1|a1_verify)__r01$"
)
COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")


def _json_read(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        item = json.load(f)
    if not isinstance(item, dict):
        raise ValueError(f"JSON deve essere oggetto: {path.name}")
    return item


def _json_exclusive(path: Path, value: dict) -> None:
    """Create only: never overwrite a historical or previously billed run."""
    with path.open("x", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def _git_sha(repo_dir: Path) -> str:
    p = subprocess.run(
        ["git", "-C", str(repo_dir), "rev-parse", "HEAD"],
        text=True, capture_output=True, check=True,
    )
    sha = p.stdout.strip()
    if not COMMIT_PATTERN.fullmatch(sha):
        raise ValueError("Git HEAD non valido")
    return sha


def _pairs_by_id(plan: dict) -> dict[str, dict]:
    cases = {}
    run_ids = set()
    for pair in plan["pairs"]:
        case_id = pair["case_id"]
        if case_id in cases:
            raise ValueError(f"Caso duplicato nel piano: {case_id}")
        if pair["ordered_variants"] not in (
            ["A1", "A1_VERIFY"], ["A1_VERIFY", "A1"]
        ):
            raise ValueError(f"Bracci non validi: {case_id}")
        for run_id in pair["run_ids"]:
            if not RUN_ID_PATTERN.fullmatch(run_id) or run_id in run_ids:
                raise ValueError(f"Run ID non valido/duplicato: {run_id}")
            run_ids.add(run_id)
        cases[case_id] = pair
    if len(cases) != plan["case_count"] or len(run_ids) != plan["run_count"]:
        raise ValueError("Numero di casi o esecuzioni incoerente")
    return cases


def carica_piano_congelato(
    data_dir: Path, *, expected_counts: dict | None = None
) -> tuple[dict, str]:
    """Reject stale or mutated plans BEFORE reading any telemetry or APIs."""
    data_dir = Path(data_dir)
    expected_counts = (
        EXPECTED_SPLIT_COUNTS if expected_counts is None
        else expected_counts
    )
    plan_path = data_dir / "data/protocols" / PLAN_FILENAME
    plan = _json_read(plan_path)
    if plan.get("protocol") != PROTOCOL:
        raise ValueError("Protocollo congelato non atteso")

    # The current inputs must reproduce EXACTLY the frozen plan.
    regenerated = costruisci_piano_abbinato(
        data_dir / "data/processed/split_market_v1.csv",
        data_dir / "data/processed/benchmark_inputs_market.csv",
        per_cloudbed=plan["per_cloudbed"],
    )
    if regenerated != plan:
        raise ValueError(
            "Piano non riproducibile: split, manifest, casi, ordine "
            "o parametri modificati. Non eseguire l'esperimento."
        )
    if plan["split_counts"] != expected_counts:
        raise ValueError("Conteggi split diversi dalla versione congelata")
    _pairs_by_id(plan)
    digest = sha256(plan_path.read_bytes()).hexdigest()
    return plan, digest


def _pair_paths(data_dir: Path, pair: dict) -> tuple[Path, list[Path]]:
    base = Path(data_dir) / "data/results/paired" / PROTOCOL
    claim = base / f"{pair['case_id']}__r01.pair_started.json"
    outputs = [base / f"{run_id}.json" for run_id in pair["run_ids"]]
    return claim, outputs


def preflight_paired(
    data_dir: Path,
    *,
    repo_dir: Path,
    expected_counts: dict | None = None,
) -> dict:
    """Read-only preflight. Never builds evidence or invokes an LLM."""
    plan, plan_sha = carica_piano_congelato(
        data_dir, expected_counts=expected_counts
    )
    head = _git_sha(Path(repo_dir))
    pairs = _pairs_by_id(plan)
    rows = []
    for case_id, pair in pairs.items():
        claim, outputs = _pair_paths(data_dir, pair)
        present = [p.exists() for p in outputs]
        if claim.exists() and all(present):
            status = "completed_never_rerun"
        elif claim.exists():
            status = "interrupted_or_partial_manual_review"
        elif any(present):
            status = "inconsistent_output_without_pair_claim"
        else:
            status = "ready"

        # All completed results in this cohort must use the same code SHA.
        for path in outputs:
            if not path.exists():
                continue
            result = _json_read(path)
            provenance = result.get("paired_provenance")
            if not isinstance(provenance, dict):
                raise ValueError(f"Provenienza mancante: {path.name}")
            if (provenance.get("git_commit") != head or
                    provenance.get("frozen_plan_sha256") != plan_sha):
                raise ValueError(
                    f"Versione codice/piano diversa da run preesistente: {path.name}"
                )
            if (result.get("variant") not in {"A1", "A1_VERIFY"}
                    or result.get("case_id") != case_id):
                raise ValueError(f"Risultato con identificativo incoerente: {path.name}")

        rows.append({
            "case_id": case_id,
            "ordered_variants": pair["ordered_variants"],
            "run_ids": pair["run_ids"],
            "status": status,
            "existing_results": sum(present),
        })

    return {
        "protocol": PROTOCOL,
        "git_commit": head,
        "frozen_plan_sha256": plan_sha,
        "split_file_sha256": plan["split_file_sha256"],
        "manifest_file_sha256": plan["input_manifest_sha256"],
        "case_count": plan["case_count"],
        "run_count": plan["run_count"],
        "read_ground_truth": False,
        "telemetry_loaded": False,
        "llm_called": False,
        "files_written": False,
        "pairs": rows,
    }


def _assert_result(
    result: dict,
    *,
    variant: str,
    case_id: str,
    expected_evidence_sha: str,
    max_tool_rounds: int,
    model_name: str,
    model_provider: str,
) -> list[str]:
    """Return integrity faults; do not discard evidence of a failed run."""
    issues = []
    if not isinstance(result, dict):
        return ["runner_non_ha_restituito_un_dizionario"]
    for key, value in (
        ("variant", variant),
        ("case_id", case_id),
        ("evidence_sha256", expected_evidence_sha),
        ("model", model_name),
        ("model_provider", model_provider),
        ("max_tool_rounds", max_tool_rounds),
    ):
        if result.get(key) != value:
            issues.append(f"{key}_incoerente")
    metrics = result.get("metrics")
    if not isinstance(metrics, dict):
        issues.append("metriche_mancanti")
    else:
        rounds = metrics.get("tool_rounds")
        if type(rounds) is not int or not 0 <= rounds <= max_tool_rounds:
            issues.append("round_tool_fuori_budget")
        if variant == "A1_VERIFY":
            a = metrics.get("exploration_tool_rounds")
            b = metrics.get("verification_tool_rounds")
            if type(a) is not int or type(b) is not int or a + b != rounds:
                issues.append("contabilizzazione_round_non_coerente")
            verification = result.get("verification")
            if (
                not isinstance(verification, dict)
                or verification.get("causa_verificata") is not False
            ):
                issues.append("verifica_causale_non_dimostrata")
    return issues


def esegui_coppia(
    data_dir: Path, *, repo_dir: Path, case_id: str,
    confirm_api: bool = False,
    expected_counts: dict | None = None,
    _prepare: Callable | None = None,
    _run: Callable | None = None,
) -> dict:
    """Execute exactly ONE pre-registered pair, with explicit API consent.

    There are no retries. A permanent pair claim is written BEFORE the
    first possible API call. If Colab disconnects, stop for manual review.
    Test injections are private and never exposed through the CLI.
    """
    if confirm_api is not True:
        raise PermissionError(
            "API disabilitate. Specificare l'autorizzazione esplicita."
        )

    status = preflight_paired(
        data_dir, repo_dir=repo_dir, expected_counts=expected_counts
    )
    rows = {item["case_id"]: item for item in status["pairs"]}
    if case_id not in rows:
        raise ValueError("Caso non appartenente alla coorte congelata")
    if rows[case_id]["status"] != "ready":
        raise FileExistsError(
            f"Coppia {case_id} non pronta: {rows[case_id]['status']}. "
            "Non ripetere chiamate API senza audit manuale."
        )
    plan, plan_sha = carica_piano_congelato(
        data_dir, expected_counts=expected_counts
    )
    pair = _pairs_by_id(plan)[case_id]

    if _prepare is None or _run is None:
        from evaluation.experiment_runner import (
            prepara_esperimento, run_experiment,
        )
        prepare = prepara_esperimento if _prepare is None else _prepare
        run = (
            (lambda config: run_experiment(
                config=config, llm=None, verbose=False, salva=False
            ))
            if _run is None else _run
        )
    else:
        prepare, run = _prepare, _run

    configs = {
        variant: ExperimentConfig(
            variant=variant,
            case_id=case_id,
            data_dir=Path(data_dir),
            repo_dir=Path(repo_dir),
            model_provider=plan["model_provider"],
            model_name=plan["model_name"],
            max_tool_rounds=pair["max_tool_rounds"],
            max_verification_checks=pair["max_verification_checks"],
            output_contract_mode=pair["output_contract_mode"],
        )
        for variant in pair["ordered_variants"]
    }

    # Precompute both reports *before* any API. Same SHA and official
    # time window are mandatory for this paired comparison.
    prepared = {
        variant: prepare(config)
        for variant, config in configs.items()
    }
    evidence_sha = prepared["A1"]["evidence_sha256"]
    if not isinstance(evidence_sha, str) or not re.fullmatch(
        r"[0-9a-f]{64}", evidence_sha
    ):
        raise ValueError("SHA del report evidenze mancante/non valido")
    if prepared["A1_VERIFY"]["evidence_sha256"] != evidence_sha:
        raise ValueError(
            "I report A1 e A1_VERIFY divergono. "
            "Non eseguire chiamate API."
        )
    for variant in pair["ordered_variants"]:
        case = prepared[variant]["caso"]
        if case["case_id"] != case_id:
            raise ValueError("Caso di preprocessing non coerente")
        if not (
            isinstance(case["start_unix"], int)
            and isinstance(case["end_unix"], int)
            and case["start_unix"] < case["end_unix"]
        ):
            raise ValueError("Finestra del caso non valida")

    # Ensure exactly the same official incident context and user request.
    case_a = prepared["A1"]["caso"]
    case_v = prepared["A1_VERIFY"]["caso"]
    for key in ("cloudbed", "start_unix", "end_unix", "instruction"):
        if case_a.get(key) != case_v.get(key):
            raise ValueError(
                f"Contesto ufficiale diverso fra i bracci: {key}"
            )
    if (
        not isinstance(prepared["A1"].get("richiesta"), str)
        or not prepared["A1"]["richiesta"].strip()
        or prepared["A1"].get("richiesta")
            != prepared["A1_VERIFY"].get("richiesta")
    ):
        raise ValueError(
            "Prompt utente A1 e A1_VERIFY diverso: "
            "non eseguire le chiamate API."
        )

    # Ripetiamo i controlli in sola lettura subito prima di occupare la coppia.
    # Questo evita di rilanciare run gia' salvate o iniziate in precedenza.
    # Repeat read-only checks immediately before the exclusive claim.
    renewed = preflight_paired(
        data_dir, repo_dir=repo_dir, expected_counts=expected_counts
    )
    if next(x for x in renewed["pairs"] if x["case_id"] == case_id)[
        "status"
    ] != "ready":
        raise FileExistsError("Coppia occupata prima dell'avvio")

    claim_path, output_paths = _pair_paths(data_dir, pair)
    claim_path.parent.mkdir(parents=True, exist_ok=True)
    # Il marcatore permanente viene creato PRIMA della prima chiamata API:
    # in caso di crash blocca un retry che potrebbe duplicare i costi.
    _json_exclusive(claim_path, {
        "status": "started_permanent_no_auto_retry",
        "case_id": case_id,
        "ordered_variants": pair["ordered_variants"],
        "run_ids": pair["run_ids"],
        "git_commit": status["git_commit"],
        "frozen_plan_sha256": plan_sha,
        "evidence_sha256_before_api": evidence_sha,
        "notes": (
            "An interrupted pair may contain billed API requests. "
            "Never auto-retry; inspect before planning a separate run ID."
        ),
    })

    # Salvataggio esclusivo: non sovrascriviamo mai diagnosi storiche.
    # Eventuali errori restano evidenze dell'esperimento.
    saved = []
    for index, variant in enumerate(pair["ordered_variants"]):
        result = run(configs[variant])
        if not isinstance(result, dict):
            raise RuntimeError(
                "Runner non ha restituito un dict: run potenzialmente "
                "fatturata, nessun retry automatico."
            )
        result = dict(result)
        issues = _assert_result(
            result, variant=variant,
            case_id=case_id,
            expected_evidence_sha=evidence_sha,
            max_tool_rounds=pair["max_tool_rounds"],
            model_name=plan["model_name"],
            model_provider=plan["model_provider"],
        )
        result["paired_provenance"] = {
            "protocol": PROTOCOL,
            "run_id": pair["run_ids"][index],
            "git_commit": status["git_commit"],
            "frozen_plan_sha256": plan_sha,
            "paired_evidence_sha256": evidence_sha,
            "execution_order_index": index,
            "integrity_issues": issues,
        }
        _json_exclusive(output_paths[index], result)
        saved.append(str(output_paths[index]))
        if issues:
            raise RuntimeError(
                f"Integrita' fallita dopo run {variant}: {issues}. "
                "Output conservato; non eseguire il secondo braccio "
                "o ripetere la coppia automaticamente."
            )

    return {
        "case_id": case_id,
        "ordered_variants": pair["ordered_variants"],
        "results_saved": saved,
        "evidence_sha256_equal": True,
        "api_execution_completed": True,
        "scoring_performed": False,
    }
