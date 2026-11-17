"""Registrazione offline degli stage D/C/K di discovery, da output forniti dal chiamante.

Questo modulo coordina provenienza, validazione del JSON e salvataggio create-only. NON chiama
l'agente RCA, un LLM, un SDK, la telemetria o gli scorer. Sono supportati solo gli stage di
discovery legati ai sorgenti; il test e' sempre bloccato. Un artefatto salvato NON e' la prova
che una chiamata al provider sia avvenuta ne' che un congelamento scientifico delle regole sia
valido.

"D completo" significa che la sua traiettoria di tool era strutturalmente utilizzabile. La
risposta RCA originale puo' comunque avere un JSON non valido; C e' una *sonda indipendente*
dalle evidenze dei tool e non deve vedere la risposta finale di D.

Contenuto
---------
- `RQ2RecorderError`: errore "stage o provenienza non validi";
- `_sha_text`, `_stage_sibling`: hash di un testo e ID di uno stage "fratello" (stesso braccio);
- `_validate_ck_receipt`: lega la ricevuta di trasporto C/K ai byte esatti salvati;
- `RQ2DiscoveryStageRecorder`: `record_d`, `record_c` e `record_k` salvano i tre stage,
  `_entry`, `_instruction` e `_parent` sono i controlli comuni.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from evaluation.rq2_dryrun_plan import (
    EXPECTED_MANIFEST_SHA256, PLAN_STATUS, preview_market,
)
from evaluation.rq2_evidence_bundle import (
    EvidenceBundleError, build_evidence_bundle, evidence_ids,
)
from evaluation.rq2_kpi_formalizability_preflight import (
    evaluate_k_formalizability,
)
from evaluation.rq2_output_contracts import (
    ContractError, validate_candidate_rule, validate_cause_probe,
)
from evaluation.rq2_stage_artifact_store import (
    RQ2ArtifactStoreError, RQ2StageArtifactStore,
)
from evaluation.rq2_stage_binding import (
    ALLOWED_TOOLS, StageBindingError, _run_identity, _validate_plan,
    prepare_bound_c, prepare_bound_k,
)
from evaluation.v2_case_window_audit import MANIFEST_COLUMNS, _read_csv

RECORDER_VERSION = "rq2_discovery_stage_recorder_v0"


class RQ2RecorderError(ValueError):
    """Lo stage richiesto o la sua provenienza legata ai sorgenti non sono validi."""


def _sha_text(text: str) -> str:
    """SHA-256 (esadecimale) di un testo in UTF-8."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _stage_sibling(sid: str, suffix: str) -> str:
    """ID dello stage "fratello" di `sid` (stesso caso, modello e harness) con tipo `suffix`.

    Ad esempio da `...:C` e `"D"` si ottiene `...:D`.
    """
    return sid.rsplit(":", 1)[0] + ":" + suffix


