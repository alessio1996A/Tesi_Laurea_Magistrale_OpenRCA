"""Percorso REALE verso il provider per C/K, BLOCCATO finche' non c'e' la release del protocollo.

Usa la factory candidata solo RQ2, con parametri espliciti di nessun ritento e di timeout,
lasciando intatti l'agente RQ1 e la sua factory originale dei modelli. Nessun client del
provider viene creato all'import ne' nel preflight. Solo una futura release, rivista a parte e
con uno SHA-256 esatto fissato, puo' abilitare una richiesta di discovery. Niente stage di test,
niente ritenti automatici, niente tool, nessun tetto di spesa (per scelta del supervisore),
nessun accesso a ground truth o scorer.

Un pilot live DEVE chiamare `run_one_claimed_ck`, che verifica il caso di discovery rispetto ai
sorgenti, ricostruisce C/K solo da D/C gia' salvati, crea un claim PRIMA di costruire qualsiasi
SDK e poi scrive risposta grezza e uso dei token nel record di stage RQ2 create-only esistente.
Un arresto ambiguo => nessun ritento automatico.

Lo SHA-256 della release scientifica e' fissato dopo la rilettura indipendente riuscita da
GitHub/Drive. L'esecuzione verso il provider richiede COMUNQUE `confirm_paid_api=True` per
esattamente uno stage approvato: la release da sola non autorizza nessuna API live.

Contenuto
---------
- `VERSION`, `RELEASE_SHA256`, `RELEASE_FILENAME`: versione del trasporto e release fissata;
- `RQ2LiveCKBlocked`: errore "non si puo' eseguire C/K";
- `_sha`, `_read_release`: SHA-256 e lettura verificata dei byte esatti della release;
- `_source_bound_binding`: ricostruisce il prompt C/K dai soli D/C salvati, senza GT;
- `_usage`, `_one_call`: uso dei token e UNA sola richiesta al provider;
- `run_one_claimed_ck`: il percorso live completo (release -> claim -> chiamata -> record).
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from langchain_core.messages import AIMessage

from agent.graph_engine import testo_messaggio
from evaluation.rq2_model_factory import crea_modello_rq2 as crea_modello
from evaluation.rq2_budget_preflight import CANDIDATE_MODELS
from evaluation.rq2_discovery_claim_journal import RQ2DiscoveryClaimJournal
from evaluation.rq2_discovery_stage_recorder import RQ2DiscoveryStageRecorder
from evaluation.rq2_stage_binding import (
    prepare_bound_c, prepare_bound_k,
)
from evaluation.rq2_dryrun_plan import (
    DISCOVERY, TEST, HARNESSES, MAX_TOOL_ROUNDS,
)
from evaluation.rq2_toolfree_fake_transport import (
    PREFREEZE_C_SYSTEM_SHA256, PREFREEZE_K_SYSTEM_SHA256,
    _check_package,
)

VERSION = "rq2_ck_provider_transport_v1_rq2_only_factory"
# SHA-256 della release RQ2 di discovery firmata; il test OOD resta bloccato.
RELEASE_SHA256 = "a35c02f830a3c5f97424e0cbf8653eda6cfa674b9c8c34d95d04627e1dba8c52"
# Nome del file della release, dentro la cartella `data/rq2`.
RELEASE_FILENAME = "RQ2_SCIENTIFIC_DISCOVERY_RELEASE_V1.json"


class RQ2LiveCKBlocked(RuntimeError):
    """Non si puo' eseguire C/K senza una release scientifica congelata in modo indipendente."""


def _sha(value: bytes) -> str:
    """SHA-256 (esadecimale) dei byte `value`."""
    return hashlib.sha256(value).hexdigest()


