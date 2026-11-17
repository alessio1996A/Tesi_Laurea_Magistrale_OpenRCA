"""RQ2 read-only provider retry/timeout *source* inventory, NOT network verification.

Never instantiates SDK clients or calls a provider. Reads only the unchanged
RQ1 factory source and installed distribution metadata/known Python sources.
A source-level assertion cannot prove actual HTTP retry behavior or timeouts.
Scientific discovery and OOD test gates remain CLOSED.
"""
# ---------------------------------------------------------------------------
# GUIDA ALLA LETTURA (in italiano)
#
# La docstring qui sopra e' il testo mostrato da `--help` e per questo resta identica
# all'originale. In sintesi: inventario in sola lettura, a livello di SORGENTE, della politica di
# ritentativi e di timeout dei provider; NON e' una verifica di rete. Non istanzia mai client SDK
# ne' chiama un provider: legge solo il sorgente della factory dei modelli di RQ1 (invariata) e i
# metadati dei pacchetti installati con alcuni file Python noti. Un'affermazione sul sorgente non
# puo' provare il comportamento HTTP reale. I gate scientifici di discovery e di test OOD restano
# CHIUSI.
#
# Contenuto:
# - `EXPECTED_COLAB_VERSIONS`: versioni dei pacchetti attese (quelle usate in Colab);
# - `KNOWN_SOURCE_PATHS`: gli unici file di pacchetto che si possono leggere;
# - `RQ2PolicySourceError`: errore "sorgente della factory inatteso o file fidati mancanti";
# - `_hash_bytes`, `_git_blob`: SHA-256 e hash git di un contenuto;
# - `_factory_call`: trova nell'albero sintattico la costruzione del client di un provider;
# - `audit_factory_text`: quali parametri la factory RQ1 imposta ESPLICITAMENTE;
# - `_package_evidence`: versione e SHA-256 del file noto di un pacchetto, senza importarlo;
# - `preview_provider_policy`: il rapporto completo (il flag di release live e' SEMPRE falso);
# - `main`: riga di comando `--repo-dir`.
# ---------------------------------------------------------------------------
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.metadata as metadata
import json
import platform
from pathlib import Path

VERSION = "rq2_provider_policy_source_audit_v0"
# Hash git atteso della factory dei modelli di RQ1 congelata (agent/model_factory.py).
FROZEN_RQ1_FACTORY_BLOB = "05308d5740763db0444556dcb7330d8fb4c308ec"
# Versioni dei pacchetti usate nelle esecuzioni su Colab: il rapporto dice se coincidono.
EXPECTED_COLAB_VERSIONS = {
    "langchain-core": "1.7.1",
    "langgraph": "1.2.18",
    "langchain-anthropic": "1.7.7",
    "langchain-google-genai": "4.4.2",
    "anthropic": "2.6.0",
    "google-genai": "2.34.0",
}
# Si possono leggere SOLO questi file noti dei pacchetti: nessuna configurazione, credenziale o
# dato del progetto.
KNOWN_SOURCE_PATHS = {
    "langchain-anthropic": "langchain_anthropic/chat_models.py",
    "langchain-google-genai": "langchain_google_genai/chat_models.py",
    "anthropic": "anthropic/_base_client.py",
    "google-genai": "google/genai/_api_client.py",
}


class RQ2PolicySourceError(ValueError):
    """Sorgente della factory inatteso, oppure file fidati mancanti."""


def _hash_bytes(data: bytes) -> str:
    """SHA-256 (esadecimale) dei byte `data`."""
    return hashlib.sha256(data).hexdigest()


def _git_blob(data: bytes) -> str:
    """Hash git (SHA-1) del contenuto `data` come blob, con a-capo CRLF normalizzati in LF."""
    normalized = data.replace(b"\r\n", b"\n")
    return hashlib.sha1(
        b"blob " + str(len(normalized)).encode("ascii") + b"\x00" + normalized
    ).hexdigest()


def _factory_call(tree: ast.Module, function: str, constructor: str) -> ast.Call:
    """Chiamata al costruttore `constructor` dentro la funzione `function` dell'albero `tree`.

    Deve esserci UNA sola funzione con quel nome e UNA sola chiamata al costruttore, senza
    `**kwargs` dinamici; altrimenti solleva `RQ2PolicySourceError`.
    """
    defs = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == function
    ]
    if len(defs) != 1:
        raise RQ2PolicySourceError("Missing/duplicated factory: " + function)
    calls = [
        node for node in ast.walk(defs[0])
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == constructor
    ]
    if len(calls) != 1:
        raise RQ2PolicySourceError("Unrecognized provider construction in " + function)
    if any(keyword.arg is None for keyword in calls[0].keywords):
        raise RQ2PolicySourceError("Dynamic **kwargs in provider factory")
    return calls[0]


