"""Finalizzazione OpenRCA strutturata, indipendente dal provider.

Una chiamata LLM aggiuntiva usa l'interfaccia LangChain
`with_structured_output`. Il testo originale rimane immutato.

Il modulo e' *extractive*: i valori delle diagnosi strutturate devono
essere presenti letteralmente nella risposta grezza. Non e' una verifica
causale ne' una correzione del guasto. Non consulta ground truth.

Funzionamento: la risposta testuale dell'agente viene passata a un modello "formattatore" che la
converte in uno schema fisso (`StructuredDiagnosis`). Il risultato viene poi controllato in più modi:
numero di guasti, ogni valore presente alla lettera nel testo originale, associazione corretta tra
indice e guasto. Se un controllo fallisce si solleva `StructuredOutputError`: nessuna riparazione.

Attenzione: le classi Pydantic `StructuredFault` e `StructuredDiagnosis` NON hanno docstring di
proposito: il loro docstring verrebbe inviato al modello come descrizione dello schema e cambierebbe
la richiesta. Per documentarle si usano solo commenti `#`.
"""

from __future__ import annotations

import json
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


# Schema di un singolo guasto, inviato al modello formattatore. Non aggiungere un docstring a questa
# classe (né a StructuredDiagnosis): finirebbe nello schema dato al modello e cambierebbe la richiesta.
class StructuredFault(BaseModel):
    occurrence_datetime: str = Field(
        description="Timestamp originale, YYYY-MM-DD HH:MM:SS"
    )
    component: str = Field(description="Identificatore del componente originale")
    reason: str = Field(description="Tipo tecnico di guasto originale")


# Schema dell'intera diagnosi: un elenco di guasti. Anche qui niente docstring (vedi sopra).
class StructuredDiagnosis(BaseModel):
    root_causes: list[StructuredFault] = Field(
        description="Una voce per ogni guasto esplicitamente diagnosticato"
    )


@dataclass(frozen=True)
class StructuredFinalization:
    """Esito della finalizzazione: predizione in JSON canonico, token usati e durata.

    `usage_available` è False se il provider non ha riportato i token (i conteggi sono allora 0).
    """
    prediction: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    elapsed_seconds: float
    usage_available: bool = True


# Prompt di sistema del formattatore (in inglese perché è il testo inviato al modello): solo conversione
# fedele della risposta, nessuna nuova informazione. NON modificarlo: cambierebbe l'esperimento.
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


def _tokens(raw: Any) -> tuple[int, int, int, bool]:
    """Legge i token dalla risposta grezza del provider.

    Restituisce (token in ingresso, token in uscita, totale, dati disponibili). Se i dati mancano
    i conteggi sono 0 e l'ultimo valore è False; il totale, se assente, è la somma dei due.
    """
    usage = getattr(raw, "usage_metadata", None) or {}
    if not isinstance(usage, dict):
        return (0, 0, 0, False)
    # I dati sono "disponibili" solo se il provider riporta sia i token in ingresso sia quelli in uscita.
    usage_available = (
        "input_tokens" in usage and "output_tokens" in usage
    )
    input_tokens = int(usage.get("input_tokens", 0) or 0)
    output_tokens = int(usage.get("output_tokens", 0) or 0)
    total_tokens = int(
        usage.get("total_tokens", input_tokens + output_tokens)
        or (input_tokens + output_tokens)
    )
    return input_tokens, output_tokens, total_tokens, usage_available


