"""Entrypoint isolato per una SOLA D Sonnet V2 sul discovery q050.

Stato corrente NO_API: EXPECTED_RELEASE_SHA256 del ledger e' None.
Nessun accesso al test OOD/GT, C o K. L'originale run_experiment RQ1
e' chiamato con salva=False e solo durante la chiamata viene sostituito
l'esecutore, non il grafo, per preservare i tool_call_id originali.
"""
from __future__ import annotations

from decimal import Decimal
from importlib import metadata
from pathlib import Path
from unittest.mock import patch

import agent.graph_engine as graph_v1
from agent.rq2_v2_graph_engine import esegui_grafo_rca_v2
from evaluation.experiment_config import ExperimentConfig
from evaluation.experiment_runner import run_experiment
from evaluation.rq2_model_factory import (
    assert_exact_runtime_snapshot, crea_modello_rq2,
)
from evaluation.rq2_provider_policy_source_audit import EXPECTED_COLAB_VERSIONS
from evaluation.rq2_v2_sonnet_pilot_ledger import (
    MODEL_ID, STAGE_ID, RQ2V2SonnetPilotLedger, SonnetPilotBlocked,
)

VERSION = "rq2_v2_sonnet_one_d_driver_v1"
MAX_CALLS = 7
# Prezzi snapshot 2026-11-12, NON cap garantito. Verificare di nuovo
# i listini Anthropic prima di congelare una release live.
INPUT_USD_PER_MTOK = Decimal("2.00")
OUTPUT_USD_PER_MTOK = Decimal("10.00")


class _LimitedInvoker:
    def __init__(self, runnable, meter):
        self.runnable, self.meter = runnable, meter

    def invoke(self, *args, **kwargs):
        return self.meter.invoke_counted(self.runnable, *args, **kwargs)


class _LimitedModel:
    """Conta tutte le invocazioni del grafo, inclusa la finalizzazione."""

    def __init__(self, model, approved_usd_limit):
        self.model = model
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.usage_complete = True
        self.approved_limit = Decimal(str(approved_usd_limit))

    @property
    def observed_cost_usd(self):
        return (
            Decimal(self.input_tokens) * INPUT_USD_PER_MTOK
            + Decimal(self.output_tokens) * OUTPUT_USD_PER_MTOK
        ) / Decimal(1_000_000)

    def invoke_counted(self, runnable, *args, **kwargs):
        # Check prima di OGNI richiesta, senza retry.
        if self.calls >= MAX_CALLS:
            raise SonnetPilotBlocked("Maximum 7 LLM calls reached")
        if self.observed_cost_usd >= self.approved_limit:
            raise SonnetPilotBlocked("Operational spend stop reached")
        self.calls += 1  # Contiamo il tentativo anche se l'HTTP fallisce.
        answer = runnable.invoke(*args, **kwargs)
        usage = getattr(answer, "usage_metadata", None)
        if (
            type(usage) is not dict
            or type(usage.get("input_tokens")) is not int
            or type(usage.get("output_tokens")) is not int
            or usage["input_tokens"] < 0 or usage["output_tokens"] < 0
        ):
            self.usage_complete = False
            raise SonnetPilotBlocked("Missing trustworthy token usage; STOP")
        self.input_tokens += usage["input_tokens"]
        self.output_tokens += usage["output_tokens"]
        # Questo stop NON e' un hard cap USD: la singola risposta puo'
        # avere gia' consumato oltre la soglia prima che sia osservata.
        if self.observed_cost_usd >= self.approved_limit:
            raise SonnetPilotBlocked("Operational spend stop after response")
        return answer

    def bind_tools(self, tools):
        return _LimitedInvoker(self.model.bind_tools(tools), self)

    def invoke(self, *args, **kwargs):
        return self.invoke_counted(self.model, *args, **kwargs)


def run_one_sonnet_v2_pilot_d(
    *, data_dir: Path, repo_dir: Path,
    confirm_paid_api: bool = False,
) -> dict:
    """Una sola D nuova: release fonte/codice/runtime e claim PRIMA dell'API.

    Non chiamare su dati reali finché non sono pubblicati release SHA e
    autorizzazione singola. L'operazione può consumare fino a 7 richieste
    HTTP con timeout 300 secondi ciascuna; non e' un budget USD hard cap.
    """
    if confirm_paid_api is not True:
        raise SonnetPilotBlocked("Explicit paid API confirmation required")
    ledger = RQ2V2SonnetPilotLedger(
        data_dir=Path(data_dir), repo_dir=Path(repo_dir),
    )
    binding, release = ledger._gate()  # fallisce se pin non approvato
    if release["code_commit"] != binding["code_commit"]:
        raise SonnetPilotBlocked("Frozen code HEAD drift")
    if release["runtime_versions"] != EXPECTED_COLAB_VERSIONS:
        raise SonnetPilotBlocked("Release/runtime pin differs from expected SDKs")
    # Verificare runtime locale senza import di client o richiesta provider.
    assert_exact_runtime_snapshot()
    for package, expected in release["runtime_versions"].items():
        if metadata.version(package) != expected:
            raise SonnetPilotBlocked("Runtime dependency drift")
    if ledger.audit_restart()["claim_exists"]:
        raise SonnetPilotBlocked("Pilot already claimed: no retry")
    config = ExperimentConfig(
        variant="A1", case_id="cloudbed-1_q050",
        model_name=MODEL_ID, model_provider="anthropic",
        max_tool_rounds=6, recursion_limit=30,
        variant_scheme="current", output_contract_mode="v2_enforce",
        data_dir=Path(data_dir), repo_dir=Path(repo_dir),
    )
    # Costruzione client prima del claim: NESSUNA chiamata di rete implicita
    # ammessa dal contratto della model factory. Se fallisce, non spende.
    client = crea_modello_rq2("anthropic", MODEL_ID)
    metered_llm = _LimitedModel(client, release["approved_usd_limit"])

    # CHECKPOINT DURABILE. Qualunque errore successivo lascia il claim:
    # mai rollback/riscrittura e nessun retry automatico.
    claim = ledger.claim_stage()
    with patch.object(graph_v1, "esegui_grafo_rca", esegui_grafo_rca_v2):
        result = run_experiment(
            config, llm=metered_llm, verbose=False, salva=False,
        )
    if type(result) is not dict:
        raise SonnetPilotBlocked("Runner output missing; claim unresolved")
    receipt = ledger.record_stage(diagnostic_run=result)
    after = ledger.audit_restart()
    if after["unresolved_claim"] or after["status"] != receipt["status"]:
        raise SonnetPilotBlocked("Post-run readback failed; STOP")
    return {
        "version": VERSION,
        "stage_id": STAGE_ID,
        "claim_sha256": claim["claim_sha256"],
        "record_sha256": receipt["record_sha256"],
        "status": receipt["status"],
        "evidence_bundle_sha256": receipt["evidence_bundle_sha256"],
        "observed_model_requests": metered_llm.calls,
        "input_tokens_observed_by_meter": metered_llm.input_tokens,
        "output_tokens_observed_by_meter": metered_llm.output_tokens,
        "token_usage_complete_by_meter": metered_llm.usage_complete,
        "cost_estimate_usd_not_invoice": str(metered_llm.observed_cost_usd),
        "usd_hard_cap_guaranteed": False,
        "automatic_retry": False,
        "ood_test_locked": True,
        "c_k_executed": False,
    }
