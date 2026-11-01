"""Factory per la creazione dei modelli LLM utilizzati dall'agente RCA.

Il motore LangGraph riceve un LLM compatibile con `bind_tools` e `invoke`.
Qui sono isolate le dipendenze dai singoli provider.

In questa prima fase soltanto Google/Gemini e' implementato e testabile;
gli altri provider saranno integrati nella fase finale della tesi.
Non vengono chiamate API durante l'import di questo modulo.
"""


def _crea_modello_google(model_name: str):
    """Crea il client Gemini mantenendo gli stessi default dei piloti."""
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(model=model_name)


def crea_modello(provider: str, model_name: str):
    """Restituisce un LLM da passare a `crea_grafo_rca`.

    Le dipendenze dei provider sono caricate solo per quello selezionato.
    La funzione crea il client ma non esegue alcuna inferenza.
    """
    if not isinstance(provider, str) or not provider.strip():
        raise ValueError("Provider LLM mancante.")

    if not isinstance(model_name, str) or not model_name.strip():
        raise ValueError("Nome del modello LLM mancante.")

    provider_normalizzato = provider.strip().lower()

    if provider_normalizzato == "google":
        return _crea_modello_google(model_name)

    raise ValueError(
        f"Provider LLM non ancora implementato: {provider_normalizzato}. "
        "Per ora e' disponibile soltanto 'google'."
    )
