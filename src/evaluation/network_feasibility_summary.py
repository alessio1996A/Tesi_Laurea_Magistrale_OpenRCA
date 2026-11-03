"""Audit A/4 GT-free: riepilogo di fattibilita' DESCRITTIVO da soli JSON A/2 e A/3.

Non legge Market.zip, record.csv, query.csv, labels o output LLM.
Non decide soglie, non classifica guasti e non crea nuove regole.
Lo schema di A/3 conserva solo statistiche: non e' possibile inferire
correlazioni temporali tra segnali o verificare identita' dei guasti.

Esecuzione (dalla radice del progetto, con PYTHONPATH=src):
 python -m evaluation.network_feasibility_summary \
   --inventory /content/network_kpi_inventory_v1.json \
   --profile /content/network_signal_profile_v1.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

from evaluation.network_kpi_inventory import METRIC_SOURCES


FAMILIES = (
    ("R03", "tcp_node_retransmission", "metric_node.csv", (
        "system.net.tcp.retrans_segs", "system.tcp.retrans_pct",
    )),
    ("R03", "tcp_node_context", "metric_node.csv", (
        "system.net.tcp.in_segs", "system.net.tcp.out_segs",
    )),
    ("R04", "container_rx_tx_errors", "metric_container.csv", (
        "container_network_receive_errors.eth0",
        "container_network_transmit_errors.eth0",
    )),
    ("R04", "container_dropped_control", "metric_container.csv", (
        "container_network_receive_packets_dropped.eth0",
        "container_network_transmit_packets_dropped.eth0",
    )),
    ("R04", "node_packet_errors", "metric_node.csv", (
        "system.net.packets_in.error", "system.net.packets_out.error",
    )),
    ("R05", "mesh_request_duration", "metric_mesh.csv", (
        "istio_request_duration_milliseconds.",
    )),
    ("R05", "mesh_request_count_control", "metric_mesh.csv", (
        "istio_requests.",
    )),
)


def _read_json(path: Path) -> tuple[dict, str]:
    data = path.read_bytes()
    parsed = json.loads(data.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError(f"JSON oggetto atteso: {path.name}")
    return parsed, hashlib.sha256(data).hexdigest()


def _nonnegative_int(value: object, field: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"Conteggio non valido: {field}")
    return value


def _numeric(value: object, name: str) -> float | None:
    if value is None:
        return None
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"Numero non valido: {name}")
    return float(value)


def _family(source: str, kpi: str) -> tuple[str, str] | None:
    for rule, family, required_source, patterns in FAMILIES:
        if source == required_source and any(
            kpi == pattern or
            (pattern.endswith(".") and kpi.startswith(pattern))
            for pattern in patterns
        ):
            return rule, family
    return None


def summarize(inventory_path: Path, profile_path: Path) -> dict:
    """Rielabora soltanto profili gia' registrati, senza nuove letture dati."""
    inventory, inventory_hash = _read_json(Path(inventory_path))
    profile, profile_hash = _read_json(Path(profile_path))
    if inventory.get("audit") != "network_kpi_inventory_v1":
        raise ValueError("Inventario A/2 di versione inattesa")
    if profile.get("audit") != "network_signal_profile_v1":
        raise ValueError("Profilo A/3 di versione inattesa")
    if not (
        inventory.get("read_ground_truth") is False
        and inventory.get("read_metric_values") is False
        and inventory.get("gemini_calls") == 0
        and profile.get("ground_truth_read") is False
        and profile.get("classification_performed") is False
        and profile.get("gemini_calls") == 0
    ):
        raise ValueError("Provenienza GT-free o assenza LLM non verificata")
    if profile.get("source_inventory_sha256") != inventory_hash:
        raise ValueError("Hash dell'inventario A/2 diverso da quello usato in A/3")
    windows = inventory.get("selected_windows")
    if not isinstance(windows, list) or not windows:
        raise ValueError("Finestre originali A/2 mancanti")
    if profile.get("selected_windows") != windows:
        raise ValueError("Finestre A/2 e A/3 incoerenti")
    if profile.get("development_case_ids_now_seen") != inventory.get(
        "development_case_ids_now_seen"
    ):
        raise ValueError("Casi development consumati non coerenti")
    cases = set()
    for win in windows:
        if (not isinstance(win, dict) or win.get("split") != "development"
                or win.get("cloudbed") not in ("cloudbed-1", "cloudbed-2")
                or type(win.get("start_unix")) is not int
                or type(win.get("end_unix")) is not int
                or win["start_unix"] >= win["end_unix"]):
            raise ValueError("Finestre A/2 non-development o malformate")
        key = (win["cloudbed"], win.get("case_id"))
        if key in cases:
            raise ValueError("Finestra duplicata")
        cases.add(key)

    raw_profiles = profile.get("profiles")
    if not isinstance(raw_profiles, list) or profile.get("profile_count") != len(raw_profiles):
        raise ValueError("Conteggio profili A/3 incoerente")
    grouped = defaultdict(list)
    seen_keys = set()
    for row in raw_profiles:
        if not isinstance(row, dict):
            raise ValueError("Profilo non valido")
        cb, case_id = row.get("cloudbed"), row.get("case_id")
        source, kpi, cmdb_id = row.get("source"), row.get("kpi_name"), row.get("cmdb_id")
        if (cb, case_id) not in cases or source not in METRIC_SOURCES:
            raise ValueError("Profilo fuori finestre development o sorgente imprevista")
        if not all(isinstance(x, str) and x for x in (kpi, cmdb_id)):
            raise ValueError("Identificativo KPI/componente non valido")
        if (row.get("root_cause_verified") is not False
                or row.get("unit") != "non_verificata"
                or row.get("signal_semantics") != "non_verificata"):
            raise ValueError("Semantica o causa indicata come verificata")
        key = (cb, case_id, source, cmdb_id, kpi)
        if key in seen_keys:
            raise ValueError("Profilo duplicato")
        seen_keys.add(key)
        stats = row.get("statistics")
        if not isinstance(stats, dict):
            raise ValueError("Statistiche non valide")
        rows = _nonnegative_int(stats.get("rows"), "rows")
        numeric_samples = _nonnegative_int(stats.get("numeric_samples"), "numeric_samples")
        missing = _nonnegative_int(
            stats.get("non_numeric_or_non_finite"), "non_numeric_or_non_finite"
        )
        distinct = _nonnegative_int(stats.get("distinct_values"), "distinct_values")
        decreasing = _nonnegative_int(stats.get("decreasing_steps"), "decreasing_steps")
        maximum = _numeric(stats.get("maximum"), "maximum")
        minimum = _numeric(stats.get("minimum"), "minimum")
        p95 = _numeric(stats.get("p95"), "p95")
        if rows != numeric_samples + missing:
            raise ValueError("Numero di campioni incoerente")
        if numeric_samples == 0:
            if any(v is not None for v in (minimum, maximum, p95)) or distinct:
                raise ValueError("Serie senza dati numerici ma con statistiche valorizzate")
        elif (minimum is None or maximum is None or p95 is None
              or minimum > p95 or p95 > maximum or distinct < 1):
            raise ValueError("Statistiche numeriche contraddittorie")
        family = _family(source, kpi)
        if family is None:
            continue
        rule, family_name = family
        grouped[(rule, family_name, cb, source, kpi)].append({
            "case_id": case_id, "component": cmdb_id,
            "rows": rows, "numeric_samples": numeric_samples, "missing": missing,
            "distinct": distinct, "decreasing": decreasing,
            "maximum": maximum, "p95": p95,
        })

    summaries = []
    for (rule, family, cb, source, kpi), records in sorted(grouped.items()):
        valid = [x for x in records if x["numeric_samples"] > 0]
        maxima = [x["maximum"] for x in valid]
        p95s = [x["p95"] for x in valid]
        summaries.append({
            "rule_under_study": rule,
            "family": family,
            "cloudbed": cb,
            "source": source,
            "kpi_name": kpi,
            "profiles": len(records),
            "windows_present": len(set(x["case_id"] for x in records)),
            "components_present": len(set(x["component"] for x in records)),
            "numeric_profiles": len(valid),
            "non_numeric_only_profiles": len(records) - len(valid),
            "positive_max_profiles": sum(x > 0 for x in maxima),
            "all_zero_profiles": sum(x == 0 for x in maxima),
            "varying_numeric_profiles": sum(x["distinct"] > 1 for x in valid),
            "profiles_with_decreases": sum(x["decreasing"] > 0 for x in valid),
            "numeric_samples": sum(x["numeric_samples"] for x in records),
            "non_numeric_samples": sum(x["missing"] for x in records),
            "maximum_across_profiles": max(maxima) if maxima else None,
            "median_of_profile_p95": statistics.median(p95s) if p95s else None,
        })

    return {
        "audit": "network_feasibility_summary_v1",
        "source_inventory_sha256": inventory_hash,
        "source_profile_sha256": profile_hash,
        "source_windows": windows,
        "source_profile_count": len(raw_profiles),
        "group_summary": summaries,
        "read_ground_truth": False,
        "read_market_zip": False,
        "gemini_calls": 0,
        "classification_performed": False,
        "provisional_interpretation": {
            "R03": "Solo proxy a livello node: non implica container target.",
            "R04": "Errori RX/TX, drop e node errors non equivalgono a corruption.",
            "R05": "Durata delle richieste Istio non equivale a sola latenza di rete.",
        },
        "limitations": [
            "Statistiche A/3 aggregate: nessuna correlazione temporale possibile.",
            "Median-of-p95 e massimi mantengono unita' e semantica NON verificate.",
            "Campione development visto: non e' una stima blind di accuratezza.",
            "Il report non propone soglie e non autorizza nuove regole deterministiche.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--profile", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(summarize(args.inventory, args.profile),
                     indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