def _read_release(root: Path) -> dict:
    """Verifica i byte ESATTI della release preregistrata, prima di qualsiasi azione sul provider.

    Argomento: `root`, radice dei dati (la release sta in `data/rq2/`). Restituisce il contenuto
    JSON della release. Passi: 1) l'hash fissato esiste ed e' ben formato; 2) il file esiste,
    non e' un link e ha esattamente quell'hash; 3) e' JSON; 4) contiene tutte le garanzie
    obbligatorie (test bloccato, nessun ritento automatico, modelli, harness e casi attesi, C/K
    senza tool, hash dei prompt). Qualsiasi scostamento solleva `RQ2LiveCKBlocked`.
    """
    if RELEASE_SHA256 is None:
        raise RQ2LiveCKBlocked("Scientific discovery release is not frozen")
    if (
        type(RELEASE_SHA256) is not str
        or len(RELEASE_SHA256) != 64
        or any(ch not in "0123456789abcdef" for ch in RELEASE_SHA256)
    ):
        raise RQ2LiveCKBlocked("Invalid pinned release hash")
    source = root / "data/rq2" / RELEASE_FILENAME
    if source.is_symlink() or not source.is_file():
        raise RQ2LiveCKBlocked("Pinned release file missing/symlink")
    blob = source.read_bytes()
    if _sha(blob) != RELEASE_SHA256:
        raise RQ2LiveCKBlocked("Scientific release bytes changed")
    try:
        record = json.loads(blob)
    except (ValueError, UnicodeDecodeError) as exc:
        raise RQ2LiveCKBlocked("Scientific release is not JSON") from exc
    if (
        type(record) is not dict
        or record.get("status") != "SCIENTIFIC_DISCOVERY_RELEASE"
        or record.get("test_unlocked") is not False
        or record.get("enable_discovery_CK") is not True
        or record.get("retry_policy") != "NO_AUTOMATIC_RETRY"
        or record.get("model_ids") != {
            m: CANDIDATE_MODELS[m]["model_id"] for m in CANDIDATE_MODELS
        }
        or record.get("C_K_tool_calls_allowed") is not False
        or record.get("budget_limit_usd") is not None
        or record.get("D_output_contract_mode") != "v2_enforce"
        or record.get("D_variant_scheme") != "current"
        or record.get("D_max_tool_rounds") != MAX_TOOL_ROUNDS
        or record.get("D_recursion_limit") != 30
        or record.get("harnesses") != list(HARNESSES)
        or record.get("discovery_case_ids") != list(DISCOVERY)
        or record.get("test_case_ids") != list(TEST)
        or record.get("C_system_prompt_sha256") != PREFREEZE_C_SYSTEM_SHA256
        or record.get("K_system_prompt_sha256") != PREFREEZE_K_SYSTEM_SHA256
    ):
        raise RQ2LiveCKBlocked("Scientific release lacks mandatory safeguards")
    return record


def _source_bound_binding(
    recorder: RQ2DiscoveryStageRecorder, stage_id: str,
) -> tuple[dict, str]:
    """Ricava il prompt C/K senza risposte D fornite dal chiamante e senza ground truth.

    Argomenti: `recorder` (registratore degli stage di discovery) e `stage_id` (stage C o K).
    Restituisce `(binding, model_id)`.

    Passi: 1) lo stage e' nel piano verificato sui sorgenti ed e' un C/K di discovery; 2) non ha
    ancora un output immutabile; 3) il D dello stesso braccio esiste, e' completo, usa lo stesso
    modello, la stessa istruzione originale e il contratto "v2_enforce"; 4) si costruisce il
    legame (binding) di C dal D; 5) per K si verifica anche il C registrato e se ne usa la
    risposta; 6) il pacchetto costruito e' dello stage giusto.
    """
    if type(stage_id) is not str or stage_id not in recorder.entries:
        raise RQ2LiveCKBlocked("Stage is not in source-verified RQ2 plan")
    entry = recorder.entries[stage_id]
    stage = entry["stage"]
    if entry["phase"] != "discovery" or stage not in ("C", "K"):
        raise RQ2LiveCKBlocked("Only discovery C/K may invoke the provider")
    model_id = CANDIDATE_MODELS[entry["logical_model"]]["model_id"]
    if recorder.store.load_discovery_stage(stage_id=stage_id) is not None:
        raise RQ2LiveCKBlocked("Stage already has an immutable output")
    d_id = stage_id.rsplit(":", 1)[0] + ":D"
    d = recorder.store.load_discovery_stage(stage_id=d_id)
    if d is None or d["status"] != "RECORDED_COMPLETE":
        raise RQ2LiveCKBlocked("Missing valid source-bound discovery D")
    if d["model_id_proposed"] != model_id:
        raise RQ2LiveCKBlocked("Recorded D uses different model ID")
    instruction = recorder._instruction(entry)
    if _sha(instruction.encode("utf-8")) != d["artifact"]["original_instruction_sha256"]:
        raise RQ2LiveCKBlocked("D and original instruction SHA differ")
    run = d["artifact"]["diagnostic_run"]
    if run.get("output_contract_mode") != "v2_enforce":
        raise RQ2LiveCKBlocked("Recorded D does not use frozen RQ1 V2 mode")
    c_id = stage_id.rsplit(":", 1)[0] + ":C"
    c_binding = prepare_bound_c(
        plan=recorder.plan, c_stage_id=c_id,
        original_instruction=instruction, diagnostic_run=run,
    )
    if stage == "C":
        binding = c_binding
    else:
        c = recorder.store.load_discovery_stage(stage_id=c_id)
        if c is None or c["status"] != "RECORDED_COMPLETE":
            raise RQ2LiveCKBlocked("Missing valid source-bound discovery C")
        if c["model_id_proposed"] != model_id:
            raise RQ2LiveCKBlocked("Recorded C uses different model ID")
        if c["artifact"]["c_binding_sha256"] != c_binding["binding_sha256"]:
            raise RQ2LiveCKBlocked("C evidence binding has changed")
        binding = prepare_bound_k(
            plan=recorder.plan, k_stage_id=stage_id,
            original_instruction=instruction, diagnostic_run=run,
            prior_c_binding=c_binding,
            cause_raw_json=c["artifact"]["raw_response"],
        )
    stage_from_package, _, _ = _check_package(binding)
    if stage_from_package != stage:
        raise RQ2LiveCKBlocked("Bound package stage differs")
    return binding, model_id


