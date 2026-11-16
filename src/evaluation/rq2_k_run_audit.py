"""RQ2: audit di sola lettura del run V5 (registro delle decisioni, riga 10).

Non modifica record, claim o manifest e non chiama nessuna API. Risponde a tre
domande: (1) quali stage sono stati ritentati e come e' andato il primo tentativo
rispetto all'esito finale; (2) quali stage NON sono RECORDED_COMPLETE e perche';
(3) quante deviazioni di formato ci sono state per modello. Gli esiti restano quelli
registrati: l'audit li descrive, non li corregge.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

VERSION = "rq2_k_run_audit_v1"
COMPLETE = "RECORDED_COMPLETE"
_HEAD, _TAIL = 240, 160


def _ids(stage_id: str) -> dict:
    parts = stage_id.split(":")
    if len(parts) < 4:
        raise ValueError(f"stage_id non riconosciuto: {stage_id}")
    return {"case_id": parts[-4], "model": parts[-3], "harness": parts[-2], "stage": parts[-1]}


def load_records(records_dir: Path) -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(Path(records_dir).glob("V5_RECORD_*.json"))]


def _clip(text: object) -> str | None:
    if text is None:
        return None
    text = text if isinstance(text, str) else json.dumps(text, ensure_ascii=False, default=str)
    return text if len(text) <= _HEAD + _TAIL else f"{text[:_HEAD]} [...] {text[-_TAIL:]}"


def audit(records: list[dict]) -> dict:
    status = Counter(r.get("status") for r in records)
    retried, non_complete = [], []
    deviation: dict[str, Counter] = {}
    for rec in sorted(records, key=lambda r: r["stage_id"]):
        ident = _ids(rec["stage_id"])
        fmt = rec.get("format") or {}
        deviation.setdefault(ident["model"], Counter())[fmt.get("deviation")] += 1
        attempts = ((rec.get("provenance") or {}).get("retry") or {}).get("attempts") or []
        if len(attempts) > 1:
            retried.append({
                "stage_id": rec["stage_id"], **ident,
                "attempts": [{k: a.get(k) for k in ("attempt", "status", "error_type",
                                                    "elapsed_seconds")} for a in attempts],
                "final_status": rec.get("status")})
        if rec.get("status") != COMPLETE:
            non_complete.append({
                "stage_id": rec["stage_id"], **ident, "status": rec.get("status"),
                "format_deviation": fmt.get("deviation"),
                "error_summary": _clip(rec.get("error_summary")),
                "original_response": _clip(fmt.get("original_response")),
                "blocked_by": rec.get("blocked_by")})
    return {
        "audit_version": VERSION, "records": len(records),
        "status": dict(sorted(status.items(), key=lambda kv: str(kv[0]))),
        "retried": retried, "non_complete": non_complete,
        "format_deviation_by_model": {m: {str(k): v for k, v in c.items()}
                                      for m, c in sorted(deviation.items())},
    }


def render(report: dict) -> str:
    lines = [f"Record letti: {report['records']} | esiti: {report['status']}", "",
             f"Stage ritentati: {len(report['retried'])}"]
    for item in report["retried"]:
        lines.append(f"  - {item['stage_id']}  esito finale: {item['final_status']}")
        for a in item["attempts"]:
            lines.append(f"      tentativo {a['attempt']}: {a['status']}, "
                         f"errore={a['error_type']}, {a['elapsed_seconds']} s")
    lines += ["", f"Stage non completi: {len(report['non_complete'])}"]
    for item in report["non_complete"]:
        lines += [f"  - {item['stage_id']}  [{item['status']}]  formato: {item['format_deviation']}",
                  f"      error_summary: {item['error_summary']}",
                  f"      risposta originale: {item['original_response']}"]
        if item["blocked_by"]:
            lines.append(f"      bloccato da: {item['blocked_by']}")
    lines += ["", "Deviazioni di formato per modello:"]
    for model, counts in report["format_deviation_by_model"].items():
        lines.append(f"  {model}: {counts}")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    print(render(audit(load_records(Path(sys.argv[1])))))
