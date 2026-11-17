"""RQ2: sandboxed SDK retry-behavior probe, no external HTTP, no model invocations.

Only enabled in the precisely pinned Colab package snapshot. Google retry
strategy is exercised on a Python callable; Anthropic SDK is exercised with
an httpx2.MockTransport returning a synthetic 503. No credentials read from
the environment. LangChain orchestration/retry behavior is NOT certified.
RQ1 model_factory is never modified or invoked. All release gates remain shut.
"""
# ---------------------------------------------------------------------------
# GUIDA ALLA LETTURA (in italiano)
#
# La docstring qui sopra e' il testo mostrato da `--help` e per questo resta identica
# all'originale. In sintesi: sonda "sandbox" del comportamento di ritentativo (retry) degli SDK
# dei provider, SENZA alcuna richiesta HTTP esterna e SENZA invocare modelli. Si abilita solo
# nell'istantanea di pacchetti Colab fissata con precisione (verificata dall'audit di sorgente).
# La strategia di retry di Google viene esercitata su una funzione Python locale; l'SDK Anthropic
# viene esercitato con un `httpx2.MockTransport` che risponde con un 503 sintetico. Non legge
# credenziali dall'ambiente. Il comportamento di orchestrazione/retry di LangChain NON e'
# certificato. La factory dei modelli di RQ1 non viene mai modificata ne' invocata e tutti i gate
# di release restano chiusi.
#
# Contenuto:
# - `EXPECTED_SOURCE_DIGESTS`: SHA-256 attesi dei file noti dei quattro pacchetti provider;
# - `RQ2MockProbeBlocked`: errore "precondizioni non soddisfatte, la sonda non parte";
# - `validate_sdk_snapshot`: controllo puro "fail-closed" sul rapporto dell'audit di sorgente;
# - `_count_synthetic_google_attempts`, `probe_google_retry_args`: tentativi di retry di Google
#   contati su una funzione in memoria;
# - `probe_anthropic_mock_503`: un solo 503 sintetico con trasporto simulato per Anthropic;
# - `run_offline_mock_probe`: orchestrazione completa (tutti i flag di esecuzione sono falsi);
# - `main`: riga di comando `--repo-dir`.
# ---------------------------------------------------------------------------
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path

from evaluation.rq2_provider_policy_source_audit import (
    EXPECTED_COLAB_VERSIONS, _package_evidence, preview_provider_policy,
)

VERSION = "rq2_sdk_retry_mock_probe_v0"
# SHA-256 dei file di pacchetto attesi: se cambiano, i pacchetti non sono quelli esaminati e la
# sonda si rifiuta di partire.
EXPECTED_SOURCE_DIGESTS = {
    "langchain-google-genai": "589106719f2038805a27ddd0c44c23d5e4a4486ea0d7116b38a83d37722ac27f",
    "google-genai": "b179b80a126a35c98b98aeefa701950304c38c8a1e117136a2270a0901fd93e4",
    "langchain-anthropic": "c55a0cb8fed75b3d310dbddf03a455f95c3c1d47aab650317bf3c9e4bab62544",
    "anthropic": "a42ef507300287261fe0b215023672a97f8a9b01216a135d614bbede72fff680",
}


class RQ2MockProbeBlocked(RuntimeError):
    """Le precondizioni esatte di ambiente/sorgente per una sonda innocua non sono soddisfatte."""


