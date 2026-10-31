# AGENTE A1-v1 — ESECUTORE PILOTA OPENRCA
# Derivato dal runner A0 dell'utente, con report deterministico aggiuntivo.
# Un solo caso ufficiale; nessuna lettura di scoring_points o record.csv.

import json
import hashlib
import os
import sys
import time
import importlib
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal, Optional
from typing_extensions import TypedDict

import pandas as pd
from google.colab import userdata
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langchain_google_genai import ChatGoogleGenerativeAI

# Percorsi utilizzati dal nostro progetto Colab.
REPO_DIR = "/content/Tesi_OpenRCA"
SRC_DIR = f"{REPO_DIR}/src"
MANIFEST = "/content/drive/MyDrive/Tesi_OpenRCA/data/processed/benchmark_inputs_market.csv"
OUTPUT_DIR = Path("/content/drive/MyDrive/Tesi_OpenRCA/data/results")

# Primo tests di integrazione su un caso ufficiale, NON valutazione finale.
TEST_CASE_ID = "cloudbed-1_q009"
MODEL_NAME = "gemini-3.5-flash-lite"
MAX_TOOL_ROUNDS = 6
RECURSION_LIMIT = 30

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import agent.tools
importlib.reload(agent.tools)

# La chiave resta nei Secrets Colab e non viene salvata nei risultati.
api_key = userdata.get("GEMINI_API_KEY")
if not api_key:
    raise RuntimeError("GEMINI_API_KEY assente nei Secrets Colab.")
os.environ["GOOGLE_API_KEY"] = api_key

# Carichiamo soltanto il manifest senza etichette.
benchmark = pd.read_csv(MANIFEST)
assert len(benchmark) == 148, "Manifest incompleto."
assert "scoring_points" not in benchmark.columns
assert "reason" not in benchmark.columns
selezione = benchmark.loc[benchmark["case_id"] == TEST_CASE_ID]
if len(selezione) != 1:
    raise ValueError(f"case_id non univoco o mancante: {TEST_CASE_ID}")
caso = selezione.iloc[0]
cloudbed = str(caso["cloudbed"])
start_unix = int(caso["start_unix"])
end_unix = int(caso["end_unix"])
if cloudbed not in ("cloudbed-1", "cloudbed-2") or start_unix >= end_unix:
    raise ValueError("Cloudbed o intervallo non validi nel manifest.")

print("CASO PILOTA:", TEST_CASE_ID)
print("Cloudbed:", cloudbed, "| task:", caso["task_index"])
print("Intervallo Unix:", start_unix, end_unix)
print("Modello:", MODEL_NAME, "| budget round:", MAX_TOOL_ROUNDS)


# ============================================================
# REPORT DETERMINISTICO A1-v1 (SOLO TELEMETRIA, NO GROUND TRUTH)
# ============================================================
# In questo primo smoke tests il report è già stato generato in Colab.
# Non includiamo quindi il suo costo di preparazione nel runtime misurato.
EVIDENCE_PATH = Path(
    "/content/drive/MyDrive/Tesi_OpenRCA/data/processed/"
    f"evidence_A1_v1_{TEST_CASE_ID}.json"
)

if not EVIDENCE_PATH.is_file():
    raise FileNotFoundError(f"Report A1 mancante: {EVIDENCE_PATH}")

evidence_bytes = EVIDENCE_PATH.read_bytes()
evidence = json.loads(evidence_bytes.decode("utf-8"))

# Impediamo di fornire all'agente evidenze di un'altra finestra/cloudbed.
if not isinstance(evidence, dict) or evidence.get("versione") != "A1-v1":
    raise ValueError("Il report non ha il formato A1-v1 previsto.")

report_case = evidence.get("caso", {})
if not isinstance(report_case, dict) or (
    report_case.get("cloudbed") != cloudbed
    or report_case.get("start_unix") != start_unix
    or report_case.get("end_unix") != end_unix
):
    raise ValueError("Il report non corrisponde alla finestra del manifest.")

if not isinstance(evidence.get("anomalie"), dict) or not isinstance(evidence.get("patterns"), dict):
    raise ValueError("Il report A1 manca delle sezioni anomalie/patterns.")

evidence_sha256 = hashlib.sha256(evidence_bytes).hexdigest()
evidence_text = json.dumps(
    evidence, ensure_ascii=False, separators=(",", ":"), allow_nan=False
)