def _usage(ai: AIMessage) -> dict:
    """Uso dei token di un messaggio AI, in forma normalizzata.

    "Completo" solo se ingresso, uscita e totale sono interi non negativi e il totale e' la
    somma; altrimenti tutto a `None`. Dei dettagli si tengono solo le voci con valore intero
    non negativo.
    """
    raw = ai.usage_metadata
    fields = ("input_tokens", "output_tokens", "total_tokens")
    complete = (
        type(raw) is dict
        and all(type(raw.get(key)) is int and raw[key] >= 0 for key in fields)
        and raw["total_tokens"] == raw["input_tokens"] + raw["output_tokens"]
    )
    if not complete:
        return {
            "complete": False, "input_tokens": None,
            "output_tokens": None, "total_tokens": None,
            "input_token_details": None, "output_token_details": None,
        }
    detail = {}
    for key in ("input_token_details", "output_token_details"):
        value = raw.get(key)
        detail[key] = (
            {str(k): v for k, v in value.items()
             if type(k) is str and type(v) is int and v >= 0}
            if type(value) is dict else None
        )
    return {
        "complete": True,
        "input_tokens": raw["input_tokens"],
        "output_tokens": raw["output_tokens"],
        "total_tokens": raw["total_tokens"],
        **detail,
    }


def _one_call(provider: str, model_id: str, messages: list) -> dict:
    """UNA sola richiesta remota, senza ritenti e senza far trapelare credenziali nelle eccezioni.

    Argomenti: `provider`, `model_id` e `messages`. Restituisce testo grezzo, eventuale codice
    d'errore (mai il testo dell'eccezione), numero di tentativi (0 o 1), uso dei token, motivo
    di arresto, modello che ha risposto e durata.

    Passi: 1) costruisce il modello (se fallisce: nessuna chiamata); 2) UNA `invoke`, senza
    mai collegare tool; 3) una risposta non AI o con tool call e' un errore di protocollo;
    4) altrimenti registra uso, testo e metadati.
    """
    started = time.monotonic()
    result = {
        "raw_response": None, "provider_error": None,
        "api_attempts": 0, "usage": {
            "complete": False, "input_tokens": None,
            "output_tokens": None, "total_tokens": None,
            "input_token_details": None, "output_token_details": None,
        },
        "finish_reason": None, "provider_response_model": None,
    }
    try:
        # Factory SDK solo RQ2, a versioni fissate e con importazione ritardata.
        model = crea_modello(provider, model_id)
    except Exception as exc:
        result["provider_error"] = "SDK_CONSTRUCTION_ERROR:" + type(exc).__name__
    else:
        # Da qui la richiesta puo' essere fatturata anche se `invoke` solleva un'eccezione.
        result["api_attempts"] = 1
        try:
            # UNA richiesta, mai `bind_tools`.
            answer = model.invoke(messages)
        except Exception as exc:
            code = getattr(exc, "status_code", None)
            # Solo tipo d'errore e codice HTTP numerico, mai il testo dell'eccezione.
            result["provider_error"] = "PROVIDER_ERROR:" + type(exc).__name__
            if type(code) is int:
                result["provider_error"] += f":HTTP_{code}"
        else:
            if not isinstance(answer, AIMessage):
                result["provider_error"] = "PROTOCOL_ERROR:NonAIMessage"
            elif answer.tool_calls or answer.invalid_tool_calls:
                result["provider_error"] = "PROTOCOL_ERROR:ToolCallsForbidden"
                result["usage"] = _usage(answer)
            else:
                result["usage"] = _usage(answer)
                result["raw_response"] = testo_messaggio(
                    answer.content, solo_testo=True
                )
                meta = answer.response_metadata or {}
                reason = meta.get("finish_reason", meta.get("stop_reason"))
                name = meta.get("model_name", meta.get("model"))
                result["finish_reason"] = reason if type(reason) is str else None
                result["provider_response_model"] = (
                    name if type(name) is str and len(name) <= 160 else None
                )
    result["elapsed_seconds"] = round(time.monotonic() - started, 6)
    return result


