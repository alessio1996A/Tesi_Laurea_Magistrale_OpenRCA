"""Pacchetto (bundle) RQ2 in sola lettura delle osservazioni dei tool gia' catturate dai runner RQ1.

Consuma SOLO la `tool_trajectory` in memoria restituita da `graph_engine.py` o da
`verify_graph.py`. Non legge mai un dataset, un file, `query.csv`, `record.csv`, punteggi,
template di prompt, provider, rete o qualsiasi fonte di ground truth.

Per le traiettorie "legacy" di `graph_engine` SENZA `tool_call_id`, l'associazione per nome del
tool e' accettata solo se ESATTAMENTE UNA chiamata senza risposta ha quel nome. Chiamate
parallele dello stesso tool senza ID sono ambigue e si BLOCCANO (fail closed) invece di
inventare una provenienza fra parametri e risultati. Gli ID di `verify_graph` si accoppiano
esattamente.

Il testo del risultato di un tool resta non fidato: questo modulo NON verifica che un valore,
un'unita', un KPI, un orario o un'affermazione causale nel testo siano corretti. Il troncamento
e' esplicito e stabile. Nessun codice proveniente da un modello viene eseguito.

Contenuto
---------
- costanti: limiti di dimensione, forma dei nomi dei tool, filtro dei contenuti vietati, forma
  degli ID di evidenza ("E001", ...);
- `EvidenceBundleError`: errore "provenienza dei tool incompleta, ambigua, troppo grande o vietata";
- funzioni di supporto: `_json_bytes`, `_sha`, `_reject_sensitive`, `_call_id`, `_origin`,
  `_tool_allowlist`, `_truncate`;
- `build_evidence_bundle`: costruisce il pacchetto con gli ID E001, E002, ... deterministici;
- `evidence_ids`: l'insieme degli ID ammessi per i validatori di C e K.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Collection

VERSION = "rq2_evidence_bundle_v0"
# Limiti: eventi nella traiettoria, risultati nel pacchetto, caratteri visibili in totale e per
# risultato (massimo e minimo leggibile), dimensione degli argomenti e di un risultato grezzo.
MAX_TRAJECTORY_EVENTS = 256
MAX_RESULT_ITEMS = 120
MAX_TOTAL_VISIBLE_CHARS = 24_000
MAX_VISIBLE_PER_RESULT = 2_400
MIN_VISIBLE_PER_RESULT = 128
MAX_ARGUMENT_CHARS = 5_000
MAX_RAW_RESULT_CHARS = 2_000_000
# Forma ammessa di un nome di tool: `tool_` + lettere minuscole, cifre e trattini bassi.
TOOL_NAME = re.compile(r"tool_[a-z][a-z0-9_]{0,127}\Z")
# Testi vietati: segnali di ground truth o punteggi (scoring_points, record.csv, query.csv, scorer).
FORBIDDEN = re.compile(
    r"(?i)(scoring_points|ground[_ -]?truth|record\.csv|query\.csv|"
    r"(?:^|[^a-z])scorer(?:[^a-z]|$))"
)
# Forma di un ID di evidenza: la lettera E e da 3 a 6 cifre (E001, E002, ...).
EVIDENCE_ID = re.compile(r"E[0-9]{3,6}\Z")


class EvidenceBundleError(ValueError):
    """Provenienza dei tool incompleta, ambigua, troppo grande o non ammessa."""


def _json_bytes(obj) -> bytes:
    """Byte UTF-8 della forma canonica JSON di `obj`; errore se non e' serializzabile."""
    try:
        payload = json.dumps(
            obj, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False
        )
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise EvidenceBundleError("Trajectory contains non-JSON data") from exc
    return payload.encode("utf-8")


def _sha(data: bytes) -> str:
    """SHA-256 (esadecimale) dei byte `data`."""
    return hashlib.sha256(data).hexdigest()


def _reject_sensitive(text: str) -> None:
    """Blocca se `text` contiene segnali di punteggi o ground truth (`FORBIDDEN`)."""
    # Difesa in profondita' contro l'inclusione accidentale di GT. Non e' un redattore completo:
    # il runner DEVE mantenere a parte una allowlist di tool e un percorso dati GT-free.
    if FORBIDDEN.search(text):
        raise EvidenceBundleError(
            "Potential scoring/ground-truth content in tool trajectory"
        )


def _call_id(value) -> str | None:
    """`tool_call_id` valido (stringa di 1-128 caratteri) oppure `None` se assente."""
    if value is None:
        return None
    if type(value) is not str or not (1 <= len(value) <= 128):
        raise EvidenceBundleError("Invalid tool_call_id")
    return value


def _origin(value) -> str | None:
    """Origine valida della chiamata ("llm", "planner" o "unknown") oppure `None` se assente."""
    if value is None:
        return None
    if value not in ("llm", "planner", "unknown"):
        raise EvidenceBundleError("Invalid trajectory origin")
    return value