print("Report A1 verificato:", EVIDENCE_PATH)
print("SHA256 report:", evidence_sha256)
print("Anomalie:", evidence["anomalie"].get("totale"))
print("Pattern:", evidence["patterns"].get("totale"))


def controlla_intervallo(inizio: int, fine: int) -> Optional[str]:
    """Impedisce letture al di fuori della finestra ufficiale del caso."""
    if inizio < start_unix or fine > end_unix or inizio >= fine:
        return (f"Errore: intervallo non consentito. Usa timestamp Unix "
                f"all'interno di [{start_unix}, {end_unix}).")
    return None


# I wrapper NON espongono market_system al modello: lo impone il runner.
# Non calcolano anomalie, diagnosi o evidenze per l'agente.
@tool("tool_get_service_metrics")
def service_metrics(
    start_unix: int, end_unix: int, service_name: Optional[str] = None,
    max_rows: int = 30,
) -> str:
    """Legge rr, sr e mrt delle metriche dei servizi nella finestra Unix (secondi)."""
    errore = controlla_intervallo(start_unix, end_unix)
    if errore:
        return errore
    return agent.tools.tool_get_service_metrics(
        start_unix=start_unix, end_unix=end_unix,
        service_name=service_name, max_rows=max_rows, market_system=cloudbed,
    )


@tool("tool_get_container_metrics")
def container_metrics(
    start_unix: int, end_unix: int, cmdb_id: Optional[str] = None,
    kpi_name: Optional[str] = None, max_rows: int = 100,
) -> str:
    """Restituisce statistiche descrittive delle metriche container per KPI e componente."""
    errore = controlla_intervallo(start_unix, end_unix)
    if errore:
        return errore
    return agent.tools.tool_get_container_metrics(
        start_unix=start_unix, end_unix=end_unix, cmdb_id=cmdb_id,
        kpi_name=kpi_name, max_rows=max_rows, market_system=cloudbed,
    )


@tool("tool_get_logs")
def logs(
    start_unix: int, end_unix: int,
    log_type: Literal["service", "proxy"] = "service",
    cmdb_id: Optional[str] = None, keyword: Optional[str] = None,
    max_rows: int = 30,
) -> str:
    """Estrae log di servizio o proxy, filtrabili per componente e parola chiave."""
    errore = controlla_intervallo(start_unix, end_unix)
    if errore:
        return errore
    return agent.tools.tool_get_logs(
        start_unix=start_unix, end_unix=end_unix, log_type=log_type,
        cmdb_id=cmdb_id, keyword=keyword, max_rows=max_rows,
        market_system=cloudbed,
    )


@tool("tool_get_traces")
def traces(
    start_unix: int, end_unix: int, cmdb_id: Optional[str] = None,
    trace_id: Optional[str] = None, min_duration_ms: Optional[int] = None,
    max_rows: int = 30,
) -> str:
    """Estrae span di trace distribuite, ordinati per durata decrescente (ms)."""
    errore = controlla_intervallo(start_unix, end_unix)
    if errore:
        return errore
    return agent.tools.tool_get_traces(
        start_unix=start_unix, end_unix=end_unix, cmdb_id=cmdb_id,
        trace_id=trace_id, min_duration_ms=min_duration_ms,
        max_rows=max_rows, market_system=cloudbed,
    )



@tool("tool_get_node_metrics")
def node_metrics(
    start_unix: int,
    end_unix: int,
    cmdb_id: Optional[str] = None,
    kpi_name: Optional[str] = None,
    max_rows: int = 100,
) -> str:
    """Restituisce statistiche delle metriche dei nodi per componente e KPI."""

    # L'agente non può uscire dalla finestra del caso.
    errore = controlla_intervallo(start_unix, end_unix)
    if errore:
        return errore

    # Il cloudbed è imposto dal runner, non da Gemini.
    return agent.tools.tool_get_node_metrics(
        start_unix=start_unix,
        end_unix=end_unix,
        cmdb_id=cmdb_id,
        kpi_name=kpi_name,
        max_rows=max_rows,
        market_system=cloudbed,
    )


A1_TOOLS = [service_metrics, container_metrics, node_metrics, logs, traces]
llm = ChatGoogleGenerativeAI(model=MODEL_NAME)
llm_with_tools = llm.bind_tools(A1_TOOLS)


