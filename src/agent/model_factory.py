"""Factory isolata dei provider LLM per OpenRCA.

Google preserva i default storici. Anthropic e' disponibile
esclusivamente su richiesta esplicita; nessuna inferenza all'import.
Non modificare prompt RCA, tool o regole nella comparazione cross-model.
"""
from __future__ import annotations

import os

ANTHROPIC_MODELS = frozenset({
    "claude-sonnet-5-5",
    "claude-haiku-5-5",
})


def _crea_modello_google(model_name: str):
    """Crea Gemini senza alterare la configurazione storica."""
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(model=model_name)


def _crea_modello_anthropic(model_name: str):
    """Crea Claude senza API invoke e senza retry impliciti.

    Anthropic SDK: max_retries=0 disabilita i retry.
    I modelli 5.5 non accettano temperature/top_p/top_k espliciti:
    non passiamo alcuno di questi parametri.
    """
    if model_name not in ANTHROPIC_MODELS:
        raise ValueError(
            "Modello Claude non preregistrato: " + model_name
        )
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY assente; usare Colab Secrets, "
            "non inserire la chiave in codice o GitHub."
        )

    from langchain_anthropic import ChatAnthropic
    return ChatAnthropic(model=model_name, max_retries=0)


def crea_modello(provider: str, model_name: str):
    """Restituisce un modello per LangGraph (bind_tools e invoke).

    Import lazy della sola dipendenza selezionata, zero inferenze qui.
    """
    if not isinstance(provider, str) or not provider.strip():
        raise ValueError("Provider LLM mancante.")
    if not isinstance(model_name, str) or not model_name.strip():
        raise ValueError("Nome del modello LLM mancante.")

    provider_normalizzato = provider.strip().lower()
    if provider_normalizzato == "google":
        return _crea_modello_google(model_name)
    if provider_normalizzato == "anthropic":
        return _crea_modello_anthropic(model_name)

    raise ValueError(
        f"Provider LLM non ancora implementato: {provider_normalizzato}. "
        "Disponibili 'google' e 'anthropic'."
    )
