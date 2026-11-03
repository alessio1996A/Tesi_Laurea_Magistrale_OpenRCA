"""V2.5: proposta riproducibile di una NUOVA coorte GT-free, solo development.

Selezione solo dagli split+manifest originali, dai piani congelati e dal
report A/2 (network KPI inventory). Nessun log, metrica, predizione, score,
query.csv/record.csv o API. Nessun file sovrascritto. La selezione di
finestre NON e' una misura dell'indipendenza statistica degli incidenti.

Esempio:
 python -m evaluation.v2_cohort_selector --data-dir ... \
   --inventory /content/network_kpi_inventory_v1.json
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from evaluation.v2_case_window_audit import (
    MANIFEST_COLUMNS, MANIFEST_SHA256, PROTOCOLS,
    SPLIT_COLUMNS, SPLIT_SHA256, _overlap, _read_csv, _sha, _window,
)
from output.v2_contract import infer_requested_faults

PROTOCOL = "openrca_harness_v2_five_agents_development_v1"
SEED = "openrca-harness-v2-five-agents-2026-11-03-v1"
AUDIT_SEED = "network-kpi-inventory-2026-11-03-v1"
VARIANTS = ("A0", "A1_V2", "A1", "A1_VERIFY", "A1_VERIFY_ST")
BALANCED_SEED = "openrca-harness-v2-balanced-seven-tasks-2026-11-03-v1"
# Snapshot letterale di SEEN_CASE_IDS in src/evaluation/network_kpi_inventory.py
# del branch feature/r03-r05-feasibility-schema-v1.
# Include 12 piloti/coorte iniziale, 8 ST, q009 e ulteriori batch development.
HISTORICAL_SEEN = frozenset({
    "cloudbed-1_q002", "cloudbed-1_q009", "cloudbed-1_q016",
    "cloudbed-1_q034", "cloudbed-1_q035", "cloudbed-1_q036",
    "cloudbed-1_q038", "cloudbed-1_q040", "cloudbed-1_q043",
    "cloudbed-1_q052", "cloudbed-1_q063", "cloudbed-1_q065",
    "cloudbed-1_q067",
    "cloudbed-2_q006", "cloudbed-2_q007", "cloudbed-2_q012",
    "cloudbed-2_q015", "cloudbed-2_q033", "cloudbed-2_q046",
    "cloudbed-2_q053", "cloudbed-2_q055", "cloudbed-2_q066",
    "cloudbed-2_q067", "cloudbed-2_q068", "cloudbed-2_q073",
})


def _rank(seed: str, case_id: str) -> str:
    return hashlib.sha256(f"{seed}|{case_id}".encode("utf-8")).hexdigest()



def _select_balanced(eligible, manifest, per_cloudbed):
    """Selezione GT-free: tutte le sette task, 4+4 e un multi per cloudbed."""
    from collections import Counter

    if 2 * per_cloudbed < 7:
        raise ValueError("Campione troppo piccolo per sette task")
    ranked = []
    for row in eligible:
        info = manifest[row["case_id"]]
        n = infer_requested_faults(info["instruction"])
        if info["task_index"] not in {f"task_{i}" for i in range(1, 8)} or n is None:
            raise ValueError("Task o cardinalita' non riconosciuta")
        ranked.append({**row, "task": info["task_index"], "faults": n})
    ranked.sort(key=lambda r: (
        hashlib.sha256(
            f"{BALANCED_SEED}|{r['case_id']}".encode()
        ).hexdigest(), r["case_id"]
    ))
    tasks = {f"task_{i}" for i in range(1, 8)}
    groups = {t: [r for r in ranked if r["task"] == t] for t in tasks}
    if not all(groups.values()):
        raise ValueError("Sette task non disponibili")
    order = sorted(tasks, key=lambda t: (len(groups[t]), t))
    visits = [0]

    def search(chosen, step):
        visits[0] += 1
        if visits[0] > 200000:
            raise ValueError("Limite ricerca coorte: stop senza fallback")
        counts = Counter(r["cloudbed"] for r in chosen)
        if len(chosen) == 2 * per_cloudbed:
            multi = Counter(
                r["cloudbed"] for r in chosen if r["faults"] >= 2
            )
            if step == 7 and all(
                counts[c] == per_cloudbed and multi[c] >= 1
                for c in ("cloudbed-1", "cloudbed-2")
            ):
                return chosen
            return None
        pool = groups[order[step]] if step < 7 else ranked
        for r in pool:
            if counts[r["cloudbed"]] >= per_cloudbed:
                continue
            if any(r["case_id"] == x["case_id"] or _overlap(r, x)
                   for x in chosen):
                continue
            found = search(chosen + [r], step + (step < 7))
            if found is not None:
                return found
        return None

    selected = search([], 0)
    if selected is None:
        raise ValueError("Nessuna coorte bilanciata senza sovrapposizioni")
    return sorted(selected, key=lambda r: (
        r["cloudbed"],
        hashlib.sha256(
            f"{BALANCED_SEED}|{r['case_id']}".encode()
        ).hexdigest()
    ))

def propose_v2_cohort(
    data_dir: Path,
    inventory_path: Path,
    *,
    per_cloudbed: int = 4,
    verify_original_hashes: bool = True,
    historical_seen: frozenset[str] = HISTORICAL_SEEN,
) -> dict:
    if type(per_cloudbed) is not int or per_cloudbed < 1:
        raise ValueError("per_cloudbed deve essere positivo")
    root = Path(data_dir)
    split_path = root / "data/processed/split_market_v1.csv"
    manifest_path = root / "data/processed/benchmark_inputs_market.csv"
    split_sha, manifest_sha = _sha(split_path), _sha(manifest_path)
    if verify_original_hashes and (
        split_sha != SPLIT_SHA256 or manifest_sha != MANIFEST_SHA256
    ):
        raise ValueError("SHA-256 split/manifest GT-free non originali")
    split = _read_csv(split_path, SPLIT_COLUMNS)
    manifest = _read_csv(manifest_path, MANIFEST_COLUMNS)
    if set(split) != set(manifest):
        raise ValueError("Split/manifest: insieme di case_id diverso")
    if not historical_seen.issubset(split):
        raise ValueError("Registro storico cita ID non presenti nello split")
    if verify_original_hashes and dict(Counter(
        r["split"] for r in split.values()
    )) != {
        "development": 92, "evaluation": 23,
        "mixed_quarantine": 18, "ood_holdout": 15,
    }:
        raise ValueError("Distribuzione dello split incoerente")
    for case_id, row in split.items():
        if (
            row["cloudbed"] not in ("cloudbed-1", "cloudbed-2")
            or not case_id.startswith(row["cloudbed"] + "_q")
        ):
            raise ValueError(f"{case_id}: cloudbed non valido")
        if any(
            row[k] != manifest[case_id][k]
            for k in ("start_unix", "end_unix", "cloudbed")
        ):
            raise ValueError(f"{case_id}: manifest e split non concordano")
        _window(row)

    # Verifica che i casi V1 non possano cadere fuori dal registro storico.
    for protocol in PROTOCOLS:
        plan_path = root / "data/protocols" / f"{protocol}_cohort_v1.json"
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        if (
            plan.get("protocol") != protocol
            or plan.get("split_file_sha256") != split_sha
            or plan.get("input_manifest_sha256") != manifest_sha
        ):
            raise ValueError(f"Provenienza coorte V1 incoerente: {protocol}")
        pairs = plan.get("pairs")
        if not isinstance(pairs, list) or len(pairs) != 8:
            raise ValueError(f"Coorte V1 non completa: {protocol}")
        observed = {x["case_id"] for x in pairs}
        if len(observed) != 8 or not observed.issubset(historical_seen):
            raise ValueError(f"Registro storico incompleto: {protocol}")

    # A/2 deve essere un inventario realmente eseguito, non un riepilogo
    # riscritto a mano. Verifichiamo anche la selezione originale via seed.
    raw = Path(inventory_path).read_bytes()
    inventory = json.loads(raw.decode("utf-8"))
    if not isinstance(inventory, dict) or any((
        inventory.get("audit") != "network_kpi_inventory_v1",
        inventory.get("selection_seed") != AUDIT_SEED,
        inventory.get("split_sha256") != split_sha,
        inventory.get("manifest_sha256") != manifest_sha,
        inventory.get("read_ground_truth") is not False,
        inventory.get("read_metric_values") is not False,
        inventory.get("gemini_calls") != 0,
    )):
        raise ValueError("Inventario rete A/2 non coerente/GT-free")
    network_windows = inventory.get("selected_windows")
    network_consumed = inventory.get("development_case_ids_now_seen")
    if (
        not isinstance(network_windows, list)
        or len(network_windows) != 4
        or not isinstance(network_consumed, list)
        or len(set(network_consumed)) != len(network_consumed)
    ):
        raise ValueError("Inventario A/2 non contiene le quattro finestre")

    # Reimplementiamo la scelta A/2 senza leggerne il codice al runtime.
    previously_protected = [
        row for row in split.values()
        if row["split"] != "development"
        or row["case_id"] in historical_seen
    ]
    original_candidates = [
        row for row in split.values()
        if row["split"] == "development"
        and row["case_id"] not in historical_seen
        and not any(_overlap(row, other) for other in previously_protected)
    ]
    expected_a2 = []
    for cb in ("cloudbed-1", "cloudbed-2"):
        chosen = []
        for row in sorted(
            (r for r in original_candidates if r["cloudbed"] == cb),
            key=lambda r: (_rank(AUDIT_SEED, r["case_id"]), r["case_id"]),
        ):
            if not any(_overlap(row, old) for old in chosen):
                chosen.append(row)
            if len(chosen) == 2:
                break
        if len(chosen) != 2:
            raise ValueError("Non posso ricostruire la selezione A/2")
        expected_a2.extend(chosen)
    canonical_keys = ("case_id", "cloudbed", "start_unix", "end_unix", "split")
    def canonical(row):
        return tuple(str(row.get(k)) for k in canonical_keys)
    if (
        [canonical(x) for x in network_windows]
        != [canonical(x) for x in expected_a2]
    ):
        raise ValueError("Finestre A/2 non riproducibili dal seed")
    actual_consumed = sorted(
        row["case_id"] for row in split.values()
        if row["split"] == "development"
        and any(_overlap(row, win) for win in expected_a2)
    )
    if sorted(network_consumed) != actual_consumed:
        raise ValueError("Il registro consumato dall'audit A/2 non coincide")

    seen = historical_seen | frozenset(actual_consumed)
    protected = [
        row for row in split.values()
        if row["split"] != "development" or row["case_id"] in seen
    ]
    eligible = [
        row for row in split.values()
        if row["split"] == "development"
        and row["case_id"] not in seen
        and not any(_overlap(row, old) for old in protected)
    ]
    selected = []
    for cb in ("cloudbed-1", "cloudbed-2"):
        picked = []
        for row in sorted(
            (r for r in eligible if r["cloudbed"] == cb),
            key=lambda r: (_rank(SEED, r["case_id"]), r["case_id"]),
        ):
            if not any(_overlap(row, old) for old in picked):
                picked.append(row)
            if len(picked) == per_cloudbed:
                break
        if len(picked) != per_cloudbed:
            raise ValueError(
                f"Finestre development indipendenti insufficienti per {cb}"
            )
        selected.extend(picked)
    if any(
        _overlap(a, b)
        for i, a in enumerate(selected) for b in selected[i + 1:]
    ):
        raise ValueError("La nuova coorte contiene intervalli sovrapposti")
    selected_rows = []
    for row in selected:
        case_id = row["case_id"]
        expected = infer_requested_faults(manifest[case_id]["instruction"])
        if expected is None:
            raise ValueError(f"Cardinalita' task sconosciuta: {case_id}")
        selected_rows.append({
            "case_id": case_id, "cloudbed": row["cloudbed"],
            "start_unix": int(row["start_unix"]),
            "end_unix": int(row["end_unix"]),
            "task_index": manifest[case_id]["task_index"],
            "requested_fault_count": expected,
        })
    return {
        "protocol": PROTOCOL,
        "status": "PROPOSED_NOT_FROZEN_NOT_EXECUTED",
        "seed": SEED,
        "split_sha256": split_sha,
        "manifest_sha256": manifest_sha,
        "network_inventory_sha256": hashlib.sha256(raw).hexdigest(),
        "historical_case_ids": sorted(historical_seen),
        "network_audit_consumed_case_ids": actual_consumed,
        "selected_cases": selected_rows,
        "case_count": len(selected_rows),
        "per_cloudbed": per_cloudbed,
        "variant_order": list(VARIANTS),
        "output_contract_mode": "v2_enforce",
        "replicas_per_case_variant": 1,
        "planned_runs": len(selected_rows) * len(VARIANTS),
        "read_ground_truth": False,
        "read_telemetry": False,
        "read_predictions": False,
        "read_scorer": False,
        "gemini_calls": 0,
        "files_written": False,
        "limitations": [
            "Finestre separate non provano indipendenza causale/statistica.",
            "La selezione e' una PROPOSTA, non preregistrazione firmata.",
            "Nessun risultato su questa coorte e' stato ancora prodotto.",
            "Il registro storico necessita conferma delle altre possibili esplorazioni.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--per-cloudbed", type=int, default=4)
    args = parser.parse_args()
    proposal = propose_v2_cohort(
        args.data_dir, args.inventory, per_cloudbed=args.per_cloudbed,
    )
    print(json.dumps(proposal, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
