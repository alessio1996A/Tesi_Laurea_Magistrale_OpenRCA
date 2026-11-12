"""GT-free, offline and NON-AUTHORIZING RQ2 model/cost preflight.

The two RQ1 Anthropic IDs and Gemini default are rechecked against the
EXISTING factory/config. No model is instantiated; no network, API, telemetry,
Market data, archive artifacts, user secrets or GT are accessed.

2026-11-12 vendor PAID STANDARD non-cached prices in USD / 1M tokens:
 Anthropic https://platform.claude.com/docs/en/about-claude/pricing
 Google https://ai.google.dev/gemini-api/docs/pricing
 These prices must be reverified immediately before any live campaign.

IMPORTANT:
  - D has multiple LLM requests; its stage-wide tokens are NOT one request.
  - Haiku 5.5's 100k threshold applies to EACH REQUEST'S prompt size,
    including cached tokens, not to the combined D stage token count.
  - Without per-request information, D high-tier pricing yields a conservative
    tariff UPPER BOUND (not an exact estimate or paid budget cap).
  - No automatic retry, caching discount, taxes, currency conversion, free
    tier, or extra services are assumed.
  - 'Budget projection' is NOT approval to pay and cannot release APIs.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, ROUND_UP

from agent.model_factory import ANTHROPIC_MODELS
from evaluation.experiment_config import ExperimentConfig
from evaluation.rq2_dryrun_plan import HARNESSES, MODELS

VERSION = "rq2_budget_preflight_v0"
PRICING_SNAPSHOT_DATE = "2026-11-12"
TOKENS_PER_MTOK = Decimal("1000000")
CENT = Decimal("0.01")
SIX_DECIMALS = Decimal("0.000001")
HAIKU_THRESHOLD = 100_000
CANDIDATE_MODELS = {
    "gemini": {"model_id": "gemini-3.5-flash-lite", "provider": "google"},
    "sonnet": {"model_id": "claude-sonnet-5-5", "provider": "anthropic"},
    "haiku": {"model_id": "claude-haiku-5-5", "provider": "anthropic"},
}
# No prompt caching, batch discounts or free-tier assumptions.
BASE_PAID_USD_PER_MTOK = {
    "gemini": {"input": Decimal("0.30"), "output": Decimal("2.50")},
    "sonnet": {"input": Decimal("2.00"), "output": Decimal("10.00")},
    "haiku": {"input": Decimal("0.10"), "output": Decimal("0.50")},
}
HAIKU_OVER_100K_USD_PER_MTOK = {
    "input": Decimal("0.50"), "output": Decimal("2.50"),
}
STAGES_PER_MODEL = {"D": 30, "C": 30, "K": 8}
SOURCE_URLS = {
    "anthropic": "https://platform.claude.com/docs/en/about-claude/pricing",
    "google": "https://ai.google.dev/gemini-api/docs/pricing",
}


class RQ2BudgetPreflightError(ValueError):
    """Invalid offline projection assumptions or model-factory drift."""


def _token_count(token: object, label: str) -> int:
    if type(token) is not int or token < 0 or token > 10_000_000:
        raise RQ2BudgetPreflightError(
            label + " must be integer in range 0..10,000,000"
        )
    return token


def _usd(amount: Decimal) -> str:
    return str(amount.quantize(SIX_DECIMALS, rounding=ROUND_HALF_UP))


def _price(tokens: int, per_million: Decimal) -> Decimal:
    return Decimal(tokens) * per_million / TOKENS_PER_MTOK


def _prices(model: str, stage: str, input_tokens: int) -> tuple[dict, dict]:
    base = BASE_PAID_USD_PER_MTOK[model]
    if model != "haiku" or input_tokens <= HAIKU_THRESHOLD:
        return base, base
    # C/K are EACH one request: >100k input definitely triggers high tier.
    if stage != "D":
        return HAIKU_OVER_100K_USD_PER_MTOK, HAIKU_OVER_100K_USD_PER_MTOK
    # D may have multiple requests: low remains possible when each prompt is
    # <=100k, while high is a conservative entire-stage tariff bound.
    return base, HAIKU_OVER_100K_USD_PER_MTOK


def validate_existing_model_factory() -> dict:
    """Recognize code-supported RQ1 IDs without making a provider request."""
    ids = {name: v["model_id"] for name, v in CANDIDATE_MODELS.items()}
    if (
        tuple(CANDIDATE_MODELS) != MODELS
        or set(HARNESSES) != {"A1", "A1_8R"}
        or not {ids["sonnet"], ids["haiku"]} <= ANTHROPIC_MODELS
        or ExperimentConfig.__dataclass_fields__["model_name"].default
        != ids["gemini"]
    ):
        raise RQ2BudgetPreflightError("Factory/config candidate model drift")
    return {
        "model_ids_proposed": ids,
        "compatible_with_current_RQ1_factory": True,
        "remote_model_availability_checked": False,
        "versions_scientifically_frozen": False,
        "can_execute_api": False,
        "api_budget_approved": False,
        "model_api_calls": 0,
    }


def estimate_stage_token_cost(
    *, logical_model: str, stage: str,
    input_tokens: int, output_tokens: int,
) -> dict:
    """Price one stage using input/output aggregate (not API call count).

    C and K each represent a single tool-free LLM call. D aggregates several
    LLM calls, so Haiku upper tariff is purposefully conservative. Neither
    bound guarantees a maximum bill if real usage exceeds assumptions.
    """
    if (
        type(logical_model) is not str
        or logical_model not in CANDIDATE_MODELS
        or type(stage) is not str
        or stage not in STAGES_PER_MODEL
    ):
        raise RQ2BudgetPreflightError("Unknown model or logical stage")
    in_tokens = _token_count(input_tokens, "input_tokens")
    out_tokens = _token_count(output_tokens, "output_tokens")
    low_rates, high_rates = _prices(logical_model, stage, in_tokens)
    low = _price(in_tokens, low_rates["input"]) + _price(
        out_tokens, low_rates["output"]
    )
    high = _price(in_tokens, high_rates["input"]) + _price(
        out_tokens, high_rates["output"]
    )
    return {
        "model_id_proposed": CANDIDATE_MODELS[logical_model]["model_id"],
        "logical_model": logical_model,
        "stage": stage,
        "input_tokens_assumed": in_tokens,
        "output_tokens_assumed": out_tokens,
        "minimum_standard_price_usd": _usd(low),
        "conservative_tariff_upper_usd": _usd(high),
        "per_request_Haiku_tier_unknown": (
            logical_model == "haiku" and stage == "D"
            and in_tokens > HAIKU_THRESHOLD
        ),
        "actual_spend_or_authorized_cap": False,
        "can_execute_api": False,
    }


def estimate_campaign_cost(*, per_stage_assumptions: dict) -> dict:
    """Compute a reproducible what-if for all 204 logical stages.

    Assumptions are total input/output tokens PER STAGE, not number of calls.
    For D the caller must include all requests' aggregate usage. For C and K
    estimates are per one tool-free request; output includes thinking tokens
    where billed. This is a mathematical sensitivity scenario, not a pilot.
    """
    if type(per_stage_assumptions) is not dict or (
        set(per_stage_assumptions) != set(STAGES_PER_MODEL)
    ):
        raise RQ2BudgetPreflightError("Require exact D/C/K assumptions")
    validate_existing_model_factory()
    checked = {}
    for stage in STAGES_PER_MODEL:
        stage_inputs = per_stage_assumptions[stage]
        if (
            type(stage_inputs) is not dict
            or set(stage_inputs) != {"input_tokens", "output_tokens"}
        ):
            raise RQ2BudgetPreflightError("Bad stage assumption keys")
        checked[stage] = {
            "input_tokens": _token_count(
                stage_inputs["input_tokens"], stage + " input"
            ),
            "output_tokens": _token_count(
                stage_inputs["output_tokens"], stage + " output"
            ),
        }
    rows = []
    total_low, total_high = Decimal(0), Decimal(0)
    for model in MODELS:
        for stage in STAGES_PER_MODEL:
            input_tokens = checked[stage]["input_tokens"]
            output_tokens = checked[stage]["output_tokens"]
            low_rates, high_rates = _prices(model, stage, input_tokens)
            low = _price(input_tokens, low_rates["input"]) + _price(
                output_tokens, low_rates["output"]
            )
            high = _price(input_tokens, high_rates["input"]) + _price(
                output_tokens, high_rates["output"]
            )
            n = STAGES_PER_MODEL[stage]
            rows.append({
                "model": model, "stage": stage, "planned_stages": n,
                "input_tokens_per_stage_assumed": input_tokens,
                "output_tokens_per_stage_assumed": output_tokens,
                "scenario_cost_lower_usd": _usd(low * n),
                "scenario_cost_conservative_tariff_usd": _usd(high * n),
            })
            total_low += low * n
            total_high += high * n
    return {
        "preflight_version": VERSION,
        "pricing_snapshot_date": PRICING_SNAPSHOT_DATE,
        "pricing_sources": SOURCE_URLS.copy(),
        "source_type": "vendor_paid_standard_rates_no_cache",
        "model_ids_proposed": {
            model: CANDIDATE_MODELS[model]["model_id"] for model in MODELS
        },
        "assumed_tokens_per_stage": checked,
        "stage_counts_by_model": STAGES_PER_MODEL.copy(),
        "total_logical_stages": len(MODELS) * sum(STAGES_PER_MODEL.values()),
        "D_api_calls_count_known": False,
        "per_request_Haiku_tier_available": False,
        "rows": rows,
        "scenario_total_lower_usd": _usd(total_low),
        "scenario_total_conservative_tariff_usd": _usd(total_high),
        "scenario_total_conservative_tariff_rounded_up_usd": str(
            total_high.quantize(CENT, rounding=ROUND_UP)
        ),
        "provider_prices_live_reverified_at_execution": False,
        "cached_tokens_and_extra_fees_included": False,
        "real_usage_observed": False,
        "approved_spending_limit_usd": None,
        "cost_hard_cap_enforced": False,
        "api_budget_approved": False,
        "scientific_protocol_frozen": False,
        "model_versions_frozen": False,
        "can_execute_api": False,
        "model_api_calls": 0,
        "files_written": False,
        "warnings": [
            "This is only a WHAT-IF calculation, not a forecast or a spend cap.",
            "Actual D may have many more LLM calls or tokens than assumptions.",
            "Haiku higher tier is per-request, not per summed D stage.",
            "Output must include billable thinking tokens for Gemini.",
            "Pricing snapshot must be reverified before any API run.",
            "No retry, rate-limit, storage, batch/caching, taxes or FX modeled.",
        ],
    }
