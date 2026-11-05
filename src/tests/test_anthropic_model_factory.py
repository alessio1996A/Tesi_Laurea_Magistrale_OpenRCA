"""Test offline della Model Factory Anthropic.

Nessuna API, chiave reale, dataset o output di esperimenti richiesti.
"""
import os
import sys
import types
import unittest
from unittest.mock import patch, sentinel

from agent.model_factory import crea_modello, ANTHROPIC_MODELS
from evaluation.experiment_config import ExperimentConfig


class TestAnthropicModelFactory(unittest.TestCase):
    def test_models_allowed_by_official_ids(self):
        self.assertEqual(
            ANTHROPIC_MODELS,
            {"claude-sonnet-5-5", "claude-haiku-5-5"},
        )

    @patch("agent.model_factory._crea_modello_anthropic",
           return_value=sentinel.llm)
    def test_provider_normalized_and_routed(self, builder):
        output = crea_modello(" ANTHROPIC ", "claude-sonnet-5-5")
        self.assertIs(output, sentinel.llm)
        builder.assert_called_once_with("claude-sonnet-5-5")

    def test_missing_key_fails_before_import_or_api(self):
        from agent.model_factory import _crea_modello_anthropic
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "ANTHROPIC_API_KEY"):
                _crea_modello_anthropic("claude-haiku-5-5")

    def test_unregistered_model_rejected_even_with_key(self):
        from agent.model_factory import _crea_modello_anthropic
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "dummy-secret"}):
            with self.assertRaisesRegex(ValueError, "non preregistrato"):
                _crea_modello_anthropic("claude-sonnet-4-5")

    def test_both_claude_models_no_retries_no_sampling_params(self):
        for name in sorted(ANTHROPIC_MODELS):
            with self.subTest(model=name):
                constructor_calls = []

                def fake_constructor(**kwargs):
                    constructor_calls.append(kwargs)
                    return sentinel.llm

                fake_module = types.ModuleType("langchain_anthropic")
                fake_module.ChatAnthropic = fake_constructor
                with patch.dict(sys.modules, {"langchain_anthropic": fake_module}):
                    with patch.dict(os.environ, {
                        "ANTHROPIC_API_KEY": "dummy-secret"
                    }):
                        llm = crea_modello("anthropic", name)
                self.assertIs(llm, sentinel.llm)
                self.assertEqual(constructor_calls, [
                    {"model": name, "max_retries": 0}
                ])
                self.assertNotIn("temperature", constructor_calls[0])
                self.assertNotIn("top_p", constructor_calls[0])
                self.assertNotIn("top_k", constructor_calls[0])

    def test_experiment_config_supports_anthropic_without_changing_default(self):
        for name in ANTHROPIC_MODELS:
            cfg = ExperimentConfig(
                variant="A1_8R",
                case_id="cloudbed-1_q005",
                model_provider="anthropic",
                model_name=name,
                variant_scheme="current",
                output_contract_mode="v2_enforce",
            )
            self.assertEqual(cfg.model_provider, "anthropic")
            self.assertEqual(cfg.model_name, name)

        default = ExperimentConfig(variant="A0", case_id="cloudbed-1_q005")
        self.assertEqual(default.model_provider, "google")
        self.assertEqual(default.model_name, "gemini-3.5-flash-lite")


if __name__ == "__main__":
    unittest.main(verbosity=2)