def run_one_claimed_ck(
    *, data_dir: Path, stage_id: str, confirm_paid_api: bool = False,
) -> dict:
    """Percorso live: sorgenti/congelamento preregistrati -> claim -> chiamata -> record.

    Richiede la release di discovery con SHA fissato ESATTO E `confirm_paid_api=True`.
    Da non chiamare mai nei test unitari con credenziali reali o con claim non salvati.
    Non sblocca il test ne' autorizza da sola nessuna richiesta live al provider.

    Argomenti (per nome): `data_dir` (radice dei dati), `stage_id` (uno stage C o K di
    discovery) e `confirm_paid_api` (conferma esplicita, di default False). Restituisce stato
    e hash del record, tentativi e uso dei token.

    Passi: 1) conferma esplicita; 2) release verificata (DEVE fallire prima di SDK e claim se
    non e' congelata); 3) registratore e registro dei claim hanno lo stesso piano, che e' quello
    della release (piano, manifest e split); 4) prompt ricavato dai soli D/C salvati;
    5) claim PRIMA della chiamata; 6) UNA chiamata al provider; 7) ricevuta di trasporto e
    scrittura del record create-only.
    """
    # 1. Conferma esplicita di una chiamata a pagamento.
    if confirm_paid_api is not True:
        raise RQ2LiveCKBlocked("Explicit paid API invocation confirmation required")
    root = Path(data_dir)
    # 2. DEVE fallire prima di qualsiasi SDK o claim finche' la release non e' congelata.
    release = _read_release(root)
    # 3. Piano, manifest e split del registratore devono essere quelli della release.
    recorder = RQ2DiscoveryStageRecorder(data_dir=root)
    journal = RQ2DiscoveryClaimJournal(data_dir=root)
    if recorder.store.plan_sha != journal.plan_sha:
        raise RQ2LiveCKBlocked("Source-bound claim/recorder plan drift")
    if release.get("plan_preview_sha256") != recorder.plan["preview_sha256"]:
        raise RQ2LiveCKBlocked("Released discovery plan SHA differs")
    if release.get("source_manifest_sha256") != recorder.plan["manifest_sha256"]:
        raise RQ2LiveCKBlocked("Released manifest SHA differs")
    if release.get("source_split_sha256") != recorder.plan["split_sha256"]:
        raise RQ2LiveCKBlocked("Released split SHA differs")
    # 4. Prompt ricavato dai soli D/C salvati.
    binding, model_id = _source_bound_binding(recorder, stage_id)
    entry = recorder.entries[stage_id]
    provider = CANDIDATE_MODELS[entry["logical_model"]]["provider"]
    stage, binding_sha, messages = _check_package(binding)
    # 5. Nessun ritento automatico dopo un arresto o una risposta ambigua: il claim e' scritto
    # PRIMA della chiamata (6).
    journal.claim_stage(stage_id=stage_id, model_id_proposed=model_id)
    call = _one_call(provider, model_id, messages)
    # 7. Ricevuta di trasporto: solo hash e metadati, mai credenziali.
    receipt = {
        "transport_version": VERSION, "stage_id": stage_id,
        "model_id": model_id, "provider": provider,
        "binding_sha256": binding_sha,
        "raw_response_sha256": (
            _sha(call["raw_response"].encode("utf-8"))
            if call["raw_response"] is not None else None
        ),
        "provider_error": call["provider_error"],
        "api_attempts": call["api_attempts"],
        "usage": call["usage"], "finish_reason": call["finish_reason"],
        "provider_response_model": call["provider_response_model"],
        "elapsed_seconds": call["elapsed_seconds"],
        "tools_enabled": False,
        "is_synthetic": False,
    }
    # Dopo una risposta del provider, un errore di registrazione NON deve causare un ritento.
    fn = recorder.record_c if stage == "C" else recorder.record_k
    record = fn(
        stage_id=stage_id, model_id_proposed=model_id,
        raw_response=call["raw_response"],
        provider_error=call["provider_error"],
        transport_receipt=receipt,
    )
    return {
        "stage_id": stage_id,
        "status": record["status"],
        "record_sha256": record["record_sha256"],
        "provider_attempts": call["api_attempts"],
        "usage": call["usage"],
        "financial_cost_ceiling": None,
        "test_unlocked": False,
    }
