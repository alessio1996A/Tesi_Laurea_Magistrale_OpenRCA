"""Gate RQ2-V2: grafo REALE con modello finto -> D/C/K in journal TEMPORANEO.

Questo file usa i moduli di persistenza V1 SOLO in una fixture sintetica
temporary-directory, con source/plan mock e marker specifico. NON costituisce
un journal V2 per gli esperimenti reali; MAI puntare al Drive della tesi.
Non esegue API, non legge Market/GT/OOD e non altera alcun risultato V1.

L'obiettivo di questo gate e' verificare il vincolo di provenienza e il
blocco delle dipendenze prima di progettare uno store V2 dedicato.
"""
from __future__ import annotations

import json
import unittest

from langchain_core.messages import AIMessage
from langchain_core.tools import tool

from agent.graph_engine import crea_grafo_rca
from agent.rq2_v2_graph_engine import esegui_grafo_rca_v2
from evaluation.rq2_evidence_bundle import build_evidence_bundle
from evaluation.rq2_discovery_claim_journal import (
    RQ2ClaimError, RQ2DiscoveryClaimJournal,
)
from evaluation.rq2_fake_discovery_driver import (
    DeterministicFakeBackend,
    FIXTURE_MARKER, FIXTURE_MARKER_BYTES,
    RQ2FakeDiscoveryDriver,
)
from evaluation.rq2_stage_binding import ALLOWED_TOOLS

import test_rq2_claim_recorder_end_to_end as fixture_module
import test_rq2_output_contracts as output_fixture
import test_rq2_stage_binding as binding_fixture


MODEL = "claude-sonnet-5-5"
TOOL = "tool_get_node_metrics"
USAGE = {"input_tokens": 30, "output_tokens": 10, "total_tokens": 40}
ANSWER = json.dumps({
    "1": {
        "root cause occurrence datetime": "2023-11-15 06:13:20",
        "root cause component": "synthetic-component",
        "root cause reason": "synthetic hypothesis",
    }
})


@tool(TOOL)
def fake_node_metrics(cmdb_id: str) -> str:
    """Restituisce solo una risposta fittizia, senza leggere file."""
    return "synthetic metric for " + cmdb_id


class _FakeModel:
    def __init__(self):
        self.calls = 0

    def bind_tools(self, tools):
        assert [t.name for t in tools] == [TOOL]
        return self

    def invoke(self, messages):
        self.calls += 1
        if self.calls == 1:
            return AIMessage(
                content="",
                tool_calls=[
                    {"name": TOOL, "args": {"cmdb_id": "A"}, "id": "fake-A"},
                    {"name": TOOL, "args": {"cmdb_id": "B"}, "id": "fake-B"},
                ],
                usage_metadata=dict(USAGE),
            )
        if self.calls == 2:
            return AIMessage(content=ANSWER, usage_metadata=dict(USAGE))
        raise AssertionError("Unexpected fake LLM call")


