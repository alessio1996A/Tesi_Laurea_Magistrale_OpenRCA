"""G2 RQ2-V2 unificata: REALI grafi LangGraph con modelli/tool FAKE.

Attraversa run_experiment INALTERATO con preparazione sintetica isolata.
A0/A1/A1_8R usano esegui_grafo_rca_v2; Planning/PAVE usano il
verify_graph originale, compresi tool ToolNode e planner deterministico.
Per C e K costruisce prompt source-free reali ed esegue un fake tool-free
per verificare estrazione del testo e contratti. NON usa i runner live.

NESSUN Market.zip, GT, scorer, credenziale, API, ledger reale o Drive.
La validita' JSON nelle fixture NON equivale alla qualita' delle regole.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool

import agent.graph_engine as react_graph
import agent.model_factory as model_factory
import evaluation.experiment_runner as runner
import harness.structural_temporal_verifier as st_verifier
from agent.rq2_v2_graph_engine import esegui_grafo_rca_v2
from evaluation.experiment_config import ExperimentConfig
from evaluation.rq2_evidence_bundle import build_evidence_bundle, evidence_ids
from evaluation.rq2_output_contracts import (
    ContractError, validate_candidate_rule, validate_cause_probe,
)
from evaluation.rq2_probe_adapter import (
    ProbeInputError, prepare_candidate_rule, prepare_cause_probe,
)
from evaluation.rq2_v2_sonnet_c_contentblocks_v2 import extract_visible_response
from evaluation.rq2_v2_unified_discovery_plan import (
    DISCOVERY, ENGINES, HARNESSES, MODELS, TEST,
)
from evaluation.rq2_v2_unified_provenance_gate import audit_captured_v2_d
from evaluation.rq2_budget_preflight import CANDIDATE_MODELS
from evaluation.rq2_stage_binding import ALLOWED_TOOLS

# L'identificativo coincide con una discovery soltanto come identita' per
# il gate; NON vengono letti dati o prompt del corrispondente caso reale.
CASE_ID = DISCOVERY[0]
START, END = 1000, 2000
INSTRUCTION = (
    "A wholly synthetic cloud service experienced exactly one failure "
    "during the synthetic observation window."
)
FINAL_JSON = json.dumps({
    "1": {
        "root cause occurrence datetime": "1970-01-01 00:20:00",
        "root cause component": "synthetic-node-5",
        "root cause reason": "synthetic diagnosis not verified",
    },
})
USAGE = {"input_tokens": 30, "output_tokens": 10, "total_tokens": 40}

USED_TOOLS = []


@tool("tool_get_node_metrics")
def fake_node_metrics(
    start_unix: int, end_unix: int, cmdb_id: str = "",
    kpi_name: str = "",
) -> str:
    """Restituisce una osservazione costruita nel test, senza aprire dati."""
    USED_TOOLS.append(("node", cmdb_id))
    return "synthetic node observation for " + cmdb_id


@tool("tool_get_container_metrics")
def fake_container_metrics(
    start_unix: int, end_unix: int, cmdb_id: str = "",
    kpi_name: str = "",
) -> str:
    """Restituisce una osservazione container puramente sintetica."""
    USED_TOOLS.append(("container", cmdb_id))
    return "synthetic container observation for " + cmdb_id


FAKE_TOOLS = [fake_node_metrics, fake_container_metrics]


def fake_evidence_report() -> dict:
    # Shape del planner realmente usata dal runner RQ1: NON e' una
    # ricostruzione del report da Market; e' un fixture deterministico.
    return {
        "versione": "unified_evidence_v2",
        "caso": {"start_unix": START, "end_unix": END},
        "regole_diagnostiche_v0": {
            "versione": "rule_based_A1_R_v1",
            "finestra": {"start_unix": START, "end_unix": END},
            "totale_candidati": 1,
            "candidati_omessi_per_budget": 0,
            "candidati_riportati": [{
                "regola": "R07",
                "componente_telemetria": "synthetic-node-5",
                "classe_candidata": "node CPU load",
                "timestamp_primo_segnale_unix": 1200,
                "timestamp_ultimo_segnale_unix": 1220,
                "evidenze": {},
            }],
        },
    }


def fake_preparation(config: ExperimentConfig) -> dict:
    if (
        config.case_id != CASE_ID or config.canonical_variant not in HARNESSES
        or config.variant_scheme != "current"
    ):
        raise AssertionError("Only the synthetic discovery test case is allowed")
    return {
        "caso": {
            "case_id": CASE_ID,
            "cloudbed": "cloudbed-1",
            "task_index": "task_7",
            "query_index": 32,
            "instruction": INSTRUCTION,
            "start_unix": START,
            "end_unix": END,
        },
        "tools": FAKE_TOOLS,
        "richiesta": "Synthetic RCA request: " + INSTRUCTION,
        "evidence_report": fake_evidence_report(),
        "evidence_sha256": "e" * 64,
        "preprocessing_seconds": 0.0,
    }


def fake_structural_context(*args, **kwargs):
    return {
        "versione": "structural_temporal_context_v1",
        "causa_verificata": False,
        "propagazione_verificata": False,
        "synthetic_only": True,
    }


class FakeDiagnosisLLM:
    """Stessa dinamica di tool calling per tutte le etichette provider.

    Primo round: due call concorrenti con lo stesso nome ma ID distinti.
    Nel planner: un secondo messaggio termina l'esplorazione e lascia
    eseguire il controllo deterministico; poi si chiude la diagnosi.
    """

    def __init__(self, *, planning: bool, final_json: str = FINAL_JSON):
        self.planning = planning
        self.final_json = final_json
        self.exploration_calls = 0
        self.final_calls = 0
        self.bound_names = None
        self.seen_messages = []

    def bind_tools(self, tools):
        self.bound_names = {t.name for t in tools}
        return self

    def invoke(self, messages):
        self.seen_messages.append(messages)
        system = messages[0].content
        if "INVESTIGATION VERIFICATION POLICY" in system:
            self.final_calls += 1
            return AIMessage(content=self.final_json, usage_metadata=dict(USAGE))

        self.exploration_calls += 1
        if self.exploration_calls == 1:
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "tool_get_node_metrics",
                        "args": {
                            "start_unix": START, "end_unix": END,
                            "cmdb_id": "synthetic-node-4",
                        },
                        "id": "synthetic-call-4",
                    },
                    {
                        "name": "tool_get_node_metrics",
                        "args": {
                            "start_unix": START, "end_unix": END,
                            "cmdb_id": "synthetic-node-6",
                        },
                        "id": "synthetic-call-6",
                    },
                ],
                usage_metadata=dict(USAGE),
            )
        if self.exploration_calls == 2:
            return AIMessage(
                content=(
                    "done exploring synthetic observations"
                    if self.planning else self.final_json
                ),
                usage_metadata=dict(USAGE),
            )
        raise AssertionError("Unexpected extra fake LLM invocation")


class FakeToolFreeModel:
    """Restituisce JSON controllato, simulando stringhe o content blocks."""

    def __init__(self, model: str, raw_json: str):
        self.model = model
        self.raw_json = raw_json
        self.calls = 0
        self.messages_seen = None

    def invoke(self, messages):
        assert len(messages) == 2
        assert isinstance(messages[0], SystemMessage)
        assert isinstance(messages[1], HumanMessage)
        self.calls += 1
        self.messages_seen = messages
        if self.model == "gemini":
            content = self.raw_json
        else:
            content = [
                {"type": "thinking", "thinking": "not a source observation"},
                {"type": "text", "text": self.raw_json},
            ]
        return AIMessage(content=content, usage_metadata=dict(USAGE))


def synthetic_c(*, abstain=False):
    return {
        "schema_version": "rq2_cause_probe_v0",
        "decision": "abstain" if abstain else "diagnosis",
        "predicted_fault_type": None if abstain else "synthetic fault hypothesis",
        "predicted_component": None if abstain else "synthetic-node-5",
        "confidence": "unassessed" if abstain else "low",
        "evidence_ids": [] if abstain else ["E001"],
        "alternatives": [] if abstain else ["synthetic unrelated condition"],
        "limitations": ["No independently established causal link"],
    }


def synthetic_k(*, insufficient=False):
    return {
        "schema_version": "rq2_candidate_rule_v0",
        "status": "insufficient_evidence" if insufficient else "candidate",
        "hypothesized_fault_type": (
            None if insufficient else "synthetic fault hypothesis"
        ),
        "rule_name": None if insufficient else "synthetic_candidate",
        "scope": None if insufficient else "synthetic-node-5",
        "evidence_ids": [] if insufficient else ["E001"],
        "required_signals": [] if insufficient else [{
            "metric": "synthetic.metric", "unit": "synthetic-units",
            "aggregation": "max", "window_seconds": 60,
        }],
        "conditions": [] if insufficient else [{
            "metric": "synthetic.metric", "operator": ">",
            "threshold": 1.0, "unit": "synthetic-units",
            "aggregation": "max", "window_seconds": 60,
        }],
        "combination": None if insufficient else "all",
        "abstain_when": ["Missing trustworthy source observation"],
        "counterexamples": ["Unrelated synthetic problem"],
        "limitations": ["Fixture only: no real meaning or validated units"],
        "pseudocode": (
            None if insufficient else "IF synthetic.metric > 1 THEN maybe"
        ),
    }


def fake_toolfree_stage(model: str, package: dict, raw_json: str):
    fake = FakeToolFreeModel(model, raw_json)
    reply = fake.invoke([
        SystemMessage(content=package["messages"][0]["content"]),
        HumanMessage(content=package["messages"][1]["content"]),
    ])
    text, kind, n_text, n_nontext = extract_visible_response(reply.content)
    return text, (kind, n_text, n_nontext), fake


class UnifiedGraphRealExecutionFakeTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        USED_TOOLS.clear()

    def run_d(self, harness: str, model: str, *,
              final_json: str = FINAL_JSON):
        self.assertIn(harness, HARNESSES)
        self.assertIn(model, MODELS)
        model_info = CANDIDATE_MODELS[model]
        config = ExperimentConfig(
            variant=harness,
            case_id=CASE_ID,
            model_name=model_info["model_id"],
            model_provider=model_info["provider"],
            max_tool_rounds=6,
            max_verification_checks=2,
            recursion_limit=30,
            variant_scheme="current",
            output_contract_mode="v2_enforce",
            repo_dir=self.root,
            data_dir=self.root,
        )
        planning = harness in ("A1_8R_Planning", "A1_PAVE")
        fake = FakeDiagnosisLLM(planning=planning, final_json=final_json)
        with (
            patch.object(runner, "prepara_esperimento",
                         side_effect=fake_preparation) as prepare,
            patch.object(model_factory, "crea_modello",
                         side_effect=AssertionError("NO PROVIDER CLIENT")) as factory,
            patch.object(react_graph, "esegui_grafo_rca",
                         esegui_grafo_rca_v2),
            patch.object(st_verifier, "costruisci_contesto_strutturale_temporale",
                         side_effect=fake_structural_context),
        ):
            result = runner.run_experiment(
                config, llm=fake, verbose=False, salva=False,
            )
        prepare.assert_called_once_with(config)
        factory.assert_not_called()
        self.assertEqual(fake.bound_names, {
            "tool_get_node_metrics", "tool_get_container_metrics",
        })
        self.assertFalse((self.root / "Market.zip").exists())
        self.assertFalse((self.root / "data").exists())
        self.assertEqual(list(self.root.iterdir()), [])
        self.assertIsNone(result["error"])
        self.assertEqual(result["output_contract_mode"], "v2_enforce")
        self.assertEqual(result["variant_scheme"], "current")
        self.assertEqual(result["metrics"]["tool_rounds"], 2 if planning else 1)
        self.assertEqual(result["metrics"]["tool_calls"], 3 if planning else 2)
        self.assertEqual(result["metrics"]["llm_calls"], 3 if planning else 2)
        self.assertTrue(result["metrics"]["token_usage_complete"])
        if planning:
            self.assertEqual(result["verification"]["tool_chiamati_dal_planner"], 1)
            self.assertEqual(result["max_verification_checks"], 2)
            self.assertEqual(fake.final_calls, 1)
        else:
            self.assertEqual(fake.final_calls, 0)
        return result

    def test_15_arms_real_graph_toolnode_then_real_c_k_packages(self):
        cases = 0
        for model in MODELS:
            for harness in HARNESSES:
                with self.subTest(model=model, harness=harness):
                    USED_TOOLS.clear()
                    d = self.run_d(harness, model)
                    self.assertEqual(d["json_status"], "valid_json")
                    self.assertEqual(json.loads(d["raw_response"]),
                                     json.loads(FINAL_JSON))
                    self.assertIn(("node", "synthetic-node-4"), USED_TOOLS)
                    self.assertIn(("node", "synthetic-node-6"), USED_TOOLS)
                    if harness in ("A1_8R_Planning", "A1_PAVE"):
                        self.assertIn(("node", "synthetic-node-5"), USED_TOOLS)
                    result = audit_captured_v2_d(
                        run=d, case_id=CASE_ID, model=model, harness=harness,
                    )
                    self.assertEqual(result["d_engine_required"], ENGINES[harness])
                    self.assertEqual(result["tool_result_pairs_matched"],
                                     3 if harness in ("A1_8R_Planning", "A1_PAVE") else 2)

                    bundle = build_evidence_bundle(
                        d["tool_trajectory"], allowed_tool_names=ALLOWED_TOOLS,
                    )
                    self.assertEqual(len(evidence_ids(bundle)),
                                     result["tool_result_pairs_matched"])

                    c_package = prepare_cause_probe(
                        original_instruction=INSTRUCTION, diagnostic_run=d,
                        allowed_tool_names=ALLOWED_TOOLS,
                    )
                    c_json = json.dumps(synthetic_c())
                    c_raw, content_info, c_fake = fake_toolfree_stage(
                        model, c_package, c_json,
                    )
                    self.assertEqual(c_fake.calls, 1)
                    self.assertEqual(content_info[0],
                                     "str" if model == "gemini" else "list")
                    self.assertEqual(
                        validate_cause_probe(c_raw,
                                             allowed_evidence_ids=evidence_ids(bundle)),
                        synthetic_c(),
                    )
                    self.assertNotIn(d["raw_response"],
                                     c_package["messages"][1]["content"])

                    k_package = prepare_candidate_rule(
                        original_instruction=INSTRUCTION, diagnostic_run=d,
                        cause_raw_json=c_raw, phase="discovery",
                        allowed_tool_names=ALLOWED_TOOLS,
                    )
                    k_json = json.dumps(synthetic_k())
                    k_raw, _, k_fake = fake_toolfree_stage(
                        model, k_package, k_json,
                    )
                    self.assertEqual(k_fake.calls, 1)
                    self.assertEqual(
                        validate_candidate_rule(
                            k_raw, allowed_evidence_ids=evidence_ids(bundle),
                        ),
                        synthetic_k(),
                    )
                    self.assertFalse(c_package["ready_for_api"])
                    self.assertFalse(k_package["ready_for_api"])
                    self.assertEqual(c_package["bundle_sha256"],
                                     k_package["bundle_sha256"])
                    self.assertNotIn(d["raw_response"],
                                     k_package["messages"][1]["content"])
                    self.assertFalse(result["can_execute_api"])
                    self.assertFalse(result["can_run_ood_test"])
                    cases += 1
        self.assertEqual(cases, 15)

    def test_planner_tool_origin_retained_from_actual_toolnode(self):
        for harness in ("A1_8R_Planning", "A1_PAVE"):
            with self.subTest(harness=harness):
                d = self.run_d(harness, "gemini")
                b = build_evidence_bundle(
                    d["tool_trajectory"], allowed_tool_names=ALLOWED_TOOLS,
                )
                self.assertEqual(
                    {e["call_origin"] for e in b["evidence"]},
                    {"llm", "planner"},
                )
                planner_ids = [
                    e["tool_call_id"] for e in b["evidence"]
                    if e["call_origin"] == "planner"
                ]
                self.assertEqual(planner_ids, ["planner-check-0"])
                self.assertEqual(d["metrics"]["verification_tool_results"], 1)

    def test_same_named_parallel_calls_map_to_correct_components(self):
        d = self.run_d("A0", "sonnet")
        b = build_evidence_bundle(
            d["tool_trajectory"], allowed_tool_names=ALLOWED_TOOLS,
        )
        mapped = {
            x["tool_call_id"]: (
                x["arguments"]["cmdb_id"], x["observation_text"]
            ) for x in b["evidence"]
        }
        self.assertEqual(mapped, {
            "synthetic-call-4": (
                "synthetic-node-4",
                "synthetic node observation for synthetic-node-4",
            ),
            "synthetic-call-6": (
                "synthetic-node-6",
                "synthetic node observation for synthetic-node-6",
            ),
        })

    def test_no_real_case_or_ood_data_is_read(self):
        with patch.object(runner, "carica_caso",
                          side_effect=AssertionError("NO REAL MANIFEST")), \
             patch.object(runner, "carica_metriche",
                          side_effect=AssertionError("NO REAL METRICS")):
            self.run_d("A1", "gemini")
            self.run_d("A1_PAVE", "haiku")
        self.assertNotIn(TEST[0], [CASE_ID])
        self.assertEqual(list(self.root.iterdir()), [])

    def test_invalid_d_json_is_not_repaired_by_v2_provenance(self):
        d = self.run_d("A0", "gemini", final_json="not valid json")
        self.assertTrue(d["json_status"].startswith("invalid_v2_task_output"))
        self.assertIsNone(d["prediction"])
        self.assertEqual(d["raw_response"], "not valid json")
        evidence = audit_captured_v2_d(
            run=d, case_id=CASE_ID, model="gemini", harness="A0",
        )
        self.assertEqual(evidence["tool_result_pairs_matched"], 2)
        self.assertFalse(evidence["scientific_release_frozen"])

    def test_invalid_c_reference_prevents_k_package(self):
        d = self.run_d("A1_8R", "haiku")
        invalid_c = synthetic_c()
        invalid_c["evidence_ids"] = ["E999"]
        with self.assertRaisesRegex(ProbeInputError, "Invalid C response"):
            prepare_candidate_rule(
                original_instruction=INSTRUCTION, diagnostic_run=d,
                cause_raw_json=json.dumps(invalid_c), phase="discovery",
                allowed_tool_names=ALLOWED_TOOLS,
            )

    def test_c_abstention_and_k_insufficient_are_valid_results(self):
        d = self.run_d("A1_8R_Planning", "sonnet")
        b = build_evidence_bundle(
            d["tool_trajectory"], allowed_tool_names=ALLOWED_TOOLS,
        )
        c_package = prepare_cause_probe(
            original_instruction=INSTRUCTION, diagnostic_run=d,
            allowed_tool_names=ALLOWED_TOOLS,
        )
        raw_c, _, _ = fake_toolfree_stage(
            "sonnet", c_package, json.dumps(synthetic_c(abstain=True)),
        )
        self.assertEqual(
            validate_cause_probe(
                raw_c, allowed_evidence_ids=evidence_ids(b),
            )["decision"],
            "abstain",
        )
        k_package = prepare_candidate_rule(
            original_instruction=INSTRUCTION, diagnostic_run=d,
            cause_raw_json=raw_c, phase="discovery",
            allowed_tool_names=ALLOWED_TOOLS,
        )
        raw_k, _, _ = fake_toolfree_stage(
            "sonnet", k_package, json.dumps(synthetic_k(insufficient=True)),
        )
        self.assertEqual(
            validate_candidate_rule(
                raw_k, allowed_evidence_ids=evidence_ids(b),
            )["status"],
            "insufficient_evidence",
        )

    def test_k_package_forbids_ood_phase(self):
        d = self.run_d("A1", "gemini")
        with self.assertRaisesRegex(ProbeInputError, "forbidden"):
            prepare_candidate_rule(
                original_instruction=INSTRUCTION, diagnostic_run=d,
                cause_raw_json=json.dumps(synthetic_c()),
                phase="test", allowed_tool_names=ALLOWED_TOOLS,
            )

    def test_content_block_extraction_drops_reasoning_and_invalid_empty(self):
        fake = FakeToolFreeModel("sonnet", json.dumps(synthetic_c()))
        reply = fake.invoke([
            SystemMessage(content="Synthetic C system prompt"),
            HumanMessage(content="Synthetic C evidence"),
        ])
        text, kind, ntext, n_other = extract_visible_response(reply.content)
        self.assertEqual(kind, "list")
        self.assertEqual((ntext, n_other), (1, 1))
        self.assertNotIn("not a source observation", text)
        empty, kind, _, _ = extract_visible_response([
            {"type": "thinking", "thinking": "not a JSON answer"},
        ])
        self.assertEqual(kind, "list")
        self.assertEqual(empty, "")
        with self.assertRaises(ContractError):
            validate_cause_probe(empty, allowed_evidence_ids={"E001"})


if __name__ == "__main__":
    unittest.main()