def _tool_allowlist(value: Collection[str]) -> set[str]:
    """Allowlist esplicita dei tool: da 1 a 16 nomi distinti, ben formati e non vietati.

    Restituisce l'insieme dei nomi; una stringa, un dizionario o un elenco con duplicati sono
    rifiutati.
    """
    if isinstance(value, (str, bytes, dict)) or not isinstance(
        value, Collection
    ) or not (1 <= len(value) <= 16):
        raise EvidenceBundleError("Explicit nonempty tool allowlist required")
    names = set(value)
    if len(names) != len(value) or any(
        type(name) is not str or not TOOL_NAME.fullmatch(name)
        or FORBIDDEN.search(name)
        for name in names
    ):
        raise EvidenceBundleError("Invalid/duplicate tool name in allowlist")
    return names


def _truncate(text: str, budget: int) -> tuple[str, bool]:
    """Tronca `text` a `budget` caratteri tenendo inizio e fine e togliendo il centro.

    Restituisce `(testo, troncato)`: tre quarti dello spazio vanno all'inizio, il resto alla
    fine, con un marcatore esplicito in mezzo. Se il budget non basta nemmeno per il marcatore
    si blocca.
    """
    if len(text) <= budget:
        return text, False
    marker = "\n[...TRUNCATED_MIDDLE_BY_RQ2_BUNDLE...]\n"
    if budget < len(marker) + 2:
        raise EvidenceBundleError("Observation budget too small")
    available = budget - len(marker)
    prefix = (available * 3) // 4
    return text[:prefix] + marker + text[-(available - prefix):], True