def _validate_ck_receipt(receipt, *, stage_id, model_id, binding_sha, raw, error):
    """Lega l'uso della chiamata ai byte C/K esatti salvati; nessun uso di token inventato.

    Argomenti: `receipt` (ricevuta di trasporto o `None`), `stage_id`, `model_id`,
    `binding_sha` (hash del legame col prompt), `raw` (risposta grezza) ed `error` (errore del
    provider). Restituisce la ricevuta se coerente (o `None`), altrimenti solleva
    `RQ2RecorderError`.

    Controlli: 1) campi, versione di trasporto, stage, modello, provider, hash del legame e della
    risposta, errore, tentativi (0 o 1), nessun tool, non sintetica e durata plausibile;
    2) chiavi dell'uso di token; 3) conteggi coerenti se completo, nessun valore inventato se
    incompleto; 4) dettagli dell'uso validi; 5) nessun output se non c'e' stata nessuna
    richiesta.
    """
    if receipt is None:
        return None
    from evaluation.rq2_ck_provider_transport import VERSION
    expected = {
        "transport_version", "stage_id", "model_id", "provider",
        "binding_sha256", "raw_response_sha256", "provider_error",
        "api_attempts", "usage", "finish_reason", "provider_response_model",
        "elapsed_seconds", "tools_enabled", "is_synthetic",
    }
    digest = _sha_text(raw) if raw is not None else None
    provider = "google" if model_id.startswith("gemini-") else "anthropic"
    if (type(receipt) is not dict or set(receipt) != expected
        or receipt["transport_version"] != VERSION
        or receipt["stage_id"] != stage_id
        or receipt["model_id"] != model_id
        or receipt["provider"] != provider
        or receipt["binding_sha256"] != binding_sha
        or receipt["raw_response_sha256"] != digest
        or receipt["provider_error"] != error
        or type(receipt["api_attempts"]) is not int
        or receipt["api_attempts"] not in (0, 1)
        or receipt["tools_enabled"] is not False
        or receipt["is_synthetic"] is not False
        or type(receipt["elapsed_seconds"]) not in (int, float)
        or not 0 <= receipt["elapsed_seconds"] <= 604800
        or type(receipt["usage"]) is not dict):
        raise RQ2RecorderError("C/K transport receipt mismatch")
    usage = receipt["usage"]
    names = {"complete", "input_tokens", "output_tokens", "total_tokens",
             "input_token_details", "output_token_details"}
    if set(usage) != names or type(usage["complete"]) is not bool:
        raise RQ2RecorderError("Invalid C/K usage keys")
    counts = [usage[k] for k in ("input_tokens", "output_tokens", "total_tokens")]
    if usage["complete"]:
        if (any(type(x) is not int or x < 0 for x in counts)
            or counts[2] != counts[0] + counts[1]):
            raise RQ2RecorderError("Invalid C/K observed counts")
    elif (any(x is not None for x in counts)
          or usage["input_token_details"] is not None
          or usage["output_token_details"] is not None):
        raise RQ2RecorderError("Missing usage must not be fabricated")
    for key in ("input_token_details", "output_token_details"):
        detail = usage[key]
        if detail is not None and (
            type(detail) is not dict
            or any(type(k) is not str or type(v) is not int or v < 0
                   for k, v in detail.items())
        ):
            raise RQ2RecorderError("Invalid C/K usage detail")
    if (receipt["api_attempts"] == 0 and
        (raw is not None or usage["complete"])):
        raise RQ2RecorderError("Unattempted request has model output")
    return receipt


