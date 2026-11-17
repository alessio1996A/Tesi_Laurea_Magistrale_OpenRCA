"""Inventario dei KPI e preflight di formalizzabilita' di RQ2-K: GT-free e solo offline.

NON e' un rilevatore eseguibile, un congelamento scientifico delle regole, un inventario di
dataset o un runner di provider. Usa solo i nomi dei KPI citati nel codice sorgente esistente,
non la telemetria di discovery/test di RQ2 ne' le etichette dei guasti obiettivo.

- Essere noto nel sorgente non prova la disponibilita' in una specifica finestra del Market.
- Un nome suggestivo non verifica unita' fisiche ne' semantica dei contatori.
- Un JSON K sintatticamente valido non e' un rilevatore implementabile.
- Il preflight non segna mai una regola come eseguibile o pronta per il test.

I riferimenti R01/R06 qui sotto sono nomi di metriche di regole VECCHIE e gia' note, non nuove regole.

Contenuto
---------
- costanti: versione, versione e origine del catalogo, etichetta "semantica candidata";
- `_EXTRA_CODE_REFERENCES`: metriche di regole preesistenti non presenti nel catalogo dei segnali;
- `_json_bytes`, `_digest`, `_add`: JSON canonico, hash e inserimento di un KPI nel catalogo;
- `known_code_kpi_catalog`: l'inventario conservativo dei KPI gia' presenti nel codice RQ1;
- `evaluate_k_formalizability`: controlla una regola candidata K contro quell'inventario.
"""
from __future__ import annotations

import hashlib
import json

from harness.signal_catalog import GAUGE_CONTAINER, GAUGE_NODI
from evaluation.rq2_output_contracts import (
    ContractError, validate_candidate_rule,
)

VERSION = "rq2_kpi_formalizability_preflight_v0"
# Versione e origine del catalogo e valore della semantica di ogni metrica: "candidata, non
# verificata".
CATALOG_VERSION = "rq2_kpi_known_in_code_v0"
CATALOG_ORIGIN = "existing_RQ1_source_only"
CANDIDATE_SEMANTIC = "candidate_not_verified"

# Riferimenti nel codice delle otto regole esistenti, non nomi di etichette obiettivo tenute da
# parte. In particolare, `reads_MB` non va convertito in una velocita' fisica in MB/s.
# Ogni voce: (nome metrica, livello di telemetria, file sorgente).
_EXTRA_CODE_REFERENCES = (
    ("container_cpu_usage_seconds", "container", "src/harness/rules/rule_container_cpu.py"),
    ("container_fs_reads_MB./dev/vda", "container", "src/harness/rules/rule_container_read_io.py"),
    ("container_fs_reads./dev/vda", "container", "src/harness/rules/rule_container_read_io.py"),
)


def _json_bytes(obj: object) -> bytes:
    """Byte UTF-8 della forma canonica JSON di `obj` (chiavi ordinate, senza spazi, NaN vietato)."""
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")


def _digest(obj: object) -> str:
    """SHA-256 (esadecimale) della forma canonica di `obj`."""
    return hashlib.sha256(_json_bytes(obj)).hexdigest()


def _add(
    catalog: dict[str, dict], *, name: str, source: str,
    family: str, location: str,
) -> None:
    """Aggiunge un KPI al `catalog`: nome, livello ("node" o "container"), famiglia e file.

    Tutto cio' che richiede verifica (presenza nel Market, unita' fisica, semantica,
    aggregazioni ammesse) parte come NON verificato. Un nome duplicato o non valido solleva
    `ValueError`.
    """
    if type(name) is not str or not name.strip() or name in catalog:
        raise ValueError("Duplicate or invalid source KPI")
    if source not in ("node", "container"):
        raise ValueError("Unsupported source KPI layer")
    catalog[name] = {
        "metric": name,
        "telemetry_layer": source,
        "tool": (
            "tool_get_node_metrics" if source == "node"
            else "tool_get_container_metrics"
        ),
        "family": family,
        "provenance_source_file": location,
        "presence_status": "known_in_code_only",
        "market_presence_verified": False,
        "physical_unit": None,
        "physical_unit_verified": False,
        "metric_semantics": CANDIDATE_SEMANTIC,
        "metric_semantics_verified": False,
        "allowed_rule_aggregations": [],
        "rule_aggregation_verified": False,
    }