def audit_factory_text(source: bytes) -> dict:
    """Audit solo sull'albero sintattico: registra la configurazione *esplicita*, non i default effettivi dell'SDK.

    Argomento: `source`, byte del sorgente della factory RQ1. Restituisce quali parametri
    (modello, ritentativi, timeout, token massimi) sono impostati esplicitamente per Google e
    per Anthropic, se i ritentativi di Anthropic sono il valore zero letterale, hash git e
    SHA-256 (con a-capo normalizzati) del sorgente e se coincide con il blob congelato.
    """
    try:
        tree = ast.parse(source.decode("utf-8"))
    except (UnicodeError, SyntaxError) as exc:
        raise RQ2PolicySourceError("Unreadable RQ1 factory") from exc
    google = _factory_call(tree, "_crea_modello_google", "ChatGoogleGenerativeAI")
    claude = _factory_call(tree, "_crea_modello_anthropic", "ChatAnthropic")
    g = {item.arg: item.value for item in google.keywords}
    a = {item.arg: item.value for item in claude.keywords}
    retries = a.get("max_retries")
    anthropic_zero = isinstance(retries, ast.Constant) and retries.value == 0
    return {
        "frozen_rq1_factory_blob_match": _git_blob(source) == FROZEN_RQ1_FACTORY_BLOB,
        "factory_git_blob_sha1": _git_blob(source),
        "factory_sha256_lf_normalized": _hash_bytes(source.replace(b"\r\n", b"\n")),
        "google_model_argument_explicit": "model" in g,
        "google_max_retries_explicit": "max_retries" in g,
        "google_timeout_explicit": bool(
            {"timeout", "request_timeout", "http_options"} & set(g)
        ),
        "anthropic_model_argument_explicit": "model" in a,
        "anthropic_max_retries_literal_zero": anthropic_zero,
        "anthropic_timeout_explicit": bool(
            {"timeout", "default_request_timeout"} & set(a)
        ),
        "anthropic_max_tokens_argument_explicit": "max_tokens" in a,
    }


def _package_evidence(package: str) -> dict:
    """Solo metadati e SHA-256; nessun import, richiesta HTTP, inizializzazione dell'SDK o lettura di segreti.

    Restituisce versione installata e SHA-256 del file noto del pacchetto (o `None` se il
    pacchetto manca, il file non c'e', e' un link o supera 4 MB).
    """
    try:
        dist = metadata.distribution(package)
    except metadata.PackageNotFoundError:
        return {"version": None, "known_source_sha256": None}
    version = dist.version
    relative = KNOWN_SOURCE_PATHS.get(package)
    if relative is None:
        return {"version": version, "known_source_sha256": None}
    path = Path(dist.locate_file(relative))
    if path.is_symlink() or not path.is_file():
        return {"version": version, "known_source_sha256": None}
    if path.stat().st_size > 4_000_000:
        return {"version": version, "known_source_sha256": None}
    return {
        "version": version,
        "known_source_sha256": _hash_bytes(path.read_bytes()),
    }


def preview_provider_policy(*, repo_dir: Path) -> dict:
    """Esegue un audit di sola provenienza; il flag di release live e' SEMPRE falso.

    Argomento (per nome): `repo_dir`, radice del repository. Restituisce il rapporto: audit della
    factory RQ1, evidenze dei pacchetti, se le versioni coincidono con quelle di Colab e le
    dichiarazioni "nessuna API, nessun gate aperto".

    Passi: 1) la factory RQ1 esiste e non e' un link; 2) audit del suo sorgente; 3) evidenze dei
    pacchetti attesi; 4) confronto delle versioni; 5) assemblaggio del rapporto.
    """
    repo_dir = Path(repo_dir)
    factory = repo_dir / "src" / "agent" / "model_factory.py"
    if factory.is_symlink() or not factory.is_file():
        raise RQ2PolicySourceError("RQ1 model_factory.py missing or symlinked")
    factory_audit = audit_factory_text(factory.read_bytes())
    packages = {
        name: _package_evidence(name) for name in EXPECTED_COLAB_VERSIONS
    }
    versions_match = all(
        packages[name]["version"] == expected
        for name, expected in EXPECTED_COLAB_VERSIONS.items()
    )
    return {
        "version": VERSION,
        "status": "SOURCE_EVIDENCE_ONLY_EFFECTIVE_RETRIES_TIMEOUTS_UNVERIFIED",
        "python_version_observed": platform.python_version(),
        "factory": factory_audit,
        "packages": packages,
        "matches_previous_colab_versions": versions_match,
        "original_factory_unchanged": factory_audit["frozen_rq1_factory_blob_match"],
        "anthropic_zero_retries_in_factory_source": (
            factory_audit["anthropic_max_retries_literal_zero"]
        ),
        "gemini_retry_timeout_unspecified_in_factory_source": (
            not factory_audit["google_max_retries_explicit"]
            and not factory_audit["google_timeout_explicit"]
        ),
        "effective_google_sdk_retry_timeout_verified": False,
        "effective_anthropic_sdk_retry_timeout_verified": False,
        "sdk_transports_dynamically_exercised": False,
        "api_calls_executed": 0,
        "read_ground_truth": False,
        "read_market": False,
        "read_predictions": False,
        "files_written": False,
        "scientific_release_signed": False,
        "can_execute_D": False,
        "can_execute_CK": False,
        "can_execute_test": False,
        "next_gate": (
            "Review exact installed provider source matching these digests; "
            "prove retry/timeout policy via network-disabled simulated HTTP "
            "transport, including Google streaming/nonstreaming differences, "
            "before any scientific release."
        ),
    }


def main() -> None:
    """Riga di comando: stampa in JSON il rapporto per `--repo-dir`."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-dir", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(
        preview_provider_policy(repo_dir=args.repo_dir),
        ensure_ascii=False, indent=2, sort_keys=True,
    ))


if __name__ == "__main__":
    main()
