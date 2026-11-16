"""RQ2-K: lettura delle regole K dai record V5 (sola lettura, nessuna etichetta).

Estrae dai record del run le regole `candidate` da valutare e conta, per ogni
modello e harness, che fine hanno fatto tutte le altre K (astensione, output non
valido, errore del provider, stage bloccato). Non esegue nulla, non apre telemetria.

ASSUNZIONE DA VERIFICARE SU UN RECORD REALE: il testo JSON normalizzato della K sta in
`record["receipt"]["artifact"]["raw_response"]` (come per C nell'esecutore V5).
Se manca, la regola risulta `no_raw_text` e NON viene inventata: la cella di lettura
a secco (`--dry-read`) serve proprio a vedere quante regole si riescono a estrarre.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

VERSION = "rq2_k_records_v1"
STATUS_COMPLETE = "RECORDED_COMPLETE"


def _dig(obj, *path):
    for key in path:
        if not isinstance(obj, dict) or key not in obj:
            return None
        obj = obj[key]
    return obj


def parse_stage_id(stage_id: str) -> dict:
    """'[<piano>:]<caso>:<modello>:<harness>:<stage>' -> componenti.

    Il prefisso del piano e' facoltativo: si leggono sempre gli ultimi quattro campi,
    cosi' il lettore funziona con entrambe le forme di stage_id."""
    parts = stage_id.split(":")
    if len(parts) < 4 or not all(parts[-4:]):
        raise ValueError(f"stage_id non riconosciuto: {stage_id}")
    return {"case_id": parts[-4], "model": parts[-3], "harness": parts[-2], "stage": parts[-1]}


def read_k_record(record: dict) -> dict:
    """Esito di un record K: regola estratta oppure motivo per cui non c'e'."""
    ident = parse_stage_id(record["stage_id"])
    entry = {"stage_id": record["stage_id"], **ident,
             "record_status": record.get("status"), "rule": None, "outcome": None}
    if ident["stage"] != "K":
        entry["outcome"] = "not_a_k_stage"
        return entry
    if record.get("status") != STATUS_COMPLETE:
        entry["outcome"] = f"not_complete:{record.get('status')}"
        return entry
    raw = _dig(record, "receipt", "artifact", "raw_response")
    if not isinstance(raw, str):
        entry["outcome"] = "no_raw_text"
        return entry
    try:
        body = json.loads(raw)
    except ValueError:
        entry["outcome"] = "unreadable_json"
        return entry
    if not isinstance(body, dict):
        entry["outcome"] = "unreadable_json"
    elif body.get("status") == "candidate":
        entry["outcome"], entry["rule"] = "candidate", body
    elif body.get("status") == "insufficient_evidence":
        entry["outcome"] = "insufficient_evidence"
    else:
        entry["outcome"] = "other_status"
    return entry


def load_k_entries(records_dir: Path) -> list[dict]:
    """Legge tutti i record K di un archivio, in ordine stabile."""
    entries = []
    for path in sorted(Path(records_dir).glob("V5_RECORD_*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if parse_stage_id(record["stage_id"])["stage"] == "K":
            entries.append(read_k_record(record))
    entries.sort(key=lambda e: (e["model"], e["harness"], e["case_id"]))
    return entries


def summarize(entries: list[dict]) -> dict:
    """Quante K per modello|harness e con che esito. Tutte le K, nessuna selezione."""
    table: dict[str, Counter] = {}
    for entry in entries:
        table.setdefault(f"{entry['model']}|{entry['harness']}", Counter())[entry["outcome"]] += 1
    return {
        "k_stages": len(entries),
        "candidates": sum(1 for e in entries if e["outcome"] == "candidate"),
        "by_model_harness": {k: dict(sorted(v.items())) for k, v in sorted(table.items())},
    }
