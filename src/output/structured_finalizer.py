"""Finalizzazione OpenRCA strutturata, indipendente dal provider.

Una chiamata LLM aggiuntiva usa l'interfaccia LangChain
`with_structured_output`. Il testo originale rimane immutato.

Il modulo e' *extractive*: i valori delle diagnosi strutturate devono
essere presenti letteralmente nella risposta grezza. Non e' una verifica
causale ne' una correzione del guasto. Non consulta ground truth.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from output.openrca_contract import (
    Diagnosis,
    RootCause,
    OutputContractError,
    parse_openrca_json,
    serialize_openrca_json,
)


class StructuredOutputError(ValueError):
    """Finalizzazione strutturata fallita, senza fallback nascosti."""


class StructuredFault(BaseModel):
    occurrence_datetime: str = Field(
        description="Timestamp originale, YYYY-MM-DD HH:MM:SS"
    )
    component: str = Field(description="Identificatore del componente originale")
    reason: str = Field(description="Tipo tecnico di guasto originale")


class StructuredDiagnosis(BaseModel):
    root_causes: list[StructuredFault] = Field(
        description="Una voce per ogni guasto esplicitamente diagnosticato"
    )


@dataclass(frozen=True)
class StructuredFinalization:
    prediction: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    elapsed_seconds: float


_EXTRACTIVE_SYSTEM = (
    "You are a lossless formatter, NOT a root cause investigator. "
    "Convert the supplied agent answer into StructuredDiagnosis. "
    "Use only the facts literally stated in that answer. "
    "Do not introduce a new component, fault reason or timestamp. "
    "Do not use external knowledge, infer missing information or "
    "repair an unsupported hypothesis. Keep the number and order "
    "of incident entries. If any required value is missing, "
    "do not fabricate a replacement."
)


def _tokens(raw: Any) -> tuple[int, int, int]:
    usage = getattr(raw, "usage_metadata", None) or {}
    if not isinstance(usage, dict):
        return (0, 0, 0)
    input_tokens = int(usage.get("input_tokens", 0) or 0)
    output_tokens = int(usage.get("output_tokens", 0) or 0)
    total_tokens = int(
        usage.get("total_tokens", input_tokens + output_tokens)
        or (input_tokens + output_tokens)
    )
    return input_tokens, output_tokens, total_tokens


def _parsed_payload(reply: Any) -> tuple[StructuredDiagnosis, Any]:
    if not isinstance(reply, dict):
        raise StructuredOutputError(
            "Il provider non ha restituito il risultato include_raw atteso"
        )
    parsed = reply.get("parsed")
    parse_error = reply.get("parsing_error")
    if parse_error is not None or parsed is None:
        raise StructuredOutputError(
            f"Parsing dell'output strutturato fallito: {parse_error}"
        )
    try:
        if isinstance(parsed, StructuredDiagnosis):
            diagnosis = parsed
        else:
            diagnosis = StructuredDiagnosis.model_validate(parsed)
    except Exception as exc:
        raise StructuredOutputError(
            "Schema strutturato restituito dal provider non valido"
        ) from exc
    return diagnosis, reply.get("raw")


def formatta_diagnosi_strutturata(
    llm: Any,
    raw_response: str,
    *,
    expected_faults: int | None = None,
) -> StructuredFinalization:
    """Esegue una sola conversione strutturata con vincolo estrattivo.

    L'eventuale expected_faults deve provenire dalla richiesta visibile
    all'agente, mai da scoring_points o dalla ground truth.
    """
    if not isinstance(raw_response, str) or not raw_response.strip():
        raise StructuredOutputError("Risposta originale vuota o assente")

    try:
        formatter = llm.with_structured_output(
            StructuredDiagnosis, include_raw=True
        )
    except (AttributeError, NotImplementedError, TypeError) as exc:
        raise StructuredOutputError(
            "Il modello non supporta with_structured_output(include_raw=True)"
        ) from exc

    started = time.perf_counter()
    try:
        reply = formatter.invoke([
            SystemMessage(content=_EXTRACTIVE_SYSTEM),
            HumanMessage(content=raw_response),
        ])
    except Exception as exc:
        raise StructuredOutputError(
            f"Chiamata di finalizzazione fallita: {type(exc).__name__}: {exc}"
        ) from exc

    elapsed = round(time.perf_counter() - started, 3)
    parsed, raw = _parsed_payload(reply)

    if expected_faults is not None and len(parsed.root_causes) != expected_faults:
        raise StructuredOutputError("Cardinalita' del task non rispettata")

    # Il formatter non deve introdurre valori non detti dall'agente.
    # Non e' una prova di attribuzione: quella appartiene a PAVE.
    causes = []
    for index, fault in enumerate(parsed.root_causes, 1):
        for field, value in (
            ("occurrence_datetime", fault.occurrence_datetime),
            ("component", fault.component),
            ("reason", fault.reason),
        ):
            if not isinstance(value, str) or value not in raw_response:
                raise StructuredOutputError(
                    f"Guasto {index}: {field} non presente letteralmente nella "
                    "risposta originale"
                )
        try:
            causes.append(RootCause(
                occurrence_datetime=fault.occurrence_datetime,
                component=fault.component,
                reason=fault.reason,
            ))
        except OutputContractError as exc:
            raise StructuredOutputError(str(exc)) from exc

    try:
        canonical = serialize_openrca_json(Diagnosis(tuple(causes)))
        parse_openrca_json(canonical, expected_faults=expected_faults)
    except OutputContractError as exc:
        raise StructuredOutputError(str(exc)) from exc

    input_tokens, output_tokens, total_tokens = _tokens(raw)
    return StructuredFinalization(
        prediction=canonical,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        elapsed_seconds=elapsed,
    )