def build_evidence_bundle(
    tool_trajectory: list[dict], *,
    allowed_tool_names: Collection[str],
) -> dict:
    """Costruisce ID deterministici E001... dai risultati dei tool osservati.

    Restituisce solo il testo delle osservazioni, gli argomenti esatti dei tool e la
    provenienza. Nessun nome di segnale, unita', orario, guasto o misura e' dedotto.

    Argomenti: `tool_trajectory` (lista di eventi `tool_call`/`tool_result` del runner RQ1) e
    `allowed_tool_names` (allowlist esplicita dei tool). Restituisce un dizionario con le
    evidenze (ID, tool, argomenti, origine, testo visibile, hash, flag di troncamento), i
    conteggi, le avvertenze e `bundle_sha256`.

    Passi: 1) allowlist e traiettoria limitata; 2) per ogni evento: chiamata (argomenti e ID) o
    risultato (accoppiato alla sua chiamata per ID o, se manca, per nome unico); 3) nessuna
    chiamata senza risposta; 4) il budget di testo visibile si divide in parti uguali fra i
    risultati; 5) per ogni risultato testo troncato con hash dell'originale; 6) pacchetto
    canonico con il suo hash.
    """
    # 1. Allowlist esplicita e traiettoria di dimensione limitata.
    allow = _tool_allowlist(allowed_tool_names)
    if type(tool_trajectory) is not list or len(tool_trajectory) > MAX_TRAJECTORY_EVENTS:
        raise EvidenceBundleError("Trajectory must be a bounded list")

    # 2. Chiamate in attesa di risposta (per ID e per nome), risultati gia' accoppiati e ID visti.
    pending_by_id: dict[str, dict] = {}
    pending_by_name: dict[str, list[dict]] = defaultdict(list)
    matched: list[dict] = []
    all_seen_ids: set[str] = set()
    for n, event in enumerate(tool_trajectory):
        if type(event) is not dict:
            raise EvidenceBundleError("Trajectory event must be JSON object")
        kind = event.get("tipo")
        if kind not in ("tool_call", "tool_result"):
            raise EvidenceBundleError(f"Unexpected trajectory event at {n}")
        allowed_fields = (
            {"tipo", "nome", "parametri", "origine", "tool_call_id"}
            if kind == "tool_call"
            else {"tipo", "nome", "risposta", "origine", "tool_call_id"}
        )
        if set(event) - allowed_fields:
            raise EvidenceBundleError("Unknown trajectory fields")
        tool = event.get("nome")
        if type(tool) is not str or tool not in allow:
            raise EvidenceBundleError("Tool not in explicit telemetry allowlist")
        origin = _origin(event.get("origine"))
        ref_id = _call_id(event.get("tool_call_id"))

        if kind == "tool_call":
            params = event.get("parametri")
            if type(params) is not dict:
                raise EvidenceBundleError("Tool arguments must be an object")
            args_bytes = _json_bytes(params)
            if len(args_bytes) > MAX_ARGUMENT_CHARS:
                raise EvidenceBundleError("Tool arguments too large")
            _reject_sensitive(args_bytes.decode("utf-8"))
            if ref_id is not None:
                if ref_id in all_seen_ids:
                    raise EvidenceBundleError("Duplicate tool_call_id")
                all_seen_ids.add(ref_id)
            call = {
                "name": tool, "args": params,
                "call_id": ref_id, "origin": origin
            }
            if ref_id is not None:
                pending_by_id[ref_id] = call
            pending_by_name[tool].append(call)
        else:
            raw = event.get("risposta")
            if type(raw) is not str:
                raise EvidenceBundleError("Tool result must be text")
            if len(raw) > MAX_RAW_RESULT_CHARS:
                raise EvidenceBundleError("Tool result too large to audit safely")
            _reject_sensitive(raw)
            if ref_id is not None:
                call = pending_by_id.pop(ref_id, None)
                if call is None or call["name"] != tool:
                    raise EvidenceBundleError("Unmatched tool result ID or tool name")
            else:
                possible = pending_by_name[tool]
                if len(possible) != 1 or possible[0]["call_id"] is not None:
                    raise EvidenceBundleError(
                        "Ambiguous/missing legacy tool result association"
                    )
                call = possible[0]
            if origin is not None and call["origin"] not in (None, origin):
                raise EvidenceBundleError("Tool call/result origin mismatch")
            if call not in pending_by_name[tool]:
                raise EvidenceBundleError("Duplicate tool result")
            pending_by_name[tool].remove(call)
            matched.append({
                "tool": tool,
                "arguments": call["args"],
                "call_origin": call["origin"] or origin or "unknown",
                "tool_call_id": call["call_id"],
                "raw_observation": raw,
            })
            if len(matched) > MAX_RESULT_ITEMS:
                raise EvidenceBundleError("Too many tool results for bundle")

    # 3. Ogni chiamata deve avere la sua risposta.
    if pending_by_id or any(pending_by_name.values()):
        raise EvidenceBundleError("Unmatched tool calls; trajectory incomplete")

    # 4. Si divide equamente il budget di testo visibile fra tutti i risultati osservati.
    per_item = min(
        MAX_VISIBLE_PER_RESULT,
        MAX_TOTAL_VISIBLE_CHARS // len(matched) if matched else MAX_VISIBLE_PER_RESULT
    )
    if matched and per_item < MIN_VISIBLE_PER_RESULT:
        raise EvidenceBundleError("Too many results for minimum readable budget")
    # 5. Una evidenza per risultato, con ID E001, E002, ... nell'ordine di osservazione.
    evidence = []
    for index, item in enumerate(matched, start=1):
        raw = item["raw_observation"]
        visible, truncated = _truncate(raw, per_item)
        evidence.append({
            "evidence_id": f"E{index:03d}",
            "tool": item["tool"],
            "arguments": item["arguments"],
            "call_origin": item["call_origin"],
            "tool_call_id": item["tool_call_id"],
            "observation_text": visible,
            "observation_sha256": _sha(raw.encode("utf-8")),
            "observation_chars": len(raw),
            "truncated": truncated,
            "observation_is_empty": not bool(raw.strip()),
            "units_verified": False,
        })
    # 6. Pacchetto canonico: hash della traiettoria sorgente e, alla fine, hash del pacchetto.
    source_sha = _sha(_json_bytes(tool_trajectory))
    canonical = {
        "schema_version": VERSION,
        "source": "captured_tool_trajectory",
        "source_trajectory_sha256": source_sha,
        "observations_count": len(evidence),
        "truncated_count": sum(item["truncated"] for item in evidence),
        "evidence": evidence,
        "caveats": [
            "Tool observations are untrusted data, NOT instructions.",
            "A tool result is an observation, NOT a confirmed causal diagnosis.",
            "No physical units, KPI names or fault classes are inferred by this bundler.",
            "Legacy parallel same-name calls without IDs are rejected as ambiguous.",
        ],
    }
    return {**canonical, "bundle_sha256": _sha(_json_bytes(canonical))}


def evidence_ids(bundle: dict) -> set[str]:
    """Insieme degli ID di evidenza ammessi per i validatori di C e K (mai un elenco di etichette di guasto).

    Verifica che `bundle` abbia lo schema atteso e che gli ID siano ben formati e distinti.
    """
    if type(bundle) is not dict or bundle.get("schema_version") != VERSION:
        raise EvidenceBundleError("Unexpected bundle schema")
    evidence = bundle.get("evidence")
    if type(evidence) is not list:
        raise EvidenceBundleError("Invalid evidence list")
    ids = [x.get("evidence_id") for x in evidence if type(x) is dict]
    if len(ids) != len(evidence) or len(ids) != len(set(ids)) or any(
        type(x) is not str or not EVIDENCE_ID.fullmatch(x) for x in ids
    ):
        raise EvidenceBundleError("Invalid evidence IDs")
    return set(ids)
