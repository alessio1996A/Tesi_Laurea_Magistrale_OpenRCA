"""Factory dei modelli candidata, solo per RQ2, con trasporto sincrono esplicito a versioni fissate.

NON e' la factory dei modelli di RQ1. Nessun import ne' costruzione di provider al momento
dell'import del modulo. E' pensata SOLO dietro i gate di claim e dispatch gia' esistenti della
release di discovery RQ2 firmata. Qui non si conservano chiavi; non si fa nessuna
`model.invoke`, chiamata a tool, uso asincrono, streaming o ritento automatico.

ATTENZIONE: questa politica di trasporto candidata va preregistrata/congelata prima di qualsiasi
chiamata reale a un provider. Un timeout di 300 s per richiesta NON e' un timeout dello stage.

Contenuto
---------
- costanti: versione, timeout, tentativi HTTP di Google, ritentativi e token massimi di Anthropic;
- `RQ2ModelPolicyBlocked`: errore "modello non supportato o ambiente cambiato";
- `assert_exact_runtime_snapshot`: controlla versioni dei pacchetti e hash dei sorgenti dei provider;
- `crea_modello_rq2`: costruisce il modello approvato (Google o Anthropic) senza chiamate API.
"""
from __future__ import annotations

import hashlib
import importlib.metadata as metadata
from pathlib import Path

from evaluation.rq2_budget_preflight import CANDIDATE_MODELS
from evaluation.rq2_provider_policy_source_audit import (
    EXPECTED_COLAB_VERSIONS, KNOWN_SOURCE_PATHS,
)
from evaluation.rq2_sdk_retry_mock_probe import EXPECTED_SOURCE_DIGESTS

VERSION = "rq2_model_factory_candidate_v0"
# Timeout di UNA richiesta (non dello stage). Google: un solo tentativo HTTP. Anthropic: nessun
# ritentativo e al massimo 4096 token in uscita.
TIMEOUT_SECONDS = 300.0
GOOGLE_HTTP_ATTEMPTS = 1
ANTHROPIC_MAX_RETRIES = 0
ANTHROPIC_MAX_TOKENS = 4096


class RQ2ModelPolicyBlocked(RuntimeError):
    """Modello non supportato o ambiente cambiato: NON tornare ai default di RQ1."""


def assert_exact_runtime_snapshot() -> None:
    """Blocca (fail closed) se versioni dei pacchetti o hash dei sorgenti noti non coincidono.

    Non importa nessun SDK: legge solo i metadati dei pacchetti installati. Passi: 1) ogni
    pacchetto fissato e' installato con la versione attesa; 2) il file sorgente noto di ogni
    provider esiste, non e' un link e ha lo SHA-256 atteso.
    """
    # 1. Versioni dei pacchetti.
    for package, expected in EXPECTED_COLAB_VERSIONS.items():
        try:
            actual = metadata.version(package)
        except metadata.PackageNotFoundError as exc:
            raise RQ2ModelPolicyBlocked("Missing pinned RQ2 package: " + package) from exc
        if actual != expected:
            raise RQ2ModelPolicyBlocked("RQ2 runtime package drift: " + package)
    # 2. Hash dei sorgenti dei provider.
    for package, expected_sha in EXPECTED_SOURCE_DIGESTS.items():
        path = Path(metadata.distribution(package).locate_file(KNOWN_SOURCE_PATHS[package]))
        if path.is_symlink() or not path.is_file():
            raise RQ2ModelPolicyBlocked("Missing expected RQ2 source: " + package)
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha:
            raise RQ2ModelPolicyBlocked("RQ2 provider source drift: " + package)


def crea_modello_rq2(provider: str, model_name: str):
    """Costruisce solo un modello sincrono approvato, con nessun ritento e timeout espliciti.

    Precondizione (nel punto di chiamata): release scientifica firmata validata e claim
    immutabile dello stage gia' scritto. Questa funzione non fa nessuna richiesta API.

    Argomenti: `provider` ("google" o "anthropic") e `model_name` (identificativo esatto del
    modello). Restituisce il client LangChain del provider (SDK importato solo qui, al momento
    della chiamata).

    Passi: 1) argomenti stringhe esatte; 2) la coppia (provider, modello) e' fra quelle
    preregistrate; 3) ambiente identico a quello fissato; 4) costruzione del client con i
    parametri espliciti di trasporto.
    """
    if type(provider) is not str or type(model_name) is not str:
        raise RQ2ModelPolicyBlocked("Provider/model ID must be exact strings")
    # 2. Coppie (provider, modello) preregistrate per RQ2.
    permitted = {
        (entry["provider"], entry["model_id"])
        for entry in CANDIDATE_MODELS.values()
    }
    if (provider, model_name) not in permitted:
        raise RQ2ModelPolicyBlocked("Provider/model ID not preregistered for RQ2")
    # 3. Ambiente identico a quello fissato.
    assert_exact_runtime_snapshot()
    # 4. Costruzione del client (importazione ritardata dell'SDK).
    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model_name,
            max_retries=GOOGLE_HTTP_ATTEMPTS,
            timeout=TIMEOUT_SECONDS,
        )
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model_name,
            max_retries=ANTHROPIC_MAX_RETRIES,
            max_tokens=ANTHROPIC_MAX_TOKENS,
            timeout=TIMEOUT_SECONDS,
        )
    raise RQ2ModelPolicyBlocked("Unexpected provider")
