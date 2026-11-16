"""Audit OFFLINE e in SOLA LETTURA dei due D Claude V4 (Sonnet, Haiku).

Nessuna API, nessuna credenziale, nessuna scrittura, nessun import del repo
(solo libreria standard). Stampa SOLO flag strutturali, nomi dei campi e hash:
mai il testo grezzo ne' i valori dei campi.

E' un'analisi descrittiva SECONDARIA: NON riclassifica i record V4, che restano
INVALID_OUTPUT. Serve a capire se, dentro il fence Markdown, c'era JSON
conforme al task_2, cioe' se il problema e' solo di formato.

Uso: python -I rq2_v5_fence_audit_readonly.py --records <cartella records V4>
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import sys

STAGES = {
    "sonnet": {
        "stage_id": "rq2_v4_task_aware_d_discovery_v0:cloudbed-1_q032:sonnet:A0:D",
        "record_sha256": "ed8e99f4928d4e539a6355d666a5a6b36e76ccb586354dfa341d33ee6fb2404f",
        "raw_sha256": "7dc1dc31eec8f6e2b89ee67e9e66de1128cdcd462ba2000c0c2a2252e0bd295d",
        "raw_len": 397,
    },
    "haiku": {
        "stage_id": "rq2_v4_task_aware_d_discovery_v0:cloudbed-1_q032:haiku:A0:D",
        "record_sha256": "1ee61fe908b32bdc439a0a594a7f56cb7b40d0a269fb9ee14c1fd16c039086a1",
        "raw_sha256": "f22aacb936923868d33c7e0b6f03f07dc0326a0e866451f38a38feac2b2deaac",
        "raw_len": 293,
    },
}
REQUIRED = ("root cause reason",)  # task_2
FENCE = re.compile(
    r"\A\s*```([A-Za-z0-9_+-]*)[ \t]*\r?\n(.*?)\r?\n?```\s*\Z", re.S,
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def no_dups(pairs):
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError("DUPLICATE_KEYS")
    return dict(pairs)


def inspect(raw: str) -> dict:
    out = {
        "starts_with_fence": raw.lstrip().startswith("```"),
        "n_fence_markers": raw.count("```"),
    }
    m = FENCE.match(raw)
    out["single_complete_fence_only"] = bool(m)  # nessun testo fuori dal fence
    if m:
        out["declared_language"] = m.group(1) or "(none)"
        inner = m.group(2)
    else:
        first, last = raw.find("```"), raw.rfind("```")
        out["text_before_fence_chars"] = first if first >= 0 else None
        out["text_after_fence_chars"] = (
            len(raw) - (last + 3) if last > first else None
        )
        out["closing_fence_present"] = last > first
        body = raw[first + 3:last] if first >= 0 and last > first else None
        inner = body.split("\n", 1)[1] if body and "\n" in body else None
    out["inner_available"] = inner is not None
    if inner is None:
        return out
    out["inner_len"] = len(inner)
    out["inner_sha256"] = sha(inner.encode("utf-8"))
    try:
        parsed = json.loads(inner, object_pairs_hook=no_dups)
        out["inner_json"] = "OK"
    except json.JSONDecodeError as exc:
        out["inner_json"] = f"JSON_DECODE_ERROR: {exc.msg} @pos {exc.pos}"
        return out
    except ValueError as exc:
        out["inner_json"] = f"ERROR: {exc}"
        return out
    out["inner_is_dict"] = isinstance(parsed, dict)
    if isinstance(parsed, dict) and parsed:
        n = len(parsed)
        out["n_faults"] = n
        out["keys_consecutive_from_1"] = set(parsed) == {
            str(i) for i in range(1, n + 1)
        }
        items = [parsed.get(str(i)) for i in range(1, n + 1)]
        out["items_are_objects"] = all(isinstance(x, dict) for x in items)
        if out["items_are_objects"]:
            out["required_fields_ok"] = all(
                all(isinstance(x.get(f), str) and x[f].strip() for f in REQUIRED)
                for x in items
            )
            out["extra_field_names"] = sorted(
                {k for x in items for k in x} - set(REQUIRED)
            )  # solo i nomi delle chiavi
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", required=True)
    args = parser.parse_args()

    paths = sorted(glob.glob(os.path.join(args.records, "V4_RECORD_*.json")))
    before = {}
    for path in paths:  # impronta dell'intero ledger PRIMA
        with open(path, "rb") as fh:
            before[path] = sha(fh.read())

    report = {}
    for name, spec in STAGES.items():
        filename = "V4_RECORD_" + sha(spec["stage_id"].encode("utf-8")) + ".json"
        path = os.path.join(args.records, filename)
        res = {"file": filename, "exists": os.path.isfile(path)}
        if res["exists"]:
            with open(path, "rb") as fh:
                rec = json.loads(fh.read().decode("utf-8"))
            res["status"] = rec.get("status")
            res["record_sha256_matches_handoff"] = (
                rec.get("record_sha256") == spec["record_sha256"]
            )
            artifact = rec.get("artifact") or {}
            run = artifact.get("diagnostic_run") or {}
            raw = run.get("raw_response")
            res["raw_is_str"] = isinstance(raw, str)
            if isinstance(raw, str):
                res["raw_len"] = len(raw)
                res["raw_len_matches_handoff"] = len(raw) == spec["raw_len"]
                res["raw_sha256_matches_handoff"] = (
                    sha(raw.encode("utf-8")) == spec["raw_sha256"]
                )
                try:
                    json.loads(raw)
                    res["strict_json_loads_on_raw"] = "OK"
                except json.JSONDecodeError as exc:
                    res["strict_json_loads_on_raw"] = (
                        f"FAIL: {exc.msg} @pos {exc.pos}"
                    )
                res["structure"] = inspect(raw)
            res["d_final_text_extraction"] = artifact.get("d_final_text_extraction")
        report[name] = res

    after = {}
    for path in sorted(glob.glob(os.path.join(args.records, "V4_RECORD_*.json"))):
        with open(path, "rb") as fh:
            after[path] = sha(fh.read())
    report["integrity"] = {
        "records_files": len(before),
        "ledger_unchanged": before == after,
        "writes_performed": 0,
        "api_calls": 0,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