class State(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    tool_rounds: int

SYSTEM_PROMPT = """
You are Agent A1, an evidence-augmented Root Cause Analysis (RCA)
agent specialized in distributed microservices systems.

Your objective is to investigate telemetry and identify the most
likely root cause of the incident reported by the user.

AVAILABLE TOOLS
- tool_get_service_metrics
- tool_get_container_metrics
- tool_get_logs
- tool_get_traces
- tool_get_node_metrics

1. TIME HANDLING

Use the exact Unix timestamps in SECONDS supplied by the user.
Do not extend or modify the requested time interval.
Do not confuse Unix seconds with Unix milliseconds.

2. AUTONOMOUS EXPLORATION

Choose which tools to call and in which order based on the evidence
already collected.

Service metrics can provide an overview. Logs, distributed traces
and container metrics can help investigate the hypotheses that
emerge from the evidence.

Do not follow a rigid sequence when another investigation is
more relevant.

3. SYMPTOMS VERSUS ROOT CAUSE

A service with unusually high latency may be experiencing the
effects of a problem originating in another service or in the
infrastructure.

Do not identify the slowest service as the root cause solely
because its latency is high.

4. EVIDENCE-BASED INVESTIGATION

Investigate relevant evidence from:
- Service response times and success rates.
- Container CPU, memory and filesystem metrics.
- Application and proxy logs.
- Distributed traces and parent-child span relationships.

Refine the filters when the returned information is too broad.

Do not invent measurements, metric names, log messages or
component identifiers.

5. VALID TOOL PARAMETERS AND DATASET KPI SCHEMA

For tool_get_logs, log_type accepts only "service" or "proxy".
Never use "application" as a log_type.

For tool_get_container_metrics, kpi_name is a case-insensitive
regular expression applied to the KPI name.

For tool_get_node_metrics, kpi_name is also a case-insensitive regular expression.
Examples of observed node KPIs include system.cpu.iowait, system.mem.used,
system.disk.pct_usage and system.load.5.

The following KPI name patterns have been observed in the
cloudbed-1 Market dataset. They are examples of valid names,
not a guarantee that this list is exhaustive:

CPU:
- container_cpu_usage_seconds
- container_cpu_user_seconds
- container_cpu_system_seconds
- container_cpu_cfs_throttled_seconds
- container_cpu_cfs_throttled_periods
- container_cpu_load_average_10s

Memory:
- container_memory_working_set_MB
- container_memory_failcnt

Filesystem:
- container_fs_reads
- container_fs_reads_MB
- container_fs_writes
- container_fs_writes_MB
- container_fs_read_seconds
- container_fs_io_time_seconds
- container_fs_io_time_weighted_seconds

Network:
- container_network_receive_errors
- container_network_transmit_errors
- container_network_receive_packets_dropped
- container_network_transmit_packets_dropped

Some KPI names include device or interface suffixes, such as
/dev/vda, /dev/vda1 or eth0.

Prefer distinctive KPI name fragments from this inventory.
Do not invent KPI names or repeatedly try alternative names
that differ only slightly.

A KPI name containing "seconds" must not automatically be
interpreted as a percentage or utilization rate.
For example, container_cpu_usage_seconds is not itself a
CPU percentage.

A returned sample may contain only max_rows records. Do not
assume those records describe the complete time series.
If the sample is insufficient, refine the query meaningfully.

6. TRACE INTERPRETATION

The timestamps supplied to the telemetry tools are Unix
timestamps in seconds.

The trace CSV stores timestamps in Unix milliseconds.
The tool returns trace timestamps in milliseconds, while
its duration values are displayed in milliseconds.

When interpreting a trace timestamp, divide it by 1000
to obtain Unix seconds before comparing it with the
requested Unix-second interval.

Use trace_id, span_id and parent_span to investigate
call relationships.

A slow parent span does not automatically prove that its
own component originated the fault.

Compare parent and child spans, considering their durations
and temporal relationships. Do not attribute a fault to a
component solely because it appears in a trace.

7. NO REPEATED INVESTIGATIONS

Avoid repeating identical tool calls unless a concrete reason
justifies doing so.

If a tool returns a parameter error, correct the parameter.
If a query returns no data, change the investigation only when
there is a meaningful alternative query.

8. STOPPING CONDITION

Stop exploring when sufficient evidence supports a diagnosis.
When the evidence is insufficient, explain the uncertainty
instead of presenting an unverified hypothesis as fact.

Use at most six rounds of tool exploration. When the budget is
exhausted, synthesize the available evidence without requesting
additional tools.

9. OFFICIAL OPENRCA FINAL FORMAT

Return ONLY a valid JSON object. Do not include Markdown fences, prose
outside JSON, explanations outside JSON, or additional comments.

Example of the required JSON shape (PLACEHOLDERS, NOT A DIAGNOSIS):
{
  "1": {
    "root cause occurrence datetime": "YYYY-MM-DD HH:MM:SS",
    "root cause component": "component_identifier",
    "root cause reason": "specific_fault_reason"
  }
}

When the user query reports two failures, output keys "1" and "2"
in chronological order, with one object for each failure.
Include all three fields for each predicted failure, even when the
query evaluates only one or two of them.
Do not invent measurements or certainty. If evidence is insufficient,
use your best supported hypothesis and reflect its uncertainty by
not pretending that unsupported evidence was observed.
Use Asia/Shanghai local datetime format YYYY-MM-DD HH:MM:SS.
Do NOT use ground-truth labels or archived predictions.
"""


# Stessa logica LangGraph e stesso limite di round del runner A0.
def agente(state: State):
    rounds = state.get("tool_rounds", 0)
    if rounds >= MAX_TOOL_ROUNDS:
        stop_prompt = SYSTEM_PROMPT + (
            "\nTool exploration budget exhausted. Do not request tools. "
            "Return the final diagnosis as ONLY valid OpenRCA JSON."
        )
        risposta = llm.invoke([SystemMessage(content=stop_prompt)] + state["messages"])
    else:
        risposta = llm_with_tools.invoke(
            [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
        )
        if getattr(risposta, "tool_calls", None):
            rounds += 1
    return {"messages": [risposta], "tool_rounds": rounds}


def route_tools(state: State):
    ultimo = state["messages"][-1]
    return "tools" if getattr(ultimo, "tool_calls", None) else END


graph_builder = StateGraph(State)
graph_builder.add_node("agente", agente)
graph_builder.add_node("tools", ToolNode(A1_TOOLS))
graph_builder.add_conditional_edges(
    "agente", route_tools, {"tools": "tools", END: END}
)
graph_builder.add_edge("tools", "agente")
graph_builder.add_edge(START, "agente")
graph_rca = graph_builder.compile()


def testo_messaggio(contenuto) -> str:
    """Converte i blocchi di risposta Gemini in testo da salvare."""
    if isinstance(contenuto, str):
        return contenuto
    if isinstance(contenuto, list):
        return "\n".join(
            str(parte.get("text", "")) if isinstance(parte, dict) else str(parte)
            for parte in contenuto
        )
    return str(contenuto)


def interpreta_json(testo: str) -> dict:
    """Valida il formato senza fabbricare predizioni mancanti."""
    pulito = testo.strip()
    if pulito.startswith("```"):
        pulito = pulito.split("\n", 1)[-1]
        if pulito.endswith("```"):
            pulito = pulito[:-3].strip()
    risultato = json.loads(pulito)
    if not isinstance(risultato, dict) or not risultato:
        raise ValueError("La diagnosi non è un oggetto JSON non vuoto.")
    campi = (
        "root cause occurrence datetime",
        "root cause component",
        "root cause reason",
    )
    for indice, item in risultato.items():
        if not str(indice).isdigit() or not isinstance(item, dict):
            raise ValueError("La diagnosi deve avere chiavi numeriche e oggetti.")
        if not all(campo in item for campo in campi):
            raise ValueError(f"Campi OpenRCA mancanti per il guasto {indice}.")
        tempo = item["root cause occurrence datetime"]
        if not isinstance(tempo, str):
            raise ValueError("Datetime non testuale.")
        datetime.strptime(tempo, "%Y-%m-%d %H:%M:%S")
    return risultato


# L'istruzione originale è inclusa integralmente; la data serve ai tool.
richiesta = (
    f"Official OpenRCA instruction:\n{caso['instruction']}\n\n"
    f"Telemetry system: {cloudbed}.\n"
    f"Use EXACT Unix seconds start_unix={start_unix}, end_unix={end_unix}.\n"
    "Tool calls must remain inside this interval. "
    "Respond only in the official OpenRCA JSON format."
)

# A1 aggiunge le evidenze come contesto. Nessun tool o accesso extra
# viene esposto al modello rispetto ad A0; il report non è ground truth.
richiesta += (
    "\n\nDETERMINISTIC A1-v1 EVIDENCE REPORT\n"
    "The following JSON contains automatically derived telemetry "
    "observations from the exact requested interval.\n"
    "These observations are NOT ground truth and do NOT establish "
    "the root cause.\n"
    "Correlated metrics are not independent causal proofs.\n"
    "Missing anomalies do not prove that a component is healthy.\n"
    "Use the original tools to investigate and verify hypotheses.\n"
    "Do not assume that the earliest anomaly caused the incident.\n\n"
    f"{evidence_text}\n"
)

stato_iniziale = {
    "messages": [HumanMessage(content=richiesta)], "tool_rounds": 0,
}

metriche = {
    "llm_calls": 0, "tool_calls": 0, "tool_rounds": 0,
    "input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
}
risposta_finale = None
traiettoria = []  # Decisioni e risultati dei tool per verifiche successive.
errore_esecuzione = None
inizio = time.perf_counter()

print("\nINIZIO ESECUZIONE A1-v1 (tests pilota; non è il benchmark finale)")
try:
    for evento in graph_rca.stream(
        stato_iniziale, config={"recursion_limit": RECURSION_LIMIT},
        stream_mode="updates",
    ):
        for nodo, aggiornamento in evento.items():
            if nodo == "agente":
                metriche["tool_rounds"] = max(
                    metriche["tool_rounds"], aggiornamento.get("tool_rounds", 0)
                )
                for messaggio in aggiornamento.get("messages", []):
                    metriche["llm_calls"] += 1
                    usage = getattr(messaggio, "usage_metadata", None) or {}
                    for chiave in ("input_tokens", "output_tokens", "total_tokens"):
                        metriche[chiave] += int(usage.get(chiave, 0) or 0)
                    calls = getattr(messaggio, "tool_calls", []) or []
                    metriche["tool_calls"] += len(calls)
                    for chiamata in calls:
                        traiettoria.append({"tipo": "tool_call", "nome": chiamata.get("name"), "parametri": chiamata.get("args", {})})
                    if calls:
                        print("Round", metriche["tool_rounds"], "- tool:",
                              ", ".join(c.get("name", "?") for c in calls))
                    else:
                        risposta_finale = testo_messaggio(messaggio.content)
            elif nodo == "tools":
                for msg in aggiornamento.get("messages", []):
                    estratto = testo_messaggio(msg.content)
                    traiettoria.append({"tipo": "tool_result", "nome": msg.name, "risposta": estratto})
                    print("Risultato", msg.name, "-", len(estratto), "caratteri",
                          "|", estratto[:140].replace("\n", " "))
except Exception as exc:
    errore_esecuzione = f"{type(exc).__name__}: {exc}"
    print("ERRORE ESECUZIONE:", errore_esecuzione)

metriche["duration_seconds"] = round(time.perf_counter() - inizio, 3)
validazione = None
predizione = None
if risposta_finale is not None:
    try:
        predizione = interpreta_json(risposta_finale)
        validazione = "valid_json"
    except Exception as exc:
        validazione = f"invalid_json: {type(exc).__name__}: {exc}"

# Salviamo esattamente la risposta, anche se non è JSON valido.
# Nessun contenuto di record.csv o scoring_points è utilizzato qui.
risultato = {
    "variant": "A1-v1",
    "evidence_sha256": evidence_sha256,
    "evidence_bytes": len(evidence_bytes),
    "preprocessing_included_in_duration": False,
    "case_id": TEST_CASE_ID,
    "cloudbed": cloudbed,
    "task_index": str(caso["task_index"]),
    "query_index": int(caso["query_index"]),
    "model": MODEL_NAME,
    "max_tool_rounds": MAX_TOOL_ROUNDS,
    "prediction": json.dumps(predizione, ensure_ascii=False) if predizione else None,
    "raw_response": risposta_finale,
    "json_status": validazione,
    "error": errore_esecuzione,
    "metrics": metriche,
    "tool_trajectory": traiettoria,
}
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
destinazione = OUTPUT_DIR / f"a1_pilot_{TEST_CASE_ID}.json"
with destinazione.open("w", encoding="utf-8") as out:
    json.dump(risultato, out, indent=2, ensure_ascii=False)

print("\n=== RISULTATO PILOTA ===")
print("Formato JSON:", validazione)
print("Metriche:", json.dumps(metriche, indent=2, ensure_ascii=False))
print("Risposta modello:\n", risposta_finale or "(mancante)")
print("File salvato:", destinazione)
