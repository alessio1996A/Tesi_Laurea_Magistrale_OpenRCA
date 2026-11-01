"""Cross-layer structural/temporal RCA evidence inspection (PAVE-inspired v1).

Use *only* node/container labels and observed rule candidates in the
current OpenRCA evidence report. This is not a service dependency graph:
a telemetry identifier like node-5.frontend-0 is evidence of a naming
relationship, not proof of deployment topology or causal propagation.

The verifier makes no LLM calls, reads no labels and does not modify
predictions or the report. It is intentionally NOT connected to the runner.
"""
from __future__ import annotations

import re
from typing import Any

from output.openrca_contract import RootCause
from harness.observational_verifier import verifica_coerenza_osservativa


# Whitelist of classes implemented by the existing, unchanged R01-R11 rules.
# The cross-layer inspection only compares families measured at both levels.
_RULES = {
    "R01": ("container", "cpu", "container CPU load"),
    "R02": ("container", "memory", "container memory load"),
    "R06": ("container", "read_io", "container read I/O load"),
    "R07": ("node", "cpu", "node CPU load"),
    "R08": ("node", "memory", "node memory consumption"),
    "R09": ("node", "read_io", "node disk read I/O consumption"),
    "R10": ("node", "write_io", "node disk write I/O consumption"),
    "R11": ("node", "disk_space", "node disk space consumption"),
}

_NODE = re.compile(r"^node-\d+$")
_CONTAINER = re.compile(r"^(node-\d+)\.(.+)$")


def _normalize_candidates(report: dict, start: int, end: int) -> list[dict]:
    """Fail closed on inconsistent candidate metadata and ordering."""
    rules = report["regole_diagnostiche_v0"]
    source = rules["candidati_riportati"]
    if not isinstance(source, list):
        raise ValueError("Lista candidati non valida")
    normalized = []
    for index, candidate in enumerate(source):
        if not isinstance(candidate, dict):
            raise ValueError(f"Candidato {index} non valido")
        rule = candidate.get("regola")
        if rule not in _RULES:
            raise ValueError(f"Regola sconosciuta: {rule}")
        scope, family, expected_class = _RULES[rule]
        component = candidate.get("componente_telemetria")
        if not isinstance(component, str):
            raise ValueError(f"Candidato {index}: componente mancante")

        if scope == "node":
            if _NODE.fullmatch(component) is None:
                raise ValueError(f"Candidato {index}: nodo malformato")
            host = component
            container = None
        else:
            match = _CONTAINER.fullmatch(component)
            if match is None or not match.group(2).strip():
                raise ValueError(f"Candidato {index}: container non qualificato")
            host, container = match.groups()

        first = candidate.get("timestamp_primo_segnale_unix")
        last = candidate.get("timestamp_ultimo_segnale_unix")
        if (
            candidate.get("classe_candidata") != expected_class
            or type(first) is not int or type(last) is not int
            or not start <= first <= last < end
        ):
            raise ValueError(f"Candidato {index}: classe o finestra incoerente")

        normalized.append({
            "source_index": index,
            "rule": rule,
            "scope": scope,
            "family": family,
            "host": host,
            "container": container,
            "component": component,
            "first": first,
            "last": last,
        })
    return normalized


def _target_hosts(component: str, candidates: list[dict]) -> tuple[list[str], str]:
    """A suffix may refer to several hosts; do not select one arbitrarily."""
    if _NODE.fullmatch(component):
        return [component], "nodo_esplicito"

    qualified = _CONTAINER.fullmatch(component)
    if qualified is not None:
        return [qualified.group(1)], "container_qualificato"

    hosts = sorted({
        c["host"] for c in candidates
        if c["scope"] == "container" and c["container"] == component
    })
    if not hosts:
        return [], "host_non_osservato"
    if len(hosts) > 1:
        return hosts, "host_ambiguo"
    return hosts, "host_da_identificativo_telemetria"


def _classe_ipotesi(reason: str) -> tuple[str, str] | None:
    normalized = " ".join(reason.split()).casefold()
    for scope, family, label in _RULES.values():
        if normalized == label.casefold():
            return scope, family
    return None


