"""Offline C/K LangChain fake transport: no real SDK or RQ2 benchmark.

Core tests use the *real* prepare_bound_c/K (mock draft plan and synthetic
D) and import prior TestCase fixture as a module so unittest does NOT
accidentally collect its tests. Integration test writes to a temp RQ2
journal with fake source verification ONLY inside the fixture class.
"""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

import test_rq2_stage_binding as fixture
import test_rq2_output_contracts as contract_fixture
import test_rq2_claim_recorder_end_to_end as journal_fixture
from evaluation.rq2_stage_binding import (
    prepare_bound_c, prepare_bound_k,
)
from evaluation.rq2_toolfree_fake_transport import (
    PREFREEZE_C_SYSTEM_SHA256, PREFREEZE_K_SYSTEM_SHA256,
    StrictToolFreeFake, SimulatedProviderFailure,
    ToolFreeFakeTransportError, invoke_bound_probe_fake,
)


C_JSON = fixture.cause()
K_JSON = json.dumps(contract_fixture.RQ2OutputContractsTests.rule())
USAGE = {"input_tokens": 500, "output_tokens": 150, "total_tokens": 650}


def fake(text: str = C_JSON, *, usage=True):
    return StrictToolFreeFake(outcome=AIMessage(
        content=text, usage_metadata=USAGE if usage else None,
    ))


