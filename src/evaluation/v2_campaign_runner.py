"""V2.6: campagna di 40 run. DEFAULT: preflight offline in sola lettura.

Una chiamata modello richiede esplicitamente --run-id, --execute e
--confirm-api. Mai eseguire in batch automaticamente, mai retry nascosti.
Ogni claim e risultato sono create-only in data/results/v2/<protocol>.
Non legge ground truth, risultati scoring o holdout.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

from evaluation.experiment_config import ExperimentConfig
from evaluation.v2_cohort_selector import PROTOCOL, VARIANTS
from evaluation.v2_preregister import _git_head_clean, _overlap
from evaluation.v2_case_window_audit import (
    MANIFEST_COLUMNS, SPLIT_COLUMNS, _read_csv, _sha,
)

RUN_RE = re.compile(r"^[a-z0-9_-]+$")
HEX64 = re.compile(r"^[a-f0-9]{64}$")


def plan_path(data_dir: Path) -> Path:
    return (
        Path(data_dir) / "data/protocols/v2" /
        f"{PROTOCOL}_plan_v1.json"
    )


def _results_dir(data_dir: Path) -> Path:
    return Path(data_dir) / "data/results/v2" / PROTOCOL


def _output_paths(data_dir: Path, run_id: str) -> tuple[Path, Path]:
    base = _results_dir(data_dir)
    return (base / f"{run_id}.claim.json", base / f"{run_id}.json")


def _exclusive_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2, sort_keys=True,
                  ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def load_preregistered(data_dir: Path, repo_dir: Path) -> tuple[dict, str]:
    """Controlla piano, repo e manifesto prima di qualsiasi API."""
    f = plan_path(data_dir)
    raw = f.read_bytes()
    plan = json.loads(raw.decode("utf-8"))
    if (
        plan.get("protocol") != PROTOCOL
        or plan.get("status") != "PREREGISTERED_NOT_EXECUTED"
        or plan.get("git_commit") != _git_head_clean(repo_dir)
        or plan.get("output_contract_mode") != "v2_enforce"
        or plan.get("model_provider") != "google"
        or plan.get("model_name") != "gemini-3.5-flash-lite"
        or plan.get("max_tool_rounds") != 6
        or plan.get("max_verification_checks") != 2
        or plan.get("recursion_limit") != 30
        or plan.get("run_count") != 40
        or plan.get("case_count") != 8
        or plan.get("ground_truth_accessed") is not False
        or plan.get("scoring_performed") is not False
    ):
        raise ValueError("Piano non valido o codice diverso dal commit congelato")

    root = Path(data_dir)
    split_path = root / "data/processed/split_market_v1.csv"
    manifest_path = root / "data/processed/benchmark_inputs_market.csv"
    if (
        _sha(split_path) != plan["split_sha256"]
        or _sha(manifest_path) != plan["manifest_sha256"]
    ):
        raise ValueError("Split e manifest differiscono dal piano")
    split = _read_csv(split_path, SPLIT_COLUMNS)
    manifest = _read_csv(manifest_path, MANIFEST_COLUMNS)
    if set(split) != set(manifest):
        raise ValueError("Set split/manifest differente")
    cases = plan.get("cases")
    if not isinstance(cases, list) or len(cases) != 8:
        raise ValueError("Otto casi non presenti")
    ids = set()
    run_ids = set()
    for pos, case in enumerate(cases):
        cid = case["case_id"]
        if cid in ids or cid not in split:
            raise ValueError("Caso assente o duplicato")
        ids.add(cid)
        row = split[cid]
        doc = manifest[cid]
        if row["split"] != "development":
            raise ValueError("Caso non development")
        if any((
            row["cloudbed"] != case["cloudbed"],
            row["cloudbed"] != doc["cloudbed"],
            int(row["start_unix"]) != case["start_unix"],
            int(row["end_unix"]) != case["end_unix"],
            doc["start_unix"] != row["start_unix"],
            doc["end_unix"] != row["end_unix"],
            doc["task_index"] != case["task_index"],
        )):
            raise ValueError(f"Metadati inconsistenti: {cid}")
        from output.v2_contract import infer_requested_faults
        if infer_requested_faults(doc["instruction"]) != case["requested_fault_count"]:
            raise ValueError("Cardinalita' dell'istruzione diversa dal piano")
        variants = case.get("ordered_variants")
        ids_for_case = case.get("run_ids")
        if (
            not isinstance(variants, list)
            or set(variants) != set(VARIANTS)
            or len(variants) != 5
            or len(ids_for_case or ()) != 5
        ):
            raise ValueError("Varianti o run ID incompleti")
        expected_order = list(VARIANTS[pos % 5:] + VARIANTS[:pos % 5])
        if variants != expected_order:
            raise ValueError("Ordine dei cinque agenti non preregistrato")
        for variant, run_id in zip(variants, ids_for_case):
            expected = f"{PROTOCOL}__{cid}__{variant.lower()}__r01"
            if (
                run_id != expected or not RUN_RE.fullmatch(run_id)
                or run_id in run_ids
            ):
                raise ValueError("Run ID fuori piano o duplicato")
            run_ids.add(run_id)
    if len(run_ids) != 40 or any(
        _overlap(a, b) for i, a in enumerate(cases) for b in cases[i+1:]
    ):
        raise ValueError("Casi sovrapposti o run non complete")
    return plan, hashlib.sha256(raw).hexdigest()


def preflight_campaign(data_dir: Path, repo_dir: Path) -> dict:
    """Nessuna inferenza, scrittura o caricamento telemetria."""
    plan, plan_sha = load_preregistered(data_dir, repo_dir)
    runs = []
    for case in plan["cases"]:
        predecessors_complete = True
        for index, (variant, run_id) in enumerate(zip(
            case["ordered_variants"], case["run_ids"]
        )):
            claim, output = _output_paths(data_dir, run_id)
            if output.exists() and claim.exists():
                status = "complete"
            elif claim.exists():
                status = "started_or_interrupted_NO_AUTO_RETRY"
            elif output.exists():
                status = "orphan_output_REVIEW"
            else:
                status = (
                    "ready" if predecessors_complete
                    else "waiting_for_previous_variant"
                )
            runs.append({
                "run_id": run_id, "case_id": case["case_id"],
                "variant": variant, "order_index": index,
                "status": status,
            })
            if status != "complete":
                predecessors_complete = False
    return {
        "protocol": PROTOCOL,
        "plan_sha256": plan_sha,
        "git_commit": plan["git_commit"],
        "runs": runs,
        "status_counts": dict(sorted(
            {status: sum(r["status"] == status for r in runs)
             for status in {x["status"] for x in runs}}.items()
        )),
        "llm_called": False,
        "telemetry_loaded": False,
        "files_written": False,
        "scoring_performed": False,
    }


def _integrity_issues(result: dict, case: dict, variant: str, plan: dict):
    issues = []
    for key, value in (
        ("case_id", case["case_id"]),
        ("variant", variant),
        ("cloudbed", case["cloudbed"]),
        ("task_index", case["task_index"]),
        ("model", plan["model_name"]),
        ("model_provider", plan["model_provider"]),
        ("max_tool_rounds", plan["max_tool_rounds"]),
        ("output_contract_mode", "v2_enforce"),
    ):
        if result.get(key) != value:
            issues.append(f"{key}_incoerente")
    metrics = result.get("metrics")
    if not isinstance(metrics, dict):
        issues.append("metriche_mancanti")
    else:
        rounds = metrics.get("tool_rounds")
        if type(rounds) is not int or not 0 <= rounds <= 6:
            issues.append("round_fuori_budget")
        if variant in ("A1_VERIFY", "A1_VERIFY_ST"):
            a = metrics.get("exploration_tool_rounds")
            b = metrics.get("verification_tool_rounds")
            if type(a) is not int or type(b) is not int or a + b != rounds:
                issues.append("round_esplorazione_verifica_incoerenti")
            if result.get("verification", {}).get("causa_verificata") is not False:
                issues.append("claim_causale_non_supportato")
    if not isinstance(result.get("output_contract_v2"), dict):
        issues.append("manca_audit_task_aware")
    if not isinstance(result.get("raw_response"), (str, type(None))):
        issues.append("raw_response_non_serializzabile")
    evidence_sha = result.get("evidence_sha256")
    if variant == "A0":
        if evidence_sha is not None:
            issues.append("a0_non_deve_avere_report_evidenze")
    elif not isinstance(evidence_sha, str) or not HEX64.fullmatch(evidence_sha):
        issues.append("evidence_sha_non_valido")
    return issues



def _ensure_runtime_ready(variant: str) -> None:
    """Importa dipendenze del modello e dei grafi senza invocare Gemini.

    Se un pacchetto non e' installato, NON creare alcun claim permanente.
    """
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from agent.graph_engine import crea_grafo_rca, esegui_grafo_rca
        if variant in ("A1_VERIFY", "A1_VERIFY_ST"):
            from agent.verify_graph import (
                crea_grafo_rca_verify, esegui_grafo_rca_verify,
            )
    except ImportError as exc:
        raise RuntimeError(
            "Dipendenza runtime mancante/incompatibile. "
            "Installare requirements.txt e ripetere i test offline "
            "PRIMA di avviare il run: " + str(exc)
        ) from exc


def execute_exactly_one(
    data_dir: Path, repo_dir: Path, *,
    run_id: str, confirm_api: bool = False,
    _runner=None,
) -> dict:
    """Una sola esecuzione; claim permanente prima della possibile API."""
    if confirm_api is not True:
        raise PermissionError("Richiesta autorizzazione esplicita alle API")
    status = preflight_campaign(data_dir, repo_dir)
    matches = [row for row in status["runs"] if row["run_id"] == run_id]
    if len(matches) != 1:
        raise ValueError("Run non presente nel piano congelato")
    row = matches[0]
    if row["status"] != "ready":
        raise FileExistsError("Run gia' occupata/svolta: stop senza retry")
    plan, plan_sha = load_preregistered(data_dir, repo_dir)
    case = next(x for x in plan["cases"] if x["case_id"] == row["case_id"])
    variant = row["variant"]

    # Il protocollo preregistra un ordine interno a ogni incidente.
    # Ogni precedente deve avere claim, output e provenienza validi.
    # Questo controllo avviene prima di leggere telemetria o chiamare API.
    for previous_id in case["run_ids"][:row["order_index"]]:
        prior_claim, prior_output = _output_paths(data_dir, previous_id)
        if not prior_claim.is_file() or not prior_output.is_file():
            raise RuntimeError("Variante precedente incompleta: ordine bloccato")
        previous = json.loads(prior_output.read_text(encoding="utf-8"))
        claim_data = json.loads(prior_claim.read_text(encoding="utf-8"))
        provenance = previous.get("v2_provenance") or {}
        if (
            claim_data.get("run_id") != previous_id
            or claim_data.get("plan_sha256") != plan_sha
            or provenance.get("run_id") != previous_id
            or provenance.get("plan_sha256") != plan_sha
            or provenance.get("git_commit") != plan["git_commit"]
            or provenance.get("integrity_issues") != []
        ):
            raise ValueError(
                "Provenienza o integrita' della variante precedente errata"
            )

    config = ExperimentConfig(
        variant=variant,
        case_id=case["case_id"],
        repo_dir=Path(repo_dir),
        data_dir=Path(data_dir),
        model_name=plan["model_name"],
        model_provider=plan["model_provider"],
        max_tool_rounds=plan["max_tool_rounds"],
        max_verification_checks=plan["max_verification_checks"],
        recursion_limit=plan["recursion_limit"],
        output_contract_mode="v2_enforce",
    )

    # Nessuna chiamata LLM: controllo del caso ufficiale prima del claim.
    from evaluation.experiment_runner import (
        carica_caso, prepara_esperimento, run_experiment,
    )
    original = carica_caso(config)
    for key, value in (
        ("case_id", case["case_id"]),
        ("cloudbed", case["cloudbed"]),
        ("task_index", case["task_index"]),
        ("start_unix", case["start_unix"]),
        ("end_unix", case["end_unix"]),
    ):
        if original.get(key) != value:
            raise ValueError(f"Caso manifest diverso dal freeze: {key}")

    # Preprocessing GT-free PRIMA del claim permanente: errori di
    # telemetria/strumenti non devono impegnare un run con costo API zero.
    prepared = prepara_esperimento(config)
    prepared_case = prepared.get("caso", {})
    for key, expected in (
        ("case_id", case["case_id"]),
        ("cloudbed", case["cloudbed"]),
        ("task_index", case["task_index"]),
        ("start_unix", case["start_unix"]),
        ("end_unix", case["end_unix"]),
    ):
        if prepared_case.get(key) != expected:
            raise ValueError(f"Preprocessing differente dal piano: {key}")
    evidence_sha = prepared.get("evidence_sha256")
    # A0 e' baseline priva di report. La mancanza dello SHA e' voluta.
    # Gli altri quattro agenti devono avere uno SHA-256 verificabile.
    if variant == "A0":
        if evidence_sha is not None:
            raise ValueError("A0 non deve generare report deterministico")
    elif not isinstance(evidence_sha, str) or not HEX64.fullmatch(evidence_sha):
        raise ValueError("SHA delle evidenze preprocessate mancante")

    # I test possono iniettare un fake runner; per le esecuzioni REALI
    # importiamo il modello e i grafi senza rete, PRIMA del claim.
    if _runner is None:
        _ensure_runtime_ready(variant)

    # Controllo status subito prima del marcatore create-only.
    refreshed = preflight_campaign(data_dir, repo_dir)
    if next(x for x in refreshed["runs"] if x["run_id"] == run_id)["status"] != "ready":
        raise FileExistsError("Run occupata durante preflight")
    claim, path = _output_paths(data_dir, run_id)
    _exclusive_json(claim, {
        "status": "started_permanent_no_automatic_retry",
        "run_id": run_id,
        "case_id": case["case_id"],
        "variant": variant,
        "execution_order_index": row["order_index"],
        "git_commit": plan["git_commit"],
        "plan_sha256": plan_sha,
        "evidence_sha256_before_api": evidence_sha,
        "note": "Se Colab si interrompe, verificare prima di qualsiasi nuovo run.",
    })
    execute = _runner or (
        lambda cfg: run_experiment(cfg, llm=None, verbose=False, salva=False)
    )
    result = execute(config)
    if not isinstance(result, dict):
        raise RuntimeError("Runner fallito dopo claim, no retry automatico")
    result = dict(result)
    issues = _integrity_issues(result, case, variant, plan)
    if result.get("evidence_sha256") != evidence_sha:
        issues.append("evidence_sha_diverso_dal_preprocessing")
    result["v2_provenance"] = {
        "protocol": PROTOCOL,
        "run_id": run_id,
        "plan_sha256": plan_sha,
        "git_commit": plan["git_commit"],
        "execution_order_index": row["order_index"],
        "integrity_issues": issues,
    }
    _exclusive_json(path, result)
    if issues:
        raise RuntimeError(
            f"Risultato salvato ma integrita' da controllare: {issues}"
        )
    return {
        "run_id": run_id,
        "saved": str(path),
        "json_status": result.get("json_status"),
        "integrity_issues": issues,
        "scoring_performed": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--repo-dir", required=True, type=Path)
    parser.add_argument("--run-id")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-api", action="store_true")
    args = parser.parse_args()
    if args.execute:
        if not args.run_id or not args.confirm_api:
            parser.error("--execute richiede --run-id e --confirm-api")
        answer = execute_exactly_one(
            args.data_dir, args.repo_dir, run_id=args.run_id,
            confirm_api=True,
        )
    else:
        if args.run_id or args.confirm_api:
            parser.error("--run-id e --confirm-api sono ammessi solo con --execute")
        answer = preflight_campaign(args.data_dir, args.repo_dir)
    print(json.dumps(answer, ensure_ascii=False, indent=2,
                     allow_nan=False))


if __name__ == "__main__":
    main()
