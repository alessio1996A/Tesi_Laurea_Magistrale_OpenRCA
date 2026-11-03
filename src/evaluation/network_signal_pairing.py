"""Audit A/5: copertura congiunta di KPI R03/R05 dai soli JSON A/2 e A/3.

Per R03 abbina KPI TCP per cloudbed + finestra + nodo.
Per R05 abbina durata Istio e volume richieste usando ESATTAMENTE
cloudbed + finestra + cmdb_id + suffisso KPI (protocollo/status).
Non usa timestamp di singoli campioni: i profili A/3 sono aggregati.
Quindi NON calcola correlazioni, rapporti tra valori, soglie, anomalie,
latenza di rete pura, attribuzione di root cause o accuracy.

Legge solo due JSON locali; verifica il vincolo SHA-256 e la provenienza
GT-free attraverso network_feasibility_summary.summarize.
Non apre Market.zip, record.csv, query.csv o risultati LLM; zero Gemini.

Da radice del progetto con PYTHONPATH=src:
 python -m evaluation.network_signal_pairing \
   --inventory /content/network_kpi_inventory_v1.json \
   --profile /content/network_signal_profile_v1.json
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from evaluation.network_feasibility_summary import summarize


R03_REQUIRED = frozenset({
    "system.net.tcp.retrans_segs",
    "system.tcp.retrans_pct",
})
R03_CONTEXT = frozenset({
    "system.net.tcp.in_segs",
    "system.net.tcp.out_segs",
})
DURATION = "istio_request_duration_milliseconds."
REQUESTS = "istio_requests."
CLOUDBEDS = ("cloudbed-1", "cloudbed-2")


def _positive(row: dict) -> bool:
    stats = row["statistics"]
    value = stats["maximum"]
    return stats["numeric_samples"] > 0 and value is not None and value > 0


def _available(row: dict) -> bool:
    return row["statistics"]["numeric_samples"] > 0


def _stats(counter: Counter, *, title: str) -> dict:
    result = {"cloudbed": title}
    result.update(dict(sorted(counter.items())))
    return result


def analyze_pairing(inventory_path: Path, profile_path: Path) -> dict:
    """Esegue solo matching tra profili gia' visti, non matching temporale."""
    provenance = summarize(inventory_path, profile_path)
    payload = json.loads(Path(profile_path).read_text(encoding="utf-8"))
    rows = payload["profiles"]

    node = defaultdict(dict)
    mesh = defaultdict(dict)
    for row in rows:
        cb, case, component = row["cloudbed"], row["case_id"], row["cmdb_id"]
        source, kpi = row["source"], row["kpi_name"]
        if source == "metric_node.csv" and kpi in R03_REQUIRED | R03_CONTEXT:
            node[(cb, case, component)][kpi] = row
        elif source == "metric_mesh.csv":
            if kpi.startswith(DURATION):
                suffix = kpi[len(DURATION):]
                kind = "duration"
            elif kpi.startswith(REQUESTS):
                suffix = kpi[len(REQUESTS):]
                kind = "requests"
            else:
                continue
            if not suffix:
                raise ValueError("KPI Istio senza suffisso")
            mesh[(cb, case, component, suffix)][kind] = row

    node_totals = defaultdict(Counter)
    for (cb, _, _), group in node.items():
        totals = node_totals[cb]
        totals["node_component_windows_with_any_r03_kpi"] += 1
        if R03_REQUIRED.issubset(group):
            totals["r03_pairs_present"] += 1
            retrans, pct = (group["system.net.tcp.retrans_segs"],
                            group["system.tcp.retrans_pct"])
            if _available(retrans) and _available(pct):
                totals["r03_pairs_both_numeric"] += 1
                r_positive, p_positive = _positive(retrans), _positive(pct)
                if r_positive and p_positive:
                    totals["r03_pairs_both_positive_max"] += 1
                elif r_positive:
                    totals["r03_pairs_retrans_only_positive_max"] += 1
                elif p_positive:
                    totals["r03_pairs_pct_only_positive_max"] += 1
                else:
                    totals["r03_pairs_both_zero_max"] += 1
            if retrans["statistics"]["distinct_values"] > 1:
                totals["r03_retrans_varying_profiles"] += 1
            if pct["statistics"]["distinct_values"] > 1:
                totals["r03_pct_varying_profiles"] += 1
            if retrans["statistics"]["decreasing_steps"] > 0:
                totals["r03_retrans_decreasing_profiles"] += 1
            if R03_CONTEXT.issubset(group):
                totals["r03_pairs_with_in_and_out_segs"] += 1
        else:
            totals["r03_pairs_incomplete"] += 1

    mesh_totals = defaultdict(Counter)
    for (cb, _, _, _), group in mesh.items():
        totals = mesh_totals[cb]
        duration, requests = group.get("duration"), group.get("requests")
        totals["mesh_component_window_suffixes"] += 1
        if duration is not None and requests is not None:
            totals["matched_duration_request_pairs"] += 1
            if _available(duration) and _available(requests):
                totals["matched_pairs_both_numeric"] += 1
                d_positive, q_positive = _positive(duration), _positive(requests)
                if d_positive and q_positive:
                    totals["matched_pairs_both_positive_max"] += 1
                elif d_positive:
                    totals["matched_pairs_duration_positive_requests_zero_max"] += 1
                elif q_positive:
                    totals["matched_pairs_requests_positive_duration_zero_max"] += 1
                else:
                    totals["matched_pairs_both_zero_max"] += 1
            else:
                totals["matched_pairs_with_non_numeric_profile"] += 1
        elif duration is not None:
            totals["unpaired_duration_profiles"] += 1
            if _positive(duration):
                totals["unpaired_positive_duration_profiles"] += 1
        else:
            totals["unpaired_request_profiles"] += 1
            if _positive(requests):
                totals["unpaired_positive_request_profiles"] += 1

    def render(totals: dict[str, Counter], names: tuple[str, ...]) -> dict:
        aggregate = Counter()
        groups = []
        for cb in names:
            aggregate.update(totals[cb])
            groups.append(_stats(totals[cb], title=cb))
        return {"by_cloudbed": groups, "total": dict(sorted(aggregate.items()))}

    return {
        "audit": "network_signal_pairing_v1",
        "input_inventory_sha256": provenance["source_inventory_sha256"],
        "input_profile_sha256": provenance["source_profile_sha256"],
        "source_profile_count": provenance["source_profile_count"],
        "source_windows": provenance["source_windows"],
        "r03_node_pairing": render(node_totals, CLOUDBEDS),
        "r05_mesh_pairing": render(mesh_totals, CLOUDBEDS),
        "r04_observation": (
            "La precedente fase A/4 ha trovato tutti-zero nei KPI "
            "container error/drop e node packet error osservati; "
            "A/5 non aggiunge nuove evidenze per R04."
        ),
        "read_ground_truth": False,
        "read_market_zip": False,
        "gemini_calls": 0,
        "classification_performed": False,
        "limitations": [
            "Il matching indica coesistenza per componente, finestra e KPI, non allineamento temporale.",
            "La positivita' riguarda il massimo del profilo, non lo stesso timestamp.",
            "R03 resta node-level e non identifica il container root cause.",
            "Le metriche Istio descrivono durata RPC, non sola latenza di rete.",
            "Nessuna soglia, causa o regola R03/R04/R05 e' stata validata.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--profile", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(
        analyze_pairing(args.inventory, args.profile),
        ensure_ascii=False, indent=2, allow_nan=False,
    ))


if __name__ == "__main__":
    main()
