"""OFFLINE fake-provider rehearsal of the *existing* RQ2 stage machinery.

This is NOT a live RCA runner. It only dispatches preloaded Python fixtures
via DeterministicFakeBackend; it never calls LangChain, SDKs, APIs, tools,
run_experiment, telemetry, scorers, or any user-supplied callback.

A strict fixture marker and absence of Market.zip isolate synthetic output
from the original benchmark data. Even with the marker, this is only a
testing safeguard, not a security boundary against malicious tampering.

No automatic retries. A claim with no result is left for manual investigation.
No test phase and no provider/model/financial approval is inferred.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from evaluation.rq2_budget_preflight import CANDIDATE_MODELS
from evaluation.rq2_discovery_claim_journal import RQ2DiscoveryClaimJournal
from evaluation.rq2_discovery_stage_recorder import RQ2DiscoveryStageRecorder
from evaluation.rq2_dryrun_plan import VERSION as PLAN_VERSION

VERSION = "rq2_fake_discovery_driver_v0"
FIXTURE_MARKER = ".rq2_synthetic_fixture_only"
FIXTURE_MARKER_BYTES = b"RQ2_SYNTHETIC_FIXTURE_ONLY_V0\n"


class FakeDriverError(ValueError):
    """Fake-only execution refused; no model call has been attempted."""


class DeterministicFakeBackend:
    """Return each preloaded stage fixture once, with NO network interfaces."""

    def __init__(self, *, replies: dict[str, dict]):
        if type(replies) is not dict or any(
            type(key) is not str or type(value) is not dict
            for key, value in replies.items()
        ):
            raise FakeDriverError("Fake replies must be a stage-id dictionary")
        self._replies = deepcopy(replies)
        self._used: set[str] = set()
        self.requested: list[str] = []

    def get_once(self, *, stage_id: str, stage: str) -> dict:
        if stage_id in self._used:
            raise FakeDriverError("Fake backend fixture already consumed")
        # A missing reply is a simulated interruption; journal claim remains.
        if stage_id not in self._replies:
            raise FakeDriverError("Missing fake stage fixture; manual review")
        reply = deepcopy(self._replies[stage_id])
        fields = {"diagnostic_run"} if stage == "D" else {
            "raw_response", "provider_error"
        }
        if set(reply) != fields:
            raise FakeDriverError("Invalid fake response schema")
        if stage == "D" and type(reply["diagnostic_run"]) is not dict:
            raise FakeDriverError("D fixture must be a run dictionary")
        if stage in ("C", "K") and (
            (reply["raw_response"] is not None and
             type(reply["raw_response"]) is not str)
            or (reply["provider_error"] is not None and
                type(reply["provider_error"]) is not str)
        ):
            raise FakeDriverError("C/K fixture must use string or null")
        self._used.add(stage_id)
        self.requested.append(stage_id)
        return reply


class RQ2FakeDiscoveryDriver:
    """Test claim->record->restart semantics against synthetic files only."""

    def __init__(
        self, *, data_dir: Path, backend: DeterministicFakeBackend,
    ):
        if type(backend) is not DeterministicFakeBackend:
            raise FakeDriverError("Only the deterministic fake backend is allowed")
        self.data_dir = Path(data_dir)
        marker = self.data_dir / FIXTURE_MARKER
        if marker.is_symlink() or not marker.is_file() or (
            marker.read_bytes() != FIXTURE_MARKER_BYTES
        ):
            raise FakeDriverError("Explicit synthetic-only marker is required")
        if (self.data_dir / "Market.zip").exists():
            raise FakeDriverError("Refusing real Market.zip in fake rehearsal")
        self.backend = backend
        # Both objects re-verify the GT-free source/plan. This succeeds on
        # synthetic fixtures ONLY in tests with the source-check entrypoints
        # patched locally. The production preview_market rejects fake hashes.
        self.journal = RQ2DiscoveryClaimJournal(data_dir=self.data_dir)
        self.recorder = RQ2DiscoveryStageRecorder(data_dir=self.data_dir)
        if self.journal.plan_sha != self.recorder.store.plan_sha:
            raise FakeDriverError("Claim and recorder plans differ")

    def run_one(self, *, stage_id: str) -> dict:
        """Consume at most one fake reply AFTER an exclusive stage claim."""
        if type(stage_id) is not str:
            raise FakeDriverError("Non-string stage ID")
        entry = self.journal._entry(stage_id)  # forbids all test stages
        stage = entry["stage"]
        model = CANDIDATE_MODELS[entry["logical_model"]]["model_id"]
        if (
            stage_id != (
                f"{PLAN_VERSION}:{entry['case_id']}:"
                f"{entry['logical_model']}:{entry['harness']}:{stage}"
            )
        ):
            raise FakeDriverError("Stage ID not canonical")

        # If a parent was unsuccessfully recorded, do NOT call the fake
        # provider and do NOT create a provider claim for the child.
        if stage in ("C", "K"):
            dependency = entry["dependencies"][0]
            parent = self.recorder.store.load_discovery_stage(
                stage_id=dependency
            )
            if parent is None:
                raise FakeDriverError("Parent not recorded; never skip stages")
            if parent["status"] != "RECORDED_COMPLETE":
                method = (
                    self.recorder.record_c if stage == "C"
                    else self.recorder.record_k
                )
                record = method(
                    stage_id=stage_id, model_id_proposed=model,
                    raw_response=None, provider_error=None,
                )
                return {
                    "version": VERSION,
                    "stage_id": stage_id,
                    "record_status": record["status"],
                    "fake_model_invoked": False,
                    "can_execute_api": False,
                    "is_scientific_result": False,
                }

        # Durable claim BEFORE any fake backend response. If it has already
        # been claimed and is unresolved after a crash, this raises, not retry.
        self.journal.claim_stage(
            stage_id=stage_id, model_id_proposed=model,
        )
        payload = self.backend.get_once(stage_id=stage_id, stage=stage)
        if stage == "D":
            record = self.recorder.record_d(
                stage_id=stage_id, model_id_proposed=model,
                diagnostic_run=payload["diagnostic_run"],
            )
        elif stage == "C":
            record = self.recorder.record_c(
                stage_id=stage_id, model_id_proposed=model, **payload,
            )
        elif stage == "K":
            record = self.recorder.record_k(
                stage_id=stage_id, model_id_proposed=model, **payload,
            )
        else:
            raise FakeDriverError("Unsupported stage")
        return {
            "version": VERSION,
            "stage_id": stage_id,
            "record_status": record["status"],
            "fake_model_invoked": True,
            "can_execute_api": False,
            "is_scientific_result": False,
        }

    def run_discovery_triplet(
        self, *, case_id: str, logical_model: str, harness: str,
    ) -> dict:
        if any(type(v) is not str for v in (
            case_id, logical_model, harness,
        )):
            raise FakeDriverError("Non-string discovery identity")
        stem = f"{PLAN_VERSION}:{case_id}:{logical_model}:{harness}"
        result = []
        for stage in ("D", "C", "K"):
            result.append(self.run_one(stage_id=stem + ":" + stage))
        return {
            "version": VERSION,
            "status": "SYNTHETIC_REHEARSAL_ONLY",
            "stages": result,
            "restart_audit": self.journal.audit_restart(),
            "model_api_calls": 0,
            "can_execute_api": False,
            "can_execute_test": False,
            "scientific_results_produced": False,
            "financial_cost_cap": None,
        }
