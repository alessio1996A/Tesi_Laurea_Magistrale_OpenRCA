"""RQ2-V5: esecutore reale di D, C e K per il runner a matrice.

Riusa, SENZA modificarle, le parti pure del percorso V4: ExperimentConfig,
run_experiment, il ponte V3 del testo finale di D, i pacchetti C/K, la chiamata
unica C/K e i normalizzatori di ricevuta V4 (che applicano il contratto strict
V2). Lascia fuori solo i cancelli di release/attestazione del ledger V4.

Unica novita' di formato: PRIMA del parser strict la risposta passa per la
politica V5 (un solo fence JSON, uguale per tutti i modelli). Il testo
originale, il suo hash e la deviazione restano registrati.

Dopo il claim ci sono al massimo DUE tentativi, e il secondo solo per un errore
di trasporto senza output del modello (politica in rq2_v5_retry.py, uguale per
tutti): il primo tentativo resta sempre nel record. Questo modulo importa
LangChain/SDK: usarlo solo dove l'ambiente e' quello pinned.

Contenuto
---------
- `prompt_hashes`: SHA-256 dei prompt di sistema C e K (vanno nel manifest del run);
- `V5DRunnerCapture`: cattura del D (diagnosi dell'agente) con la politica di formato V5;
- `_check_ck_package`: controllo del pacchetto di messaggi per le chiamate C e K;
- `V5StageExecutor`: l'esecutore iniettato nel runner; `prepare` fa tutto cio' che puo'
  fallire offline, `run` esegue UNA chiamata (con al piu' un secondo tentativo per errore
  di trasporto).

Stage: D = esperimento diagnostico completo dell'agente; C = ipotesi di causa; K = regola
candidata (il pacchetto di C e K si costruisce a partire dal risultato di D).
"""
from __future__ import annotations

import hashlib
import time
from pathlib import Path
from unittest.mock import patch

import evaluation.rq2_v3_d_final_stream_candidate as d_stream
from evaluation.experiment_config import ExperimentConfig
from evaluation.experiment_runner import run_experiment
from evaluation.rq2_model_factory import crea_modello_rq2
from evaluation.rq2_probe_adapter import (
    CAUSE_SYSTEM, RULE_SYSTEM, prepare_candidate_rule, prepare_cause_probe,
)
from evaluation.rq2_stage_binding import ALLOWED_TOOLS
from evaluation.rq2_v2_ck_provider_transport_candidate import (
    one_ck_call_candidate,
)
from evaluation.rq2_v2_unified_live_stage_preflight import _source_instruction
from evaluation.rq2_v3_d_runner_capture_candidate import V3DRunnerCapture
from evaluation.rq2_v4_scientific_receipt_adapter_candidate import (
    V4ScientificReceiptBlocked, normalize_v4_ck_call, normalize_v4_d_capture,
)
from evaluation.rq2_v5_matrix_runner import (
    STATUS_RECEIPT_REJECTED,
)
from evaluation.rq2_v5_response_normalization import (
    apply_policy, wrap_visible_text_extractor,
)
from evaluation.rq2_v5_retry import (
    ck_error_is_transport, d_error_is_transport, error_type,
    run_with_one_retry,
)

VERSION = "rq2_v5_stage_executor_v1"
# Budget dell'esperimento D, uguali per tutti i modelli (finiscono anche nel manifest):
# turni massimi di tool, verifiche massime del pianificatore e limite di ricorsione del grafo.
D_MAX_ROUNDS = 6
PLANNER_CHECKS = 2
RECURSION_LIMIT = 30