def verifica_relazioni_strutturali_temporali(
    root_cause: RootCause,
    evidence_report: dict | None,
    *,
    start_unix: int,
    end_unix: int,
    tolleranza_secondi: int = 60,
) -> dict[str, Any]:
    """Observe cross-layer candidate relations without claiming causation.

    First delegates validation and hypothesis-level matching to v0.
    Then compares explicit host/container candidate pairs of the *same
    monitored resource family*. Signal-order labels describe observations,
    not confirmed propagation or the occurrence time of the root cause.
    """
    base = verifica_coerenza_osservativa(
        root_cause,
        evidence_report,
        start_unix=start_unix,
        end_unix=end_unix,
        tolleranza_secondi=tolleranza_secondi,
    )

    result = {
        "versione": "structural_temporal_verification_v1",
        "verifica_osservativa": base,
        "stato": "non_valutabile",
        "host_candidati": [],
        "origine_host": None,
        "relazioni_cross_layer": [],
        "causa_verificata": False,
        "propagazione_verificata": False,
        "nota": (
            "Le relazioni nodo/container derivano da identificativi di "
            "telemetria e non dimostrano dipendenze applicative o causalita'. "
            "L'ordine dei segnali non determina il momento della causa."
        ),
    }

    if base["stato"] == "fuori_finestra":
        return {**result, "stato": "fuori_finestra"}
    if evidence_report is None or "regole_diagnostiche_v0" not in evidence_report:
        return result

    candidates = _normalize_candidates(evidence_report, start_unix, end_unix)
    hosts, origin = _target_hosts(root_cause.component, candidates)
    result["host_candidati"] = hosts
    result["origine_host"] = origin

    predicted_class = _classe_ipotesi(root_cause.reason)
    if predicted_class is None:
        return {**result, "stato": "classe_non_coperta"}

    claimed_scope, claimed_family = predicted_class
    component_scope = (
        "node" if _NODE.fullmatch(root_cause.component)
        else "container" if (
            _CONTAINER.fullmatch(root_cause.component)
            or re.fullmatch(r".+-\\d+", root_cause.component)
        ) else "sconosciuto"
    )
    result["famiglia_ipotesi"] = claimed_family
    result["livello_ipotesi"] = claimed_scope
    result["livello_componente"] = component_scope
    if component_scope != claimed_scope:
        return {**result, "stato": "livello_non_verificabile"}

    if not hosts:
        return {**result, "stato": "host_non_osservato"}
    if len(hosts) > 1:
        return {**result, "stato": "host_ambiguo"}

    host = hosts[0]
    nodes = [c for c in candidates if c["scope"] == "node" and c["host"] == host]
    containers = [
        c for c in candidates
        if c["scope"] == "container" and c["host"] == host
    ]

    # For a container hypothesis inspect only that container; a host-level
    # hypothesis may inspect all candidate containers on the host.
    if not _NODE.fullmatch(root_cause.component):
        container_name = (
            root_cause.component.split(".", 1)[1]
            if _CONTAINER.fullmatch(root_cause.component)
            else root_cause.component
        )
        containers = [c for c in containers if c["container"] == container_name]

    pairs = []
    for node in nodes:
        for container in containers:
            if (node["family"] != container["family"]
                    or node["family"] != claimed_family):
                continue
            delta = container["first"] - node["first"]
            if abs(delta) <= tolleranza_secondi:
                order = "segnali_quasi_contemporanei"
            elif delta > 0:
                order = "segnale_nodo_precede_container"
            else:
                order = "segnale_container_precede_nodo"
            pairs.append({
                "host": host,
                "container": container["component"],
                "famiglia": node["family"],
                "regola_nodo": node["rule"],
                "regola_container": container["rule"],
                "primo_segnale_nodo_unix": node["first"],
                "primo_segnale_container_unix": container["first"],
                "differenza_secondi_container_meno_nodo": delta,
                "ordine_osservato": order,
                "provenienza": [
                    f"regole_diagnostiche_v0.candidati_riportati[{node['source_index']}]",
                    f"regole_diagnostiche_v0.candidati_riportati[{container['source_index']}]",
                ],
            })

    # Independent of report ordering; no causal ranking is implied.
    pairs.sort(key=lambda p: (
        p["famiglia"], p["container"], p["primo_segnale_nodo_unix"],
        p["primo_segnale_container_unix"], p["regola_nodo"],
    ))
    result["relazioni_cross_layer"] = pairs
    result["stato"] = "relazioni_osservate" if pairs else "nessuna_relazione_osservata"
    return result