def validate_sdk_snapshot(preflight: dict) -> None:
    """Controllo puro "fail-closed", prima di importare un SDK o aprire il trasporto simulato locale.

    Argomento: `preflight`, il rapporto di `preview_provider_policy`. Non restituisce nulla:
    solleva `RQ2MockProbeBlocked` se manca il rapporto, se la factory RQ1 e' cambiata, se le
    versioni Colab non coincidono, se un flag di esecuzione (D, C/K, test) non e' falso, se sono
    state fatte chiamate API, se manca l'inventario dei pacchetti, se un pacchetto ha versione
    inattesa o se l'SHA-256 del sorgente noto di un provider e' cambiato.
    """
    if not isinstance(preflight, dict):
        raise RQ2MockProbeBlocked("Missing SDK preflight")
    if preflight.get("original_factory_unchanged") is not True:
        raise RQ2MockProbeBlocked("Frozen RQ1 factory changed")
    if preflight.get("matches_previous_colab_versions") is not True:
        raise RQ2MockProbeBlocked("Colab version snapshot changed")
    if preflight.get("can_execute_D") is not False or preflight.get("can_execute_CK") is not False:
        raise RQ2MockProbeBlocked("Production must remain blocked")
    if preflight.get("can_execute_test") is not False:
        raise RQ2MockProbeBlocked("OOD tests must remain blocked")
    if preflight.get("api_calls_executed") != 0:
        raise RQ2MockProbeBlocked("Unexpected external API execution")
    packages = preflight.get("packages")
    if not isinstance(packages, dict):
        raise RQ2MockProbeBlocked("Missing package inventory")
    for name, version in EXPECTED_COLAB_VERSIONS.items():
        p = packages.get(name)
        if not isinstance(p, dict) or p.get("version") != version:
            raise RQ2MockProbeBlocked("Unexpected package: " + name)
    for name, digest in EXPECTED_SOURCE_DIGESTS.items():
        if packages[name].get("known_source_sha256") != digest:
            raise RQ2MockProbeBlocked("Changed provider source: " + name)


def _count_synthetic_google_attempts(retry_options: object) -> int:
    """Conta i tentativi di retry su una funzione Python in memoria: nessun client e nessun HTTP.

    Argomento: `retry_options`, le opzioni di retry di google-genai (oppure `None` per i default).
    Restituisce il numero di tentativi osservati (da 1 a 3).

    Passi: 1) costruisce la configurazione di retry con la logica reale installata; 2) azzera
    l'attesa tra i tentativi (solo simulazione); 3) esegue una funzione che fallisce sempre con
    un errore di connessione sintetico; 4) controlla che l'errore finale arrivi e che il numero
    di tentativi sia plausibile.
    """
    from google.genai import _api_client
    import httpx
    import tenacity

    # 1) Usa la vera logica retry_args/Retrying del google-genai installato.
    config = dict(_api_client.retry_args(retry_options))
    config["wait"] = tenacity.wait_none()  # solo simulazione: non attende mai tra i tentativi
    count = 0

    def synthetic_transient_error() -> None:
        """Funzione che fallisce sempre con un errore di connessione sintetico, contando le chiamate."""
        nonlocal count
        count += 1
        raise httpx.ConnectError("synthetic-memory-only-connect-error")

    try:
        tenacity.Retrying(**config)(synthetic_transient_error)
    except httpx.ConnectError:
        pass  # atteso: tutti i tentativi sono chiamate Python locali
    else:
        raise RQ2MockProbeBlocked("Synthetic failure was unexpectedly swallowed")
    if not 1 <= count <= 3:
        raise RQ2MockProbeBlocked("Unexpected local retry count")
    return count


def probe_google_retry_args() -> dict:
    """Sonda dei soli `retry_args` dell'SDK google-genai: NON il percorso LangChain Google completo.

    Osserva i tentativi locali con le opzioni di default (1), con `attempts=1` (1) e con
    `attempts=2` (2); se non coincidono solleva `RQ2MockProbeBlocked`. Restituisce i conteggi e
    i flag "client non costruito, zero richieste esterne, inoltro LangChain e streaming asincrono
    NON verificati".
    """
    from google.genai.types import HttpRetryOptions

    observed = {
        "default_no_options": _count_synthetic_google_attempts(None),
        "explicit_attempts_1": _count_synthetic_google_attempts(
            HttpRetryOptions(attempts=1, initial_delay=0.0, max_delay=0.0, jitter=0.0)
        ),
        "explicit_attempts_2": _count_synthetic_google_attempts(
            HttpRetryOptions(attempts=2, initial_delay=0.0, max_delay=0.0, jitter=0.0)
        ),
    }
    if observed != {
        "default_no_options": 1,
        "explicit_attempts_1": 1,
        "explicit_attempts_2": 2,
    }:
        raise RQ2MockProbeBlocked("google-genai retry semantics mismatch")
    return {
        "sdk_retry_args_local_attempts": observed,
        "client_constructed": False,
        "external_requests": 0,
        "langchain_google_forwarding_verified": False,
        "google_async_streaming_retry_verified": False,
        "google_internal_aiohttp_implicit_retry_verified": False,
    }