def _parsed_payload(reply: Any) -> tuple[StructuredDiagnosis, Any]:
    """Estrae dalla risposta del provider la diagnosi strutturata e il messaggio grezzo.

    La risposta attesa è un dizionario con `parsed` (la diagnosi), `parsing_error` e `raw` (messaggio
    originale, da cui si leggono i token). Qualunque anomalia solleva `StructuredOutputError`.
    """
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
    # Alcuni provider restituiscono già l'oggetto, altri un dizionario: in questo caso lo si valida.
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

    Argomenti:
      llm              modello di linguaggio che supporta `with_structured_output(include_raw=True)`.
      raw_response     risposta testuale originale dell'agente (non viene modificata).
      expected_faults  numero di guasti richiesti dall'istruzione (None = non controllare il numero).

    Restituisce una `StructuredFinalization` con la predizione in JSON canonico OpenRCA, i token e la
    durata della chiamata; solleva `StructuredOutputError` se un controllo fallisce.

    Passi: (1) controllo della risposta; (2) chiamata strutturata al modello; (3) lettura dell'esito;
    (4) numero di guasti; (5) corrispondenza con l'eventuale JSON numerato originale; (6) ogni valore
    deve comparire alla lettera nella risposta originale e nello stesso guasto; (7) serializzazione
    canonica e verifica finale.
    """
    # --- 1. Controllo della risposta originale.
    if not isinstance(raw_response, str) or not raw_response.strip():
        raise StructuredOutputError("Risposta originale vuota o assente")

    # --- 2. Preparazione del formattatore: un modello che non supporta l'interfaccia è un errore esplicito.
    try:
        formatter = llm.with_structured_output(
            StructuredDiagnosis, include_raw=True
        )
    except (AttributeError, NotImplementedError, TypeError) as exc:
        raise StructuredOutputError(
            "Il modello non supporta with_structured_output(include_raw=True)"
        ) from exc

    # Una sola chiamata, misurata nel tempo; nessun retry in caso di errore.
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

    # --- 3. Lettura dell'esito e 4. numero di guasti richiesto.
    elapsed = round(time.perf_counter() - started, 3)
    parsed, raw = _parsed_payload(reply)

    if expected_faults is not None and len(parsed.root_causes) != expected_faults:
        raise StructuredOutputError("Cardinalita' del task non rispettata")

    # Se l'agente ha prodotto un JSON numerato, preserviamo anche
    # cardinalita' e associazione indice -> guasto. Non permettiamo
    # che il formatter scambi componenti o motivi tra due guasti.
    # --- 5. Se la risposta originale non è un JSON, `original` resta None e questo controllo si salta.
    try:
        original = json.loads(raw_response)
    except json.JSONDecodeError:
        original = None

    # "Numerato" = oggetto non vuoto con chiavi fatte di sole cifre e valori che sono oggetti.
    numbered_original = (
        isinstance(original, dict)
        and bool(original)
        and all(
            isinstance(key, str) and key.isdigit()
            and isinstance(value, dict)
            for key, value in original.items()
        )
    )
    if numbered_original and len(original) != len(parsed.root_causes):
        raise StructuredOutputError(
            "Il formatter ha cambiato la cardinalita' dei guasti originali"
        )

    # Il formatter non deve introdurre valori non detti dall'agente.
    # Non e' una prova di attribuzione: quella appartiene a PAVE.
    # --- 6. Controllo di ogni guasto e di ogni suo campo (data, componente, motivo).
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
            if numbered_original:
                source_fault = original.get(str(index))
                if not isinstance(source_fault, dict):
                    raise StructuredOutputError(
                        f"Guasto {index}: indice sorgente mancante"
                    )
                # Esigere valori del medesimo guasto, non di altri indici.
                if value not in source_fault.values():
                    raise StructuredOutputError(
                        f"Guasto {index}: {field} associato a un altro guasto "
                        "o non presente nel guasto originale"
                    )
                # Nome del campo corrispondente nel JSON originale: se presente, il valore non può essere cambiato.
                known_key = {
                    "occurrence_datetime": "root cause occurrence datetime",
                    "component": "root cause component",
                    "reason": "root cause reason",
                }[field]
                if (
                    known_key in source_fault
                    and source_fault[known_key] != value
                ):
                    raise StructuredOutputError(
                        f"Guasto {index}: valore originale {field} modificato"
                    )
        # Il guasto controllato viene convertito nel tipo del contratto canonico (che ne verifica il formato).
        try:
            causes.append(RootCause(
                occurrence_datetime=fault.occurrence_datetime,
                component=fault.component,
                reason=fault.reason,
            ))
        except OutputContractError as exc:
            raise StructuredOutputError(str(exc)) from exc

    # --- 7. Serializzazione canonica e prova finale: il risultato deve superare il parser del contratto.
    try:
        canonical = serialize_openrca_json(Diagnosis(tuple(causes)))
        parse_openrca_json(canonical, expected_faults=expected_faults)
    except OutputContractError as exc:
        raise StructuredOutputError(str(exc)) from exc

    # Token del solo passaggio di formattazione, letti dal messaggio grezzo del provider.
    input_tokens, output_tokens, total_tokens, usage_available = _tokens(raw)
    return StructuredFinalization(
        prediction=canonical,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        elapsed_seconds=elapsed,
        usage_available=usage_available,
    )