class RQ2V2FakeDCKJournalTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture_module.RQ2ClaimRecorderEndToEndTests(
            methodName="test_three_claims_three_artifacts_and_restart"
        )
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        # La fixture vive in una temporary-directory, non in Drive/Colab.
        self.assertFalse((self.fixture.root / "Market.zip").exists())
        (self.fixture.root / FIXTURE_MARKER).write_bytes(FIXTURE_MARKER_BYTES)

    def _v2_diagnostic(self):
        fake = _FakeModel()
        graph = crea_grafo_rca(
            fake, [fake_node_metrics], "Synthetic test only",
            max_tool_rounds=6,
        )
        execution = esegui_grafo_rca_v2(
            graph, richiesta="Analyze two synthetic observations",
            verbose=False,
        )
        self.assertEqual(fake.calls, 2)
        self.assertIsNone(execution["error"])
        self.assertEqual(execution["raw_response"], ANSWER)
        self.assertEqual(execution["metrics"]["tool_calls"], 2)
        self.assertEqual(execution["metrics"]["llm_calls"], 2)
        self.assertTrue(execution["metrics"]["token_usage_complete"])
        self.assertEqual(
            {event["tool_call_id"] for event in execution["tool_trajectory"]},
            {"fake-A", "fake-B"},
        )
        bundle = build_evidence_bundle(
            execution["tool_trajectory"], allowed_tool_names=ALLOWED_TOOLS
        )
        self.assertEqual(bundle["observations_count"], 2)
        paired = {
            e["tool_call_id"]: (
                e["arguments"]["cmdb_id"], e["observation_text"]
            )
            for e in bundle["evidence"]
        }
        self.assertEqual(paired, {
            "fake-A": ("A", "synthetic metric for A"),
            "fake-B": ("B", "synthetic metric for B"),
        })
        # Metadati di identita' provengono da un piano interamente mock.
        # NON e' un run reale OpenRCA, anche se usa il grafo LangGraph vero.
        return self.fixture.diagnostic(
            raw_response=execution["raw_response"],
            metrics=execution["metrics"],
            tool_trajectory=execution["tool_trajectory"],
        )

    def _backend(self, d):
        return DeterministicFakeBackend(replies={
            self.fixture.sid("D"): {"diagnostic_run": d},
            self.fixture.sid("C"): {
                "raw_response": binding_fixture.cause(),
                "provider_error": None,
            },
            self.fixture.sid("K"): {
                "raw_response": json.dumps(
                    output_fixture.RQ2OutputContractsTests.rule()
                ),
                "provider_error": None,
            },
        })

    def _execute_triplet(self, d):
        backend = self._backend(d)
        driver = RQ2FakeDiscoveryDriver(
            data_dir=self.fixture.root,
            backend=backend,
        )
        summary = driver.run_discovery_triplet(
            case_id=fixture_module.CID,
            logical_model="sonnet",
            harness="A1",
        )
        return driver, backend, summary

    def test_v2_ids_complete_fake_dck_and_survive_restart(self):
        d = self._v2_diagnostic()
        driver, backend, summary = self._execute_triplet(d)
        self.assertEqual(
            [x["record_status"] for x in summary["stages"]],
            ["RECORDED_COMPLETE"] * 3,
        )
        self.assertEqual(
            backend.requested,
            [self.fixture.sid(s) for s in ("D", "C", "K")],
        )
        self.assertFalse(summary["can_execute_api"])
        self.assertFalse(summary["can_execute_test"])
        self.assertFalse(summary["scientific_results_produced"])
        self.assertEqual(summary["model_api_calls"], 0)

        stored_d = driver.recorder.store.load_discovery_stage(
            stage_id=self.fixture.sid("D")
        )
        self.assertEqual(stored_d["status"], "RECORDED_COMPLETE")
        self.assertEqual(
            stored_d["artifact"]["evidence_bundle_sha256"],
            build_evidence_bundle(
                d["tool_trajectory"], allowed_tool_names=ALLOWED_TOOLS
            )["bundle_sha256"],
        )
        c = driver.recorder.store.load_discovery_stage(
            stage_id=self.fixture.sid("C")
        )
        k = driver.recorder.store.load_discovery_stage(
            stage_id=self.fixture.sid("K")
        )
        self.assertEqual(
            c["dependency_record_hashes"],
            {self.fixture.sid("D"): stored_d["record_sha256"]},
        )
        self.assertEqual(
            k["dependency_record_hashes"],
            {self.fixture.sid("C"): c["record_sha256"]},
        )
        self.assertEqual(c["artifact"]["validated_c"]["evidence_ids"], ["E001"])
        self.assertEqual(k["artifact"]["validated_k"]["evidence_ids"], ["E001"])
        self.assertEqual(
            c["artifact"]["bundle_sha256"],
            stored_d["artifact"]["evidence_bundle_sha256"],
        )
        restart = RQ2DiscoveryClaimJournal(
            data_dir=self.fixture.root
        ).audit_restart()
        self.assertEqual(restart["claims"], 3)
        self.assertEqual(restart["finished_with_matching_result"], 3)
        self.assertEqual(restart["unresolved_manual_review"], 0)
        self.assertEqual(restart["result_archive_discovery_count"], 3)

    def test_wrong_v2_result_id_invalid_d_blocks_c_and_k_offline(self):
        d = self._v2_diagnostic()
        for event in d["tool_trajectory"]:
            if event["tipo"] == "tool_result":
                event["tool_call_id"] = "unmatched-id"
                break
        driver, backend, summary = self._execute_triplet(d)
        self.assertEqual(
            [x["record_status"] for x in summary["stages"]],
            ["INVALID_OUTPUT", "BLOCKED_DEPENDENCY", "BLOCKED_DEPENDENCY"],
        )
        self.assertEqual(backend.requested, [self.fixture.sid("D")])
        self.assertEqual(
            [x["fake_model_invoked"] for x in summary["stages"]],
            [True, False, False],
        )
        self.assertEqual(summary["restart_audit"]["claims"], 1)
        self.assertEqual(summary["restart_audit"]["result_archive_discovery_count"], 3)
        self.assertEqual(summary["restart_audit"]["unresolved_manual_review"], 0)
        for stage in ("C", "K"):
            sid = self.fixture.sid(stage)
            self.assertIsNone(driver.journal._read_claim(sid))
            record = driver.recorder.store.load_discovery_stage(stage_id=sid)
            self.assertEqual(record["status"], "BLOCKED_DEPENDENCY")
            self.assertEqual(record["artifact"], {})

    def test_completed_v2_fake_dck_cannot_be_claimed_again(self):
        driver, _, _ = self._execute_triplet(self._v2_diagnostic())
        for stage in ("D", "C", "K"):
            with self.subTest(stage=stage):
                with self.assertRaises(RQ2ClaimError):
                    driver.journal.claim_stage(
                        stage_id=self.fixture.sid(stage),
                        model_id_proposed=MODEL,
                    )
        self.assertEqual(driver.journal.audit_restart()["claims"], 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
