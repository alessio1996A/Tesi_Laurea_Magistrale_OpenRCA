"""Synthetic-only model/cost estimates. No provider calls, Market or GT."""
import copy
import unittest
from unittest.mock import patch

import evaluation.rq2_budget_preflight as budget


def assumptions():
    # Illustrative, NOT measured RQ2 token usage or an actual API budget.
    return {
        "D": {"input_tokens": 150_000, "output_tokens": 4000},
        "C": {"input_tokens": 8000, "output_tokens": 600},
        "K": {"input_tokens": 10_000, "output_tokens": 900},
    }


class RQ2BudgetPreflightTests(unittest.TestCase):
    def test_existing_model_ids_match_RQ1_factory(self):
        x = budget.validate_existing_model_factory()
        self.assertEqual(x["model_ids_proposed"], {
            "gemini": "gemini-3.5-flash-lite",
            "sonnet": "claude-sonnet-5-5",
            "haiku": "claude-haiku-5-5",
        })
        self.assertTrue(x["compatible_with_current_RQ1_factory"])
        self.assertFalse(x["remote_model_availability_checked"])
        self.assertFalse(x["can_execute_api"])

    def test_detects_factory_model_drift(self):
        with patch.object(budget, "ANTHROPIC_MODELS", frozenset()):
            with self.assertRaisesRegex(budget.RQ2BudgetPreflightError, "drift"):
                budget.validate_existing_model_factory()

    def test_sonnet_input_output_paid_cost(self):
        x = budget.estimate_stage_token_cost(
            logical_model="sonnet", stage="D",
            input_tokens=100_000, output_tokens=3000,
        )
        self.assertEqual(x["minimum_standard_price_usd"], "0.230000")
        self.assertEqual(x["conservative_tariff_upper_usd"], "0.230000")

    def test_gemini_thinking_output_paid_price(self):
        x = budget.estimate_stage_token_cost(
            logical_model="gemini", stage="C",
            input_tokens=10_000, output_tokens=1000,
        )
        self.assertEqual(x["minimum_standard_price_usd"], "0.005500")
        self.assertFalse(x["actual_spend_or_authorized_cap"])

    def test_haiku_exact_100k_boundary_low_tier(self):
        x = budget.estimate_stage_token_cost(
            logical_model="haiku", stage="D",
            input_tokens=100_000, output_tokens=1000,
        )
        self.assertEqual(x["minimum_standard_price_usd"], "0.010500")
        self.assertEqual(x["conservative_tariff_upper_usd"], "0.010500")

    def test_haiku_multicall_D_150k_stage_has_tariff_range(self):
        x = budget.estimate_stage_token_cost(
            logical_model="haiku", stage="D",
            input_tokens=150_000, output_tokens=4000,
        )
        self.assertEqual(x["minimum_standard_price_usd"], "0.017000")
        self.assertEqual(x["conservative_tariff_upper_usd"], "0.085000")
        self.assertTrue(x["per_request_Haiku_tier_unknown"])

    def test_haiku_single_C_over_100k_must_use_high_tier(self):
        x = budget.estimate_stage_token_cost(
            logical_model="haiku", stage="C",
            input_tokens=100_001, output_tokens=1000,
        )
        self.assertEqual(x["minimum_standard_price_usd"], "0.052501")
        self.assertEqual(x["conservative_tariff_upper_usd"], "0.052501")
        self.assertFalse(x["per_request_Haiku_tier_unknown"])

    def test_haiku_single_K_under_100k_uses_low_tier(self):
        x = budget.estimate_stage_token_cost(
            logical_model="haiku", stage="K",
            input_tokens=99_999, output_tokens=1000,
        )
        self.assertEqual(x["minimum_standard_price_usd"], "0.010500")

    def test_projection_counts_exact_204_logical_stages(self):
        x = budget.estimate_campaign_cost(per_stage_assumptions=assumptions())
        self.assertEqual(x["total_logical_stages"], 204)
        self.assertEqual(x["stage_counts_by_model"], {"D":30, "C":30, "K":8})
        self.assertEqual(len(x["rows"]), 9)
        self.assertFalse(x["D_api_calls_count_known"])
        self.assertFalse(x["per_request_Haiku_tier_available"])

    def test_projection_is_deterministic(self):
        a = budget.estimate_campaign_cost(per_stage_assumptions=assumptions())
        b = budget.estimate_campaign_cost(per_stage_assumptions=assumptions())
        self.assertEqual(a, b)
        self.assertFalse(a["real_usage_observed"])
        self.assertIsNone(a["approved_spending_limit_usd"])
        self.assertFalse(a["cost_hard_cap_enforced"])
        self.assertFalse(a["api_budget_approved"])
        self.assertFalse(a["can_execute_api"])
        self.assertEqual(a["model_api_calls"], 0)
        self.assertFalse(a["files_written"])

    def test_projection_cost_range_high_not_lower(self):
        x = budget.estimate_campaign_cost(per_stage_assumptions=assumptions())
        self.assertGreaterEqual(
            float(x["scenario_total_conservative_tariff_usd"]),
            float(x["scenario_total_lower_usd"]),
        )
        haiku_d = next(
            r for r in x["rows"] if r["model"] == "haiku" and r["stage"] == "D"
        )
        self.assertGreater(
            float(haiku_d["scenario_cost_conservative_tariff_usd"]),
            float(haiku_d["scenario_cost_lower_usd"]),
        )

    def test_false_precision_about_api_calls_is_not_reported(self):
        x = budget.estimate_campaign_cost(per_stage_assumptions=assumptions())
        self.assertEqual(x["source_type"], "vendor_paid_standard_rates_no_cache")
        self.assertFalse(x["provider_prices_live_reverified_at_execution"])
        self.assertFalse(x["real_usage_observed"])
        self.assertTrue(any("WHAT-IF" in t for t in x["warnings"]))

    def test_wrong_stage_or_model_is_rejected(self):
        for changes in ({"logical_model": "opus"}, {"stage":"X"}):
            with self.subTest(changes=changes):
                args = dict(
                    logical_model="sonnet", stage="D",
                    input_tokens=10, output_tokens=20,
                )
                args.update(changes)
                with self.assertRaises(budget.RQ2BudgetPreflightError):
                    budget.estimate_stage_token_cost(**args)

    def test_invalid_numeric_inputs_rejected(self):
        for n in (-1, 1.2, True, "100", None, 10_000_001):
            with self.subTest(n=n):
                with self.assertRaises(budget.RQ2BudgetPreflightError):
                    budget.estimate_stage_token_cost(
                        logical_model="gemini", stage="C",
                        input_tokens=n, output_tokens=10,
                    )

    def test_incomplete_scenario_is_refused(self):
        for payload in (
            {},
            {"D": {"input_tokens":1, "output_tokens":2}},
            {"D":{}, "C":{}, "K":{}},
            {"D": {"input_tokens":1, "output_tokens":2},
             "C": {"input_tokens":1, "output_tokens":2},
             "K": {"input_tokens":1, "output_tokens":2, "retry": 2}},
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(budget.RQ2BudgetPreflightError):
                    budget.estimate_campaign_cost(
                        per_stage_assumptions=payload,
                    )

    def test_no_provider_client_created(self):
        # A calculation must not call a model factory, even when patched.
        import agent.model_factory as factory
        with patch.object(factory, "crea_modello",
                          side_effect=AssertionError("NO PROVIDER")):
            x = budget.estimate_campaign_cost(
                per_stage_assumptions=assumptions(),
            )
        self.assertEqual(x["model_api_calls"], 0)


if __name__ == "__main__":
    unittest.main()