class RQ2ToolFreeFakeTransportTests(unittest.TestCase):
    def setUp(self):
        self.c_binding = fixture.make_c()
        self.k_binding = fixture.make_k()

    def test_c_invokes_once_with_real_langchain_system_human_messages(self):
        model = fake()
        result = invoke_bound_probe_fake(binding=self.c_binding, fake_model=model)
        self.assertEqual(result["stage"], "C")
        self.assertEqual(result["raw_response"], C_JSON)
        self.assertEqual(result["fake_invocations"], 1)
        self.assertIsNone(result["provider_error"])
        self.assertEqual(model.calls, 1)
        self.assertEqual(len(model.received_messages), 2)
        self.assertIs(type(model.received_messages[0]), SystemMessage)
        self.assertIs(type(model.received_messages[1]), HumanMessage)

    def test_k_invokes_once_without_tool_or_D_original_answer(self):
        model = fake(K_JSON)
        result = invoke_bound_probe_fake(binding=self.k_binding, fake_model=model)
        self.assertEqual(result["stage"], "K")
        self.assertEqual(result["raw_response"], K_JSON)
        self.assertEqual(result["model_api_calls"], 0)
        self.assertNotIn("SECRET ANCHORING", str(model.received_messages))
        self.assertIn("unverified_model_cause_probe",
                      model.received_messages[1].content)

    def test_C_K_prompt_fingerprints_match_user_verified_prefreeze(self):
        self.assertEqual(
            self.c_binding["underlying_package"]["system_prompt_sha256"],
            PREFREEZE_C_SYSTEM_SHA256,
        )
        self.assertEqual(
            self.k_binding["underlying_package"]["system_prompt_sha256"],
            PREFREEZE_K_SYSTEM_SHA256,
        )
        self.assertNotEqual(PREFREEZE_C_SYSTEM_SHA256,
                            PREFREEZE_K_SYSTEM_SHA256)

    def test_synthetic_usage_is_reported_not_billed(self):
        result = invoke_bound_probe_fake(binding=self.c_binding,
                                         fake_model=fake())
        self.assertEqual(result["usage"]["input_tokens"], 500)
        self.assertEqual(result["usage"]["output_tokens"], 150)
        self.assertEqual(result["usage"]["total_tokens"], 650)
        self.assertTrue(result["usage"]["complete"])
        self.assertFalse(result["actual_usage_billed"])

    def test_missing_usage_does_not_invent_zero_tokens(self):
        result = invoke_bound_probe_fake(binding=self.c_binding,
                                         fake_model=fake(usage=False))
        self.assertFalse(result["usage"]["complete"])
        self.assertIsNone(result["usage"]["input_tokens"])
        self.assertIsNone(result["usage"]["output_tokens"])
        self.assertIsNone(result["usage"]["total_tokens"])

    def test_anthropic_content_blocks_exclude_thinking_and_signatures(self):
        msg = AIMessage(
            content=[
                {"type": "thinking", "thinking": "SENSITIVE FAKE THINKING"},
                {"type": "text", "text": C_JSON},
            ],
            usage_metadata=USAGE,
        )
        obj = StrictToolFreeFake(outcome=msg)
        result = invoke_bound_probe_fake(binding=self.c_binding, fake_model=obj)
        self.assertEqual(result["raw_response"], C_JSON)
        self.assertNotIn("SENSITIVE FAKE THINKING", result["raw_response"])

    def test_fake_provider_exception_retained_without_retry(self):
        obj = StrictToolFreeFake(
            outcome=SimulatedProviderFailure("fake 503 UNAVAILABLE"),
        )
        result = invoke_bound_probe_fake(binding=self.c_binding, fake_model=obj)
        self.assertEqual(result["fake_transport_status"], "FAKE_PROVIDER_ERROR")
        self.assertIn("503", result["provider_error"])
        self.assertIsNone(result["raw_response"])
        self.assertEqual(obj.calls, 1)

    def test_invalid_json_is_returned_raw_for_strict_recorder(self):
        obj = fake("NOT JSON")
        result = invoke_bound_probe_fake(binding=self.c_binding, fake_model=obj)
        self.assertEqual(result["fake_transport_status"], "FAKE_RESPONSE_OBSERVED")
        self.assertEqual(result["raw_response"], "NOT JSON")
        self.assertIsNone(result["provider_error"])

    def test_tool_call_is_prohibited_and_no_second_invoke(self):
        msg = AIMessage(
            content="", tool_calls=[{
                "id": "fake-call-1", "name": "tool_get_node_metrics",
                "args": {},
            }],
            usage_metadata=USAGE,
        )
        obj = StrictToolFreeFake(outcome=msg)
        result = invoke_bound_probe_fake(binding=self.c_binding, fake_model=obj)
        self.assertEqual(result["fake_transport_status"], "FAKE_PROTOCOL_ERROR")
        self.assertIn("Tool request forbidden", result["provider_error"])
        self.assertIsNone(result["raw_response"])
        self.assertEqual(obj.calls, 1)

    def test_empty_text_block_is_not_repaired(self):
        msg = AIMessage(
            content=[{"type": "thinking", "thinking": "fake-only"}],
        )
        result = invoke_bound_probe_fake(
            binding=self.c_binding,
            fake_model=StrictToolFreeFake(outcome=msg),
        )
        self.assertEqual(result["fake_transport_status"], "FAKE_EMPTY_RESPONSE")
        self.assertEqual(result["raw_response"], "")

    def test_untrusted_callable_backend_rejected_before_invocation(self):
        class PotentialProvider:
            def invoke(self, messages):
                raise AssertionError("MUST NOT CALL REAL PROVIDER")

        with self.assertRaisesRegex(ToolFreeFakeTransportError, "StrictToolFreeFake"):
            invoke_bound_probe_fake(binding=self.c_binding,
                                    fake_model=PotentialProvider())

    def test_recomputed_or_mismatched_binding_digest_is_rejected(self):
        changed = dict(self.c_binding)
        changed["stage_id"] = "some-other-stage"
        with self.assertRaisesRegex(ToolFreeFakeTransportError, "integrity"):
            invoke_bound_probe_fake(binding=changed, fake_model=fake())

    def test_wrong_system_prompt_hash_rejected_before_any_call(self):
        import copy
        changed = copy.deepcopy(self.c_binding)
        changed["underlying_package"]["system_prompt_sha256"] = "0" * 64
        from evaluation.rq2_stage_binding import _sha as signed_digest
        package = changed["underlying_package"]
        package["package_sha256"] = signed_digest({
            k: v for k, v in package.items() if k != "package_sha256"
        })
        changed["binding_sha256"] = signed_digest({
            k: v for k, v in changed.items() if k != "binding_sha256"
        })
        model = fake()
        with self.assertRaisesRegex(ToolFreeFakeTransportError, "prompt mismatch"):
            invoke_bound_probe_fake(binding=changed, fake_model=model)
        self.assertEqual(model.calls, 0)

    def test_test_phase_c_refused_even_if_binding_is_well_formed(self):
        p = fixture.make_plan()
        cid = "cloudbed-1_q000"
        bound = prepare_bound_c(
            plan=p, c_stage_id=fixture.stage_id(cid=cid),
            original_instruction=fixture.INSTRUCTION,
            diagnostic_run=fixture.synthetic_d(cid=cid),
        )
        model = fake()
        with self.assertRaisesRegex(ToolFreeFakeTransportError, "phase gate"):
            invoke_bound_probe_fake(binding=bound, fake_model=model)
        self.assertEqual(model.calls, 0)

    def test_c_and_k_use_expected_exact_model_names(self):
        c = invoke_bound_probe_fake(binding=self.c_binding, fake_model=fake())
        k = invoke_bound_probe_fake(binding=self.k_binding,
                                    fake_model=fake(K_JSON))
        self.assertEqual(c["model_id_proposed"], "claude-sonnet-5-5")
        self.assertEqual(k["model_id_proposed"], "claude-sonnet-5-5")
        self.assertFalse(c["can_execute_api"])
        self.assertFalse(k["can_execute_test"])
        self.assertFalse(k["scientific_protocol_frozen"])

    def test_fake_model_cannot_be_reused_for_second_invoke(self):
        obj = fake()
        invoke_bound_probe_fake(binding=self.c_binding, fake_model=obj)
        with self.assertRaises(AssertionError):
            invoke_bound_probe_fake(binding=self.c_binding, fake_model=obj)
        self.assertEqual(obj.calls, 1)

    def test_full_claim_D_fake_C_K_transport_and_store(self):
        # Reuses the already-tested synthetic, source-mocked journal fixture.
        parent = journal_fixture.RQ2ClaimRecorderEndToEndTests(
            methodName="test_three_claims_three_artifacts_and_restart"
        )
        parent.setUp()
        self.addCleanup(parent.doCleanups)
        parent.claim("D")
        parent.d()
        d = parent.recorder.store.load_discovery_stage(stage_id=parent.sid("D"))
        instruction = parent.recorder._instruction(
            parent.recorder.entries[parent.sid("C")]
        )
        bound_c = prepare_bound_c(
            plan=parent.recorder.plan,
            c_stage_id=parent.sid("C"),
            original_instruction=instruction,
            diagnostic_run=d["artifact"]["diagnostic_run"],
        )
        parent.claim("C")
        c_out = invoke_bound_probe_fake(binding=bound_c, fake_model=fake(C_JSON))
        c_record = parent.recorder.record_c(
            stage_id=parent.sid("C"),
            model_id_proposed=parent.MODEL if hasattr(parent, "MODEL")
            else journal_fixture.MODEL,
            raw_response=c_out["raw_response"],
            provider_error=c_out["provider_error"],
        )
        self.assertEqual(c_record["status"], "RECORDED_COMPLETE")
        bound_k = prepare_bound_k(
            plan=parent.recorder.plan,
            k_stage_id=parent.sid("K"),
            original_instruction=instruction,
            diagnostic_run=d["artifact"]["diagnostic_run"],
            prior_c_binding=bound_c,
            cause_raw_json=C_JSON,
        )
        parent.claim("K")
        k_out = invoke_bound_probe_fake(binding=bound_k,
                                        fake_model=fake(K_JSON))
        k_record = parent.recorder.record_k(
            stage_id=parent.sid("K"), model_id_proposed=journal_fixture.MODEL,
            raw_response=k_out["raw_response"],
            provider_error=k_out["provider_error"],
        )
        self.assertEqual(k_record["status"], "RECORDED_COMPLETE")
        audit = parent.journal.audit_restart()
        self.assertEqual(audit["claims"], 3)
        self.assertEqual(audit["finished_with_matching_result"], 3)
        self.assertEqual(audit["unresolved_manual_review"], 0)
        self.assertFalse(audit["can_execute_api"])


if __name__ == "__main__":
    unittest.main()
