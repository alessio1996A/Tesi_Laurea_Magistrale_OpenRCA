"""Preflight RQ2 di modelli e costi: GT-free, offline e NON AUTORIZZANTE.

I due ID Anthropic di RQ1 e il modello Gemini predefinito si ricontrollano rispetto alla
factory/configurazione ESISTENTI. Nessun modello viene istanziato; non si accede a rete, API,
telemetria, dati Market, artefatti d'archivio, segreti dell'utente o ground truth.

Prezzi del 2026-11-12, tariffa STANDARD A PAGAMENTO senza cache, in USD per 1 milione di token:
 Anthropic https://platform.claude.com/docs/en/about-claude/pricing
 Google https://ai.google.dev/gemini-api/docs/pricing
 Questi prezzi vanno riverificati subito prima di qualsiasi campagna live.

IMPORTANTE:
  - D fa piu' richieste al LLM: i token dell'intero stage NON sono una sola richiesta.
  - La soglia di 100k di Haiku 5.5 vale per la dimensione del prompt di OGNI RICHIESTA,
    token in cache compresi, non per il totale dei token dello stage D.
  - Senza informazioni per richiesta, il prezzo della fascia alta per D da' un LIMITE
    SUPERIORE prudenziale di tariffa (non una stima esatta ne' un tetto di spesa).
  - Non si assumono ritenti automatici, sconti per cache, tasse, conversioni di valuta,
    fascia gratuita o servizi extra.
  - La "proiezione di budget" NON e' un'approvazione a pagare e non puo' sbloccare le API.

Contenuto
---------
- costanti: prezzi per modello, soglia di Haiku, modelli candidati, stage per modello (D 30,
  C 30, K 8, cioe' 68 per modello e 204 in totale);
- `RQ2BudgetPreflightError`: errore "ipotesi non valide o factory cambiata";
- `_token_count`, `_usd`, `_price`, `_prices`: validazione dei token, formato del prezzo,
  costo di un numero di token e scelta delle tariffe (bassa e alta);
- `validate_existing_model_factory`: i modelli proposti sono riconosciuti dal codice RQ1;
- `estimate_stage_token_cost`: costo di un singolo stage;
- `estimate_campaign_cost`: scenario "e se" per tutti i 204 stage logici.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, ROUND_UP

from agent.model_factory import ANTHROPIC_MODELS
from evaluation.experiment_config import ExperimentConfig
from evaluation.rq2_dryrun_plan import HARNESSES, MODELS

VERSION = "rq2_budget_preflight_v0"
# Data a cui si riferiscono i prezzi sotto.
PRICING_SNAPSHOT_DATE = "2026-11-12"
# Un milione di token (unita' di misura dei prezzi), un centesimo e la precisione di 6 decimali.
TOKENS_PER_MTOK = Decimal("1000000")
CENT = Decimal("0.01")
SIX_DECIMALS = Decimal("0.000001")
# Oltre questa dimensione del prompt di una richiesta Haiku passa alla fascia di prezzo alta.
HAIKU_THRESHOLD = 100_000
# Modelli candidati: nome logico -> identificativo del modello e provider.
CANDIDATE_MODELS = {
    "gemini": {"model_id": "gemini-3.5-flash-lite", "provider": "google"},
    "sonnet": {"model_id": "claude-sonnet-5-5", "provider": "anthropic"},
    "haiku": {"model_id": "claude-haiku-5-5", "provider": "anthropic"},
}
# Prezzi base in USD per milione di token (ingresso e uscita), senza cache, sconti per batch
# o fascia gratuita.
BASE_PAID_USD_PER_MTOK = {
    "gemini": {"input": Decimal("0.30"), "output": Decimal("2.50")},
    "sonnet": {"input": Decimal("2.00"), "output": Decimal("10.00")},
    "haiku": {"input": Decimal("0.10"), "output": Decimal("0.50")},
}
# Prezzi di Haiku quando il prompt della richiesta supera i 100k token.
HAIKU_OVER_100K_USD_PER_MTOK = {
    "input": Decimal("0.50"), "output": Decimal("2.50"),
}
# Numero di stage di ciascun tipo previsti per ogni modello.
STAGES_PER_MODEL = {"D": 30, "C": 30, "K": 8}
# Pagine ufficiali dei prezzi, da cui provengono i valori sopra.
SOURCE_URLS = {
    "anthropic": "https://platform.claude.com/docs/en/about-claude/pricing",
    "google": "https://ai.google.dev/gemini-api/docs/pricing",
}


class RQ2BudgetPreflightError(ValueError):
    """Ipotesi di proiezione offline non valide, oppure factory dei modelli cambiata."""


def _token_count(token: object, label: str) -> int:
    """Restituisce `token` se e' un intero fra 0 e 10.000.000; altrimenti solleva l'errore.

    `label` e' il nome da mostrare nel messaggio (ad esempio "input_tokens").
    """
    if type(token) is not int or token < 0 or token > 10_000_000:
        raise RQ2BudgetPreflightError(
            label + " must be integer in range 0..10,000,000"
        )
    return token


def _usd(amount: Decimal) -> str:
    """Importo in dollari come testo, arrotondato a 6 decimali (mezzo verso l'alto)."""
    return str(amount.quantize(SIX_DECIMALS, rounding=ROUND_HALF_UP))


def _price(tokens: int, per_million: Decimal) -> Decimal:
    """Costo di `tokens` token, dato il prezzo `per_million` per milione di token."""
    return Decimal(tokens) * per_million / TOKENS_PER_MTOK


def _prices(model: str, stage: str, input_tokens: int) -> tuple[dict, dict]:
    """Tariffe `(bassa, alta)` per modello, stage e token di ingresso.

    Per tutti i modelli tranne Haiku, e per Haiku sotto soglia, le due tariffe coincidono.
    Sopra soglia: per C e K (una sola richiesta) la fascia alta e' certa; per D (piu' richieste)
    la bassa resta possibile e l'alta e' un limite prudenziale sull'intero stage.
    """
    base = BASE_PAID_USD_PER_MTOK[model]
    if model != "haiku" or input_tokens <= HAIKU_THRESHOLD:
        return base, base
    # C e K sono ciascuno UNA richiesta: oltre 100k token di ingresso la fascia alta scatta di certo.
    if stage != "D":
        return HAIKU_OVER_100K_USD_PER_MTOK, HAIKU_OVER_100K_USD_PER_MTOK
    # D puo' avere piu' richieste: la tariffa bassa resta possibile se ogni prompt e' <= 100k,
    # mentre l'alta e' un limite prudenziale di tariffa sull'intero stage.
    return base, HAIKU_OVER_100K_USD_PER_MTOK


def validate_existing_model_factory() -> dict:
    """Riconosce gli ID di modello supportati dal codice RQ1, senza chiamare nessun provider.

    Controlla che i tre modelli candidati, i due harness e i modelli Anthropic noti alla factory
    coincidano con quelli attesi, e che il default Gemini sia quello della configurazione.
    Restituisce gli ID proposti con le dichiarazioni "nessuna API, budget non approvato".
    """
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
    """Prezzo di un solo stage, dai token aggregati di ingresso e uscita (non dal numero di chiamate).

    C e K rappresentano ciascuno una sola chiamata al LLM, senza tool. D aggrega piu'
    chiamate, quindi la tariffa alta di Haiku e' volutamente prudenziale. Nessuno dei due limiti
    garantisce una fattura massima se l'uso reale supera le ipotesi.

    Argomenti (per nome): `logical_model` ("gemini", "sonnet" o "haiku"), `stage` ("D", "C"
    o "K"), `input_tokens` e `output_tokens` (interi). Restituisce il costo minimo a tariffa
    standard e il limite superiore prudenziale, in dollari come testo.
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
    """Calcola uno scenario "e se" riproducibile per tutti i 204 stage logici.

    Le ipotesi sono i token totali di ingresso/uscita PER STAGE, non il numero di chiamate.
    Per D il chiamante deve includere l'uso aggregato di tutte le richieste. Per C e K le
    stime riguardano una sola richiesta senza tool; l'uscita comprende i token di ragionamento
    dove vengono fatturati. E' uno scenario matematico di sensibilita', non un pilot.

    Argomento (per nome): `per_stage_assumptions`, dizionario con le chiavi "D", "C" e "K",
    ciascuna con `input_tokens` e `output_tokens`. Restituisce righe per modello e stage, i
    totali (minimo e prudenziale) e le dichiarazioni "nessuna API, nessun tetto di spesa".

    Passi: 1) ipotesi esatte per D/C/K; 2) la factory dei modelli e' coerente; 3) token validi
    per ogni stage; 4) per ogni modello e stage: costo per stage e costo moltiplicato per il
    numero di stage previsti; 5) somma dei totali e assemblaggio del risultato.
    """
    # 1. Le ipotesi devono riguardare esattamente gli stage D, C e K.
    if type(per_stage_assumptions) is not dict or (
        set(per_stage_assumptions) != set(STAGES_PER_MODEL)
    ):
        raise RQ2BudgetPreflightError("Require exact D/C/K assumptions")
    # 2. I modelli candidati devono essere ancora quelli noti al codice RQ1.
    validate_existing_model_factory()
    # 3. Token validi per ogni stage.
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
    # 4. Costo per ogni coppia (modello, stage), moltiplicato per gli stage previsti.
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
    # 5. Risultato: tutto cio' che e' "approvato", "eseguibile" o "scritto" resta False o zero.
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