def probe_anthropic_mock_503() -> dict:
    """Un singolo 503 sintetico solo a livello SDK, con un mock HTTPX2 iniettato esplicitamente e senza rete.

    Restituisce il numero di tentativi osservati (deve essere 1, con `max_retries=0`), il timeout
    richiesto e i flag "zero richieste esterne, nessuna credenziale reale, inoltro LangChain e
    timeout sotto stallo di rete NON verificati".

    Passi: 1) costruisce un client HTTP con solo il trasporto simulato; 2) crea il client
    Anthropic con chiave fittizia e URL non raggiungibile; 3) esegue una richiesta e controlla
    che arrivi un errore con codice 503; 4) controlla che il mock abbia visto una sola richiesta.
    """
    import anthropic
    import httpx2

    requests = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        """Registra la richiesta e risponde sempre con un 503 sintetico."""
        requests.append({"path": request.url.path, "method": request.method})
        return httpx2.Response(
            503, request=request,
            json={"type": "error", "error": {"type": "api_error", "message": "SYNTHETIC_503"}},
        )

    # Il MockTransport e' l'UNICO trasporto: la rete reale non e' raggiungibile.
    with httpx2.Client(
        transport=httpx2.MockTransport(handler), trust_env=False
    ) as fake_http:
        with anthropic.Anthropic(
            api_key="sk-ant-synthetic-offline-only",
            base_url="https://no-network.invalid",
            max_retries=0, timeout=15.0,
            http_client=fake_http,
            open_telemetry=False,
        ) as client:
            try:
                client.get("/v1/models", cast_to=httpx2.Response)
            except anthropic.APIStatusError as err:
                if err.status_code != 503:
                    raise RQ2MockProbeBlocked("Mock error code mismatch") from err
            else:
                raise RQ2MockProbeBlocked("Synthetic Anthropic 503 not raised")

    if len(requests) != 1:
        raise RQ2MockProbeBlocked("Anthropic SDK made unexpected mocked attempts")

    return {
        "sdk_mock_503_attempts": len(requests),
        "requested_timeout_seconds": 15.0,
        "external_requests": 0,
        "external_credentials_used": False,
        "langchain_anthropic_forwarding_verified": False,
        "timeout_enforcement_under_network_stall_verified": False,
    }


def run_offline_mock_probe(*, repo_dir: Path) -> dict:
    """Esegue l'intera sonda offline; si ferma (fail-closed) se non si e' nell'ambiente Colab esatto.

    Argomento (per nome): `repo_dir`, radice del repository. Restituisce il rapporto con lo stato
    "SDK controllato con mock locale, politica di rete LangChain NON congelata", l'hash
    dell'istantanea dei sorgenti, gli esiti per Google e Anthropic e tutti i flag di esecuzione
    (D, C/K, test) a falso.

    Passi: 1) audit di sorgente dei provider; 2) validazione dell'istantanea; 3) sonda Google;
    4) sonda Anthropic; 5) assemblaggio del rapporto.
    """
    preflight = preview_provider_policy(repo_dir=repo_dir)
    validate_sdk_snapshot(preflight)
    google = probe_google_retry_args()
    anthropic_report = probe_anthropic_mock_503()
    return {
        "version": VERSION,
        "status": "SDK_LOCAL_MOCK_CHECKED_LANGCHAIN_NETWORK_POLICY_NOT_FROZEN",
        "source_snapshot_sha256": hashlib.sha256(
            json.dumps(
                {name: preflight["packages"][name] for name in sorted(EXPECTED_SOURCE_DIGESTS)},
                sort_keys=True, separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
        "google": google,
        "anthropic": anthropic_report,
        "real_provider_requests": 0,
        "read_market": False,
        "read_ground_truth": False,
        "read_predictions": False,
        "files_written": False,
        "scientific_release_signed": False,
        "can_execute_D": False,
        "can_execute_CK": False,
        "can_execute_test": False,
        "next_gate": (
            "Prove LangChain->SDK per-request retry mapping, Google async/stream "
            "and aiohttp implicit retry; set and audit timeout in RQ2-only "
            "transport before signing scientific discovery release."
        ),
    }


def main() -> None:
    """Riga di comando: stampa in JSON il rapporto della sonda per `--repo-dir`."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-dir", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(
        run_offline_mock_probe(repo_dir=args.repo_dir),
        ensure_ascii=False, indent=2, sort_keys=True,
    ))


if __name__ == "__main__":
    main()