def _sha256_text(text: str) -> str:
    """SHA-256 (esadecimale) di un testo in UTF-8."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def prompt_hashes() -> dict:
    """Hash dei prompt di sistema C/K: vanno nel manifest del run."""
    return {"C_system_prompt_sha256": _sha256_text(CAUSE_SYSTEM),
            "K_system_prompt_sha256": _sha256_text(RULE_SYSTEM)}


class V5DRunnerCapture(V3DRunnerCapture):
    """Cattura V3 del D + politica di formato V5 sul solo messaggio finale.

    La politica e' applicata dentro il ponte V3, prima che run_experiment
    legga la risposta: il parser strict V2 (che resta invariato) vede quindi
    gia' il testo normalizzato. Stessa funzione per tutti i modelli.
    """

    def __init__(self, *, harness: str):
        """`harness` e' la variante dell'agente (A0, A1, ...). Prepara la lista, inizialmente
        vuota, dei registri formato: uno per ogni messaggio finale intercettato."""
        super().__init__(harness=harness)
        self.format_records: list[dict] = []

    def __enter__(self):
        """Attiva la cattura V3 e, in piu', sostituisce temporaneamente (con `patch.object`)
        l'estrattore del testo visibile con la versione avvolta dalla politica V5.

        Se la sostituzione fallisce, la cattura viene disattivata e chiusa prima di rilanciare
        l'errore, cosi' non resta nessuna modifica attiva.
        """
        super().__enter__()
        try:
            wrapped = wrap_visible_text_extractor(
                d_stream.extract_visible_ck_text, self.format_records,
            )
            self._stack.enter_context(
                patch.object(d_stream, "extract_visible_ck_text", wrapped)
            )
        except Exception:
            self._active = False
            self._stack.close()
            raise
        return self

    def format_record(self) -> dict:
        """Registro formato del messaggio finale (o 'nessun output')."""
        if len(self.format_records) > 1:
            raise RuntimeError("Piu' messaggi finali nel D: ambiguo")
        if self.format_records:
            return dict(self.format_records[0])
        return apply_policy(None)[1]


def _check_ck_package(package: dict, expected_prompt: str) -> None:
    """Controlla che il pacchetto per C o K sia quello previsto; altrimenti `ValueError`.

    Argomenti: `package` (dizionario costruito da `prepare_cause_probe` o
    `prepare_candidate_rule`) e `expected_prompt` (il prompt di sistema congelato).

    Condizioni: due messaggi, nell'ordine system e user, entrambi con contenuto testuale;
    hash del prompt di sistema uguale a quello del prompt congelato; zero chiamate al modello
    gia' fatte; hash del pacchetto presente (64 caratteri esadecimali).
    """
    expected = _sha256_text(expected_prompt)
    messages = package.get("messages") if type(package) is dict else None
    if (
        type(messages) is not list or len(messages) != 2
        or [m.get("role") for m in messages if type(m) is dict]
        != ["system", "user"]
        or any(type(m) is not dict or type(m.get("content")) is not str
               for m in messages)
        or package.get("system_prompt_sha256") != expected
        or package.get("model_api_calls") != 0
        or type(package.get("package_sha256")) is not str
        or len(package["package_sha256"]) != 64
    ):
        raise ValueError("Pacchetto C/K non conforme al prompt congelato")


class V5StageExecutor:
    """prepare(): tutto cio' che puo' fallire offline; run(): una sola chiamata.

    E' l'`executor` che il runner a matrice (`rq2_v5_matrix_runner`) riceve dall'esterno.
    """

    def __init__(self, *, data_dir: Path, repo_dir: Path, sleep=time.sleep):
        """`data_dir` = radice dei dati del benchmark; `repo_dir` = checkout del codice;
        `sleep` = funzione di attesa fra due tentativi (iniettabile per i test)."""
        self.data_dir = Path(data_dir)
        self.repo_dir = Path(repo_dir)
        self._sleep = sleep

    # ------------------------------------------------------------ prepare
    def prepare(self, row: dict, parents: dict) -> dict:
        """Prepara uno stage SENZA chiamare il modello (tutto offline, prima del claim).

        Argomenti: `row` (riga del piano) e `parents` (record dei genitori gia' completi,
        per `stage_id`). Restituisce il materiale per `run`:
          - stage D: la configurazione dell'esperimento (`config`) e la provenienza;
          - stage C o K: il pacchetto di messaggi (`package`), la diagnosi di D
            (`diagnostic_run`) e la provenienza (hash del pacchetto e del prompt, genitori).
        Solleva `ValueError` se la configurazione o il pacchetto non sono conformi.
        """
        stage = row["stage"]
        # Istruzione ufficiale del caso (la stessa che vede l'agente), letta dai dati GT-free.
        instruction = _source_instruction(
            data_dir=self.data_dir, case_id=row["case_id"],
        )
        # Stage D: si costruisce la configurazione dell'esperimento con i budget comuni.
        if stage == "D":
            config = ExperimentConfig(
                variant=row["harness"], case_id=row["case_id"],
                model_name=row["model_id"],
                model_provider=row["model_provider"],
                max_tool_rounds=D_MAX_ROUNDS,
                max_verification_checks=PLANNER_CHECKS,
                recursion_limit=RECURSION_LIMIT,
                output_contract_mode="v2_enforce",
                variant_scheme="current",
                repo_dir=self.repo_dir, data_dir=self.data_dir,
            )
            # La configurazione costruita deve coincidere con quella scritta nel piano.
            if (
                config.canonical_variant != row["harness"]
                or config.model_name != row["model_id"]
                or config.model_provider != row["model_provider"]
            ):
                raise ValueError("Configurazione D diversa dal piano")
            return {"config": config, "provenance": {
                "max_tool_rounds": D_MAX_ROUNDS,
                "max_verification_checks": PLANNER_CHECKS,
                "recursion_limit": RECURSION_LIMIT,
                "output_contract_mode": "v2_enforce",
            }}

        # Stage C e K: si parte dalla diagnosi registrata nel D della stessa cella (stesso stem).
        stem = row["stage_id"].rsplit(":", 1)[0]
        d_receipt = parents[stem + ":D"]["receipt"]
        diagnostic_run = d_receipt["artifact"]["diagnostic_run"]
        if stage == "C":
            # C: pacchetto "ipotesi di causa", con il prompt di sistema congelato di C.
            package = prepare_cause_probe(
                original_instruction=instruction,
                diagnostic_run=diagnostic_run,
                allowed_tool_names=ALLOWED_TOOLS,
            )
            _check_ck_package(package, CAUSE_SYSTEM)
        elif stage == "K":
            # K: pacchetto "regola candidata"; usa anche la risposta grezza di C.
            c_receipt = parents[stem + ":C"]["receipt"]
            package = prepare_candidate_rule(
                original_instruction=instruction,
                diagnostic_run=diagnostic_run,
                cause_raw_json=c_receipt["artifact"]["raw_response"],
                phase="discovery", allowed_tool_names=ALLOWED_TOOLS,
            )
            _check_ck_package(package, RULE_SYSTEM)
        else:
            raise ValueError("Stage sconosciuto")
        return {
            "package": package, "diagnostic_run": diagnostic_run,
            "provenance": {
                "package_sha256": package["package_sha256"],
                "system_prompt_sha256": package["system_prompt_sha256"],
                "parents": sorted(parents),
            },
        }

    # ---------------------------------------------------------------- run
    def run(self, row: dict, prepared: dict) -> dict:
        """Esegue lo stage con la politica di retry unica (al piu' due tentativi).

        Argomenti: `row` e `prepared` (restituito da `prepare`). Il secondo tentativo scatta solo
        per un errore di trasporto senza output del modello; il primo resta nel record.
        Restituisce il dizionario d'esito (stato, ricevuta, registro formato, provenienza).
        """
        attempt = self._attempt_d if row["stage"] == "D" else self._attempt_ck
        return run_with_one_retry(
            lambda number: attempt(row, prepared), sleep=self._sleep,
        )

    def _attempt_d(self, row: dict, prepared: dict):
        """Un tentativo di D. Restituisce (esito, ritentabile, riepilogo).

        Passi: crea il modello; esegue l'esperimento sotto la cattura V5 (che applica la
        politica di formato al messaggio finale); costruisce la ricevuta V4; se la ricevuta
        viene rifiutata registra RECEIPT_REJECTED con la cattura grezza (non ritentabile).
        """
        started = time.monotonic()
        model = crea_modello_rq2(row["model_provider"], row["model_id"])
        capture = V5DRunnerCapture(harness=row["harness"])
        # La cattura e' attiva solo dentro il blocco `with`.
        with capture:
            result = run_experiment(
                prepared["config"], llm=model, verbose=False, salva=False,
            )
        captured = capture.build_receipt(result)
        fmt = capture.format_record()
        error = result.get("error")
        # Riepilogo del tentativo: tipo di errore, hash del messaggio (mai il testo) e durata.
        summary = {
            "error_type": error_type(error),
            "error_message_sha256": (
                _sha256_text(error) if type(error) is str else None),
            "elapsed_seconds": round(time.monotonic() - started, 3),
        }
        try:
            receipt = normalize_v4_d_capture(
                stage_id=row["stage_id"], logical_model=row["logical_model"],
                captured=captured,
            )
        except V4ScientificReceiptBlocked as exc:
            # Ricevuta rifiutata: non e' un errore del modello; si conserva l'output grezzo.
            return {
                "status": STATUS_RECEIPT_REJECTED, "receipt": None,
                "format": fmt,
                "provenance": {**prepared["provenance"], "raw_capture": {
                    "raw_response": result.get("raw_response"),
                    "json_status": result.get("json_status"),
                    "metrics": result.get("metrics"),
                }},
                "error_summary": {"code": "V4_RECEIPT_REJECTED",
                                  "detail": str(exc)[:200]},
            }, False, summary
        summary["stage_meter"] = receipt["artifact"].get("stage_meter")
        # Si ritenta solo un errore del provider dovuto al trasporto (rete, timeout, ...).
        retriable = (receipt["status"] == "PROVIDER_ERROR"
                     and d_error_is_transport(error))
        return {"status": receipt["status"], "receipt": receipt,
                "format": fmt, "provenance": prepared["provenance"]
                }, retriable, summary

    def _attempt_ck(self, row: dict, prepared: dict):
        """Un tentativo di C o K. Restituisce (esito, ritentabile, riepilogo).

        Passi: costruisce i due messaggi (system e user) dal pacchetto; fa UNA chiamata al
        modello; applica la politica di formato alla risposta; costruisce la ricevuta V4 con
        il testo normalizzato; la ricevuta rifiutata diventa RECEIPT_REJECTED (non ritentabile).
        """
        # Import locale: LangChain serve solo quando si esegue davvero uno stage C o K.
        from langchain_core.messages import HumanMessage, SystemMessage

        messages = prepared["package"]["messages"]
        payload = [SystemMessage(content=messages[0]["content"]),
                   HumanMessage(content=messages[1]["content"])]
        call = one_ck_call_candidate(
            row["model_provider"], row["model_id"], payload,
        )
        # Riepilogo del tentativo: errore del provider, chiamate, uso di token, motivo di arresto, durata.
        summary = {k: call.get(k) for k in (
            "provider_error", "api_attempts", "usage", "finish_reason",
            "elapsed_seconds")}
        # Politica di formato V5: il testo normalizzato va alla ricevuta, l'originale resta nel registro.
        text, fmt = apply_policy(call.get("raw_response"))
        for_receipt = dict(call)
        if call.get("provider_error") is None and text is not None:
            for_receipt["raw_response"] = text
        try:
            receipt = normalize_v4_ck_call(
                stage_id=row["stage_id"], logical_model=row["logical_model"],
                call=for_receipt, diagnostic_run=prepared["diagnostic_run"],
            )
        except V4ScientificReceiptBlocked as exc:
            return {
                "status": STATUS_RECEIPT_REJECTED, "receipt": None,
                "format": fmt,
                "provenance": {**prepared["provenance"], "raw_call": dict(summary)},
                "error_summary": {"code": "V4_RECEIPT_REJECTED",
                                  "detail": str(exc)[:200]},
            }, False, summary
        # Si ritenta solo un errore del provider dovuto al trasporto, senza output del modello.
        retriable = (receipt["status"] == "PROVIDER_ERROR"
                     and ck_error_is_transport(call))
        return {"status": receipt["status"], "receipt": receipt,
                "format": fmt, "provenance": prepared["provenance"]
                }, retriable, summary