class RQ2DiscoveryStageRecorder:
    """Salva gli output D, C e K forniti dal chiamante; non invoca mai un provider.

    Richiede i file originali GT-free. NON esistono argomenti di modalita' di esecuzione,
    interruttori LIVE, funzioni di sblocco del test o autorizzazioni di budget.
    """

    def __init__(self, *, data_dir: Path):
        """Apre il registratore su `data_dir`.

        Passi: 1) archivio degli stage; 2) piano legato ai sorgenti, verificato e senza
        autorizzazioni (`can_execute_api` False, hash uguale a quello dell'archivio);
        3) il manifest GT-free ha l'hash atteso e si legge. Qualsiasi errore diventa
        `RQ2RecorderError`.
        """
        self.store = RQ2StageArtifactStore(data_dir=Path(data_dir))
        try:
            self.plan = preview_market(Path(data_dir))
            self.entries = _validate_plan(self.plan)
            if (
                self.plan["source_verified"] is not True
                or self.plan["status"] != PLAN_STATUS
                or self.plan["can_execute_api"] is not False
                or self.plan["preview_sha256"] != self.store.plan_sha
            ):
                raise RQ2RecorderError("Source-bound blocked plan mismatch")
            manifest_path = Path(data_dir) / (
                "data/processed/benchmark_inputs_market.csv"
            )
            if hashlib.sha256(manifest_path.read_bytes()).hexdigest() != (
                EXPECTED_MANIFEST_SHA256
            ):
                raise RQ2RecorderError("GT-free manifest hash mismatch")
            self.manifest = _read_csv(manifest_path, MANIFEST_COLUMNS)
        except RQ2RecorderError:
            raise
        except (StageBindingError, RQ2ArtifactStoreError, ValueError, OSError) as exc:
            raise RQ2RecorderError("Source-bound recorder initialization refused") from exc

    def _entry(self, sid: str, stage: str) -> dict:
        """Riga del piano per `sid`, che deve essere uno stage di discovery del tipo `stage`."""
        if type(sid) is not str or sid not in self.entries:
            raise RQ2RecorderError("Unknown stage")
        e = self.entries[sid]
        if e["stage"] != stage or e["phase"] != "discovery":
            raise RQ2RecorderError("Only planned discovery stages accepted")
        return e

    def _instruction(self, entry: dict) -> str:
        """Istruzione originale GT-free del caso di `entry`, dal manifest.

        Cloudbed, task e finestra temporale del manifest devono coincidere con quelli del
        piano; l'istruzione deve essere un testo non vuoto.
        """
        row = self.manifest.get(entry["case_id"])
        if (
            row is None
            or row["cloudbed"] != entry["cloudbed"]
            or row["task_index"] != entry["task_index"]
            or int(row["start_unix"]) != entry["start_unix"]
            or int(row["end_unix"]) != entry["end_unix"]
            or type(row["instruction"]) is not str
            or not row["instruction"].strip()
        ):
            raise RQ2RecorderError("Original GT-free instruction does not match plan")
        return row["instruction"]

    def _parent(self, stage_id: str) -> dict:
        """Record gia' salvato dello stage da cui si dipende; errore se non c'e'."""
        record = self.store.load_discovery_stage(stage_id=stage_id)
        if record is None:
            raise RQ2RecorderError("Required previous stage not recorded")
        return record

    def record_d(
        self, *, stage_id: str, model_id_proposed: str,
        diagnostic_run: dict,
    ) -> dict:
        """Registra l'esito di D e la traiettoria osservata, non la correttezza della risposta.

        Argomenti (per nome): `stage_id`, `model_id_proposed` e `diagnostic_run` (risultato del
        runner D). Stato: PROVIDER_ERROR se il run ha un errore; INVALID_OUTPUT se la
        traiettoria dei tool non e' utilizzabile; altrimenti RECORDED_COMPLETE.
        """
        e = self._entry(stage_id, "D")
        if type(diagnostic_run) is not dict:
            raise RQ2RecorderError("D must be a run dictionary")
        try:
            _run_identity(diagnostic_run, e)
        except StageBindingError as exc:
            raise RQ2RecorderError("D run identity is not the planned stage") from exc
        if (
            type(model_id_proposed) is not str
            or diagnostic_run["model"] != model_id_proposed
        ):
            raise RQ2RecorderError("D provider model ID differs from proposed model")
        instruction = self._instruction(e)
        error = diagnostic_run["error"]
        status = "RECORDED_COMPLETE"
        evidence_digest = None
        trajectory_issue = None
        if error is not None:
            status = "PROVIDER_ERROR"
        else:
            try:
                evidence = build_evidence_bundle(
                    diagnostic_run["tool_trajectory"],
                    allowed_tool_names=ALLOWED_TOOLS,
                )
                evidence_digest = evidence["bundle_sha256"]
            except (EvidenceBundleError, KeyError, TypeError, ValueError) as exc:
                status = "INVALID_OUTPUT"
                trajectory_issue = type(exc).__name__

        # Si conserva lo `json_status` originale senza far finta che C usi la risposta di D.
        # Un JSON di task non valido in D puo' coesistere con una traiettoria dei tool
        # comunque utilizzabile: e' una decisione di preregistrazione da definire.
        artifact = {
            "recorder_version": RECORDER_VERSION,
            "diagnostic_run": diagnostic_run,
            "original_instruction_sha256": _sha_text(instruction),
            "evidence_bundle_sha256": evidence_digest,
            "tool_trajectory_issue": trajectory_issue,
            "original_d_json_status": diagnostic_run.get("json_status"),
            "d_result_semantics": "RECORDED_RUN_NOT_GROUND_TRUTH_SCORE",
        }
        receipt = self.store.save_discovery_stage(
            stage_id=stage_id, model_id_proposed=model_id_proposed,
            status=status, artifact=artifact,
        )
        return {**receipt, "recorder_version": RECORDER_VERSION}

    @staticmethod
    def _response_status(raw_response: str | None, provider_error: str | None,
                         validator, evidence_allowlist: set[str]) -> tuple[str, dict | None, str | None]:
        """Stato di una risposta C/K: `(stato, contenuto validato, tipo d'errore del contratto)`.

        Con errore del provider: PROVIDER_ERROR. Altrimenti si applica `validator` sulle evidenze
        ammesse: contratto rispettato = RECORDED_COMPLETE, violato = INVALID_OUTPUT.
        """
        if provider_error is not None:
            return "PROVIDER_ERROR", None, None
        try:
            parsed = validator(
                raw_response, allowed_evidence_ids=evidence_allowlist,
            )
            return "RECORDED_COMPLETE", parsed, None
        except (ContractError, ValueError, TypeError) as exc:
            return "INVALID_OUTPUT", None, type(exc).__name__

    def record_c(
        self, *, stage_id: str, model_id_proposed: str,
        raw_response: str | None = None,
        provider_error: str | None = None,
        transport_receipt: dict | None = None,
    ) -> dict:
        """Registra l'esito di C (JSON rigoroso e trasporto), usando solo le evidenze del D gia' salvato.

        Argomenti (per nome): `stage_id`, `model_id_proposed`, `raw_response` (testo o `None`),
        `provider_error` (errore o `None`, mai insieme al testo) e `transport_receipt`.

        Passi: 1) argomenti ben formati; 2) il D dello stesso braccio esiste e ha lo stesso
        modello; 3) se D non e' completo, C e' BLOCKED_DEPENDENCY e non puo' avere output;
        4) l'istruzione coincide con quella di D; 5) il prompt di C si lega al D salvato e si
        ricavano gli ID di evidenza ammessi; 6) ricevuta di trasporto validata; 7) risposta
        validata col contratto "sonda causale"; 8) salvataggio create-only.
        """
        e = self._entry(stage_id, "C")
        if (
            type(model_id_proposed) is not str
            or (raw_response is not None and type(raw_response) is not str)
            or (provider_error is not None and (type(provider_error) is not str
                                                or not provider_error.strip()))
            or (provider_error is not None and raw_response is not None)
        ):
            raise RQ2RecorderError("Invalid C response/provider outcome")
        # 2-3. D genitore: stesso modello; se non e' completo, C e' bloccato.
        d = self._parent(e["dependencies"][0])
        if d["model_id_proposed"] != model_id_proposed:
            raise RQ2RecorderError("C model ID differs from source D")
        if d["status"] != "RECORDED_COMPLETE":
            if raw_response is not None or provider_error is not None:
                raise RQ2RecorderError("Dependent C cannot use output after failed D")
            return self.store.save_discovery_stage(
                stage_id=stage_id, model_id_proposed=model_id_proposed,
                status="BLOCKED_DEPENDENCY", artifact={},
            )
        # 4-5. Istruzione originale e legame del prompt C col D registrato.
        run = d["artifact"]["diagnostic_run"]
        instruction = self._instruction(e)
        if _sha_text(instruction) != d["artifact"]["original_instruction_sha256"]:
            raise RQ2RecorderError("D instruction provenance differs from manifest")
        try:
            binding = prepare_bound_c(
                plan=self.plan, c_stage_id=stage_id,
                original_instruction=instruction, diagnostic_run=run,
            )
            allowed = evidence_ids(build_evidence_bundle(
                run["tool_trajectory"], allowed_tool_names=ALLOWED_TOOLS,
            ))
        except (StageBindingError, EvidenceBundleError, ValueError) as exc:
            raise RQ2RecorderError("C input cannot be bound to recorded D") from exc
        # 6-7. Ricevuta di trasporto e validazione della risposta.
        receipt = _validate_ck_receipt(
            transport_receipt, stage_id=stage_id, model_id=model_id_proposed,
            binding_sha=binding["binding_sha256"],
            raw=raw_response, error=provider_error,
        )
        status, parsed, issue = self._response_status(
            raw_response, provider_error, validate_cause_probe, allowed,
        )
        artifact = {
            "recorder_version": RECORDER_VERSION,
            "raw_response": raw_response,
            "provider_error": provider_error,
            "contract_status": status,
            "contract_error_type": issue,
            "validated_c": parsed,
            "c_binding_sha256": binding["binding_sha256"],
            "bundle_sha256": binding["underlying_package"]["bundle_sha256"],
            **({"transport_receipt": receipt} if receipt is not None else {}),
        }
        return self.store.save_discovery_stage(
            stage_id=stage_id, model_id_proposed=model_id_proposed,
            status=status, artifact=artifact,
        )

    def record_k(
        self, *, stage_id: str, model_id_proposed: str,
        raw_response: str | None = None,
        provider_error: str | None = None,
        transport_receipt: dict | None = None,
    ) -> dict:
        """Registra K solo dopo un C costruito esattamente dallo stesso D e dalla stessa identita'.

        Argomenti come `record_c`. Passi: 1) argomenti ben formati; 2) il C genitore esiste e ha
        lo stesso modello; 3) se C non e' completo, K e' BLOCKED_DEPENDENCY e non puo' avere
        output; 4) il D dello stesso braccio e' completo e l'istruzione coincide; 5) i legami
        dei prompt di C e di K si ricostruiscono dal D salvato (quello di C non deve essere
        cambiato) e si ricavano le evidenze ammesse; 6) ricevuta di trasporto validata;
        7) risposta validata col contratto "regola candidata"; 8) anteprima di formalizzabilita'
        (non puo' mai autorizzare il test); 9) salvataggio create-only.
        """
        e = self._entry(stage_id, "K")
        if (
            type(model_id_proposed) is not str
            or (raw_response is not None and type(raw_response) is not str)
            or (provider_error is not None and (type(provider_error) is not str
                                                or not provider_error.strip()))
            or (provider_error is not None and raw_response is not None)
        ):
            raise RQ2RecorderError("Invalid K response/provider outcome")
        # 2-3. C genitore: stesso modello; se non e' completo, K e' bloccato.
        c = self._parent(e["dependencies"][0])
        if c["model_id_proposed"] != model_id_proposed:
            raise RQ2RecorderError("K model differs from C")
        if c["status"] != "RECORDED_COMPLETE":
            if raw_response is not None or provider_error is not None:
                raise RQ2RecorderError("Dependent K cannot use output after failed C")
            return self.store.save_discovery_stage(
                stage_id=stage_id, model_id_proposed=model_id_proposed,
                status="BLOCKED_DEPENDENCY", artifact={},
            )

        # 4. D dello stesso braccio, completo, con la stessa istruzione.
        d = self._parent(_stage_sibling(stage_id, "D"))
        if d["status"] != "RECORDED_COMPLETE":
            raise RQ2RecorderError("K cannot use a failed D")
        run = d["artifact"]["diagnostic_run"]
        instruction = self._instruction(e)
        if _sha_text(instruction) != d["artifact"]["original_instruction_sha256"]:
            raise RQ2RecorderError("K manifest/D instruction mismatch")
        # 5. Legami dei prompt di C e di K ricostruiti dal D salvato.
        try:
            c_binding = prepare_bound_c(
                plan=self.plan, c_stage_id=e["dependencies"][0],
                original_instruction=instruction, diagnostic_run=run,
            )
            if c_binding["binding_sha256"] != c["artifact"]["c_binding_sha256"]:
                raise RQ2RecorderError("C binding changed since recording")
            k_binding = prepare_bound_k(
                plan=self.plan, k_stage_id=stage_id,
                original_instruction=instruction, diagnostic_run=run,
                prior_c_binding=c_binding,
                cause_raw_json=c["artifact"]["raw_response"],
            )
            allowed = evidence_ids(build_evidence_bundle(
                run["tool_trajectory"], allowed_tool_names=ALLOWED_TOOLS,
            ))
        except (StageBindingError, EvidenceBundleError, ValueError) as exc:
            raise RQ2RecorderError("K input cannot be bound to recorded C/D") from exc

        # 6-7. Ricevuta di trasporto e validazione della risposta.
        receipt = _validate_ck_receipt(
            transport_receipt, stage_id=stage_id, model_id=model_id_proposed,
            binding_sha=k_binding["binding_sha256"],
            raw=raw_response, error=provider_error,
        )
        status, parsed, issue = self._response_status(
            raw_response, provider_error, validate_candidate_rule, allowed,
        )
        # 8. Anteprima di formalizzabilita' della regola: serve solo a documentare, mai a sbloccare.
        feasibility = (
            evaluate_k_formalizability(
                raw_response, allowed_evidence_ids=tuple(sorted(allowed)),
            ) if status == "RECORDED_COMPLETE" else None
        )
        if feasibility is not None and feasibility["ready_for_test"]:
            raise RQ2RecorderError("Source-only KPI preview cannot authorize test")
        artifact = {
            "recorder_version": RECORDER_VERSION,
            "raw_response": raw_response,
            "provider_error": provider_error,
            "contract_status": status,
            "contract_error_type": issue,
            "validated_k": parsed,
            "k_binding_sha256": k_binding["binding_sha256"],
            "preflight_status": (
                feasibility["status"] if feasibility is not None else None
            ),
            "preflight_reasons": (
                feasibility["reasons"] if feasibility is not None else None
            ),
            "scientific_freeze": False,
            **({"transport_receipt": receipt} if receipt is not None else {}),
        }
        return self.store.save_discovery_stage(
            stage_id=stage_id, model_id_proposed=model_id_proposed,
            status=status, artifact=artifact,
        )