def known_code_kpi_catalog() -> dict:
    """Inventario deterministico e conservativo delle metriche gia' presenti nel codice RQ1.

    Non scansiona `Market.zip`, CSV, ground truth, risultati API o incidenti OOD. Le costanti
    del sorgente esistente non sono un'approvazione automatica delle unita' fisiche.

    Passi: 1) metriche dei nodi e dei container dal catalogo dei segnali; 2) metriche aggiuntive
    delle regole preesistenti; 3) corpo del catalogo (ordinato, con le dichiarazioni "nessun
    accesso a GT/Market") e suo hash.
    """
    catalog: dict[str, dict] = {}
    # 1. Metriche dei nodi, poi dei container, dal catalogo dei segnali (ordinate per nome).
    for metric, (family, _direction) in sorted(GAUGE_NODI.items()):
        _add(
            catalog, name=metric, source="node", family=family,
            location="src/harness/signal_catalog.py",
        )
    for metric, (family, _direction) in sorted(GAUGE_CONTAINER.items()):
        _add(
            catalog, name=metric, source="container", family=family,
            location="src/harness/signal_catalog.py",
        )
    # 2. Metriche citate da regole gia' esistenti ma non nel catalogo dei segnali.
    for metric, source, location in _EXTRA_CODE_REFERENCES:
        _add(
            catalog, name=metric, source=source,
            family="pre_existing_rule_reference", location=location,
        )
    # 3. Corpo del catalogo, in ordine alfabetico, e hash.
    body = {
        "catalog_version": CATALOG_VERSION,
        "origin": CATALOG_ORIGIN,
        "source_code_references_only": True,
        "ground_truth_access": False,
        "reads_market": False,
        "reads_ood_cases": False,
        "physical_units_verified": 0,
        "metric_semantics_verified": 0,
        "can_certify_formalizability": False,
        "metrics": [catalog[name] for name in sorted(catalog)],
    }
    return {**body, "catalog_sha256": _digest(body)}


def evaluate_k_formalizability(
    raw_json: str, *, allowed_evidence_ids: tuple[str, ...],
) -> dict:
    """Controlla una regola candidata K rispetto ai nomi dei KPI noti nel sorgente.

    Ogni candidata per il resto valida richiede comunque una verifica, perche' l'inventario
    attuale del codice NON certifica nessuna unita' fisica ne' semantica. Un futuro
    orchestratore legato al piano dovra' ammettere K solo in discovery: questa funzione NON e'
    una fonte di autorita' sullo stage o sulla fase.

    Argomenti: `raw_json` (risposta K grezza) e `allowed_evidence_ids` (ID di evidenza ammessi).
    Restituisce lo stato ("invalid_contract", "insufficient_evidence" o "requires_verification"),
    i motivi e i conteggi dei segnali dichiarati e riconosciuti, sempre con `ready_for_test` False.

    Passi: 1) catalogo e metadati comuni; 2) validazione del contratto K; 3) se il modello si
    e' astenuto, esito "evidenze insufficienti"; 4) per ogni segnale richiesto: e' nel catalogo?
    presenza nel Market, unita', semantica e aggregazione verificate?; 5) se non c'e' nessun
    motivo, resta quello "congelamento scientifico mancante".
    """
    # 1. Catalogo dei KPI noti e metadati comuni a ogni esito.
    catalog = known_code_kpi_catalog()
    metadata = {
        "preflight_version": VERSION,
        "catalog_sha256": catalog["catalog_sha256"],
        "only_source_code_references": True,
        "read_ground_truth": False,
        "reads_market": False,
        "model_api_calls": 0,
        "files_written": False,
        "rule_executed": False,
        "ready_for_test": False,
        "catalog_frozen_for_science": False,
    }
    # 2. Contratto K: se non e' valido, si esce subito.
    try:
        candidate = validate_candidate_rule(
            raw_json, allowed_evidence_ids=allowed_evidence_ids,
        )
    except ContractError:
        return {
            **metadata,
            "status": "invalid_contract",
            "reasons": ["invalid_k_contract"],
            "declared_signal_count": None,
            "recognized_in_source_count": None,
        }
    # 3. Il modello si e' astenuto dal proporre una regola.
    if candidate["status"] == "insufficient_evidence":
        return {
            **metadata,
            "status": "insufficient_evidence",
            "reasons": ["model_abstained_from_rule"],
            "declared_signal_count": 0,
            "recognized_in_source_count": 0,
        }

    # 4. Ogni segnale richiesto dalla regola viene confrontato con il catalogo.
    known = {item["metric"]: item for item in catalog["metrics"]}
    recognized = 0
    reasons: set[str] = set()
    for signal in candidate["required_signals"]:
        entry = known.get(signal["metric"])
        if entry is None:
            reasons.add("metric_not_in_source_catalog")
            continue
        recognized += 1
        if not entry["market_presence_verified"]:
            reasons.add("market_presence_unverified")
        if not entry["physical_unit_verified"]:
            reasons.add("physical_unit_unverified")
        elif signal["unit"] != entry["physical_unit"]:
            reasons.add("physical_unit_mismatch")
        if not entry["metric_semantics_verified"]:
            reasons.add("metric_semantics_unverified")
        if not entry["rule_aggregation_verified"]:
            reasons.add("aggregation_semantics_unverified")
        elif signal["aggregation"] not in entry["allowed_rule_aggregations"]:
            reasons.add("unsupported_aggregation")

    # 5. Anche senza altri motivi, manca comunque il congelamento scientifico di catalogo e regola.
    if not reasons:
        reasons.add("scientific_catalog_and_rule_freeze_missing")
    return {
        **metadata,
        "status": "requires_verification",
        "reasons": sorted(reasons),
        "declared_signal_count": len(candidate["required_signals"]),
        "recognized_in_source_count": recognized,
    }
