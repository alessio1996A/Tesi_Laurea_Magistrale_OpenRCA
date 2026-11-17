"""RQ2: audit di sola lettura del run V5 (registro delle decisioni, riga 10).

Non modifica record, claim o manifest e non chiama nessuna API. Risponde a tre
domande: (1) quali stage sono stati ritentati e come e' andato il primo tentativo
rispetto all'esito finale; (2) quali stage NON sono RECORDED_COMPLETE e perche';
(3) quante deviazioni di formato ci sono state per modello. Gli esiti restano quelli
registrati: l'audit li descrive, non li corregge.

Come si usa
-----------
    python -m evaluation.rq2_k_run_audit <cartella_record_V5>
legge tutti i file `V5_RECORD_*.json` della cartella e stampa il resoconto.

Contenuto
---------
- `_ids`: scompone l'identificativo di uno stage (caso, modello, harness, stage);
- `load_records`: carica i record dalla cartella;
- `_clip`: accorcia i testi lunghi (inizio + fine) per renderli leggibili;
- `probe_k_contract`: spiega perche' una risposta K e' stata rifiutata dal contratto;
- `audit`: costruisce il resoconto (stage ritentati, non completi, deviazioni di formato);
- `render`: lo trasforma in testo.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from evaluation import rq2_output_contracts as contracts

VERSION = "rq2_k_run_audit_v1"
# Esito di uno stage andato a buon fine (quello degli altri stage e' un'anomalia da spiegare).
COMPLETE = "RECORDED_COMPLETE"
# Per i testi lunghi si conservano i primi 240 e gli ultimi 160 caratteri.
_HEAD, _TAIL = 240, 160


def _ids(stage_id: str) -> dict:
    """Scompone un `stage_id` nei suoi quattro campi finali.

    L'id ha la forma "...:<caso>:<modello>:<harness>:<stage>"; si usano le ultime quattro
    parti separate da ":". Solleva `ValueError` se ce ne sono meno di quattro.
    """
    parts = stage_id.split(":")
    if len(parts) < 4:
        raise ValueError(f"stage_id non riconosciuto: {stage_id}")
    return {"case_id": parts[-4], "model": parts[-3], "harness": parts[-2], "stage": parts[-1]}


def load_records(records_dir: Path) -> list[dict]:
    """Legge tutti i record `V5_RECORD_*.json` della cartella, in ordine alfabetico di nome.
    Sola lettura: non scrive e non modifica nulla."""
    return [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(Path(records_dir).glob("V5_RECORD_*.json"))]


def _clip(text: object) -> str | None:
    """Accorcia un testo (o un valore JSON) per il resoconto.

    None resta None; un valore non testuale diventa JSON; un testo piu' lungo di
    `_HEAD + _TAIL` caratteri viene ridotto a "inizio [...] fine".
    """
    if text is None:
        return None
    text = text if isinstance(text, str) else json.dumps(text, ensure_ascii=False, default=str)
    return text if len(text) <= _HEAD + _TAIL else f"{text[:_HEAD]} [...] {text[-_TAIL:]}"


def probe_k_contract(raw: object) -> str:
    """Perche' una risposta K e' stata rifiutata dal contratto (solo lettura).

    Rivalida il testo originale con il contratto V4, dando come elenco degli ID di
    evidenza ammessi quelli che la risposta stessa dichiara: cosi' un ID inventato
    non maschera altre violazioni. Se passa, l'unica causa possibile e' un ID non
    presente nei log reali dei tool. Non esegue nulla e non corregge nulla.
    """
    # Senza testo originale non c'e' nulla da rivalidare.
    if not isinstance(raw, str):
        return "risposta originale assente"
    try:
        body = json.loads(raw)
        # Gli id di evidenza che la risposta dichiara di aver usato (solo le stringhe).
        ids = body.get("evidence_ids") if isinstance(body, dict) else None
        declared = sorted({i for i in ids if isinstance(i, str)}) if isinstance(ids, list) else []
        # Rivalidazione con il contratto V4: se solleva, il messaggio e' il motivo.
        contracts.validate_candidate_rule(raw, allowed_evidence_ids=declared)
    except (ValueError, TypeError) as exc:
        return f"violazione: {exc}"
    return ("nessuna violazione con gli ID dichiarati: la causa e' un evidence_id "
            "non presente nei log reali dei tool")


def audit(records: list[dict]) -> dict:
    """Costruisce il resoconto di sola lettura sui record del run.

    Argomenti: `records` e' la lista dei record V5 (dizionari letti da `load_records`).

    Restituisce un dizionario con: versione dell'audit, numero di record, conteggio degli
    esiti (`status`), gli stage ritentati con i dettagli di ogni tentativo (`retried`), gli
    stage non completi con errore, risposta originale e sonda del contratto K
    (`non_complete`) e le deviazioni di formato per modello (`format_deviation_by_model`).
    """
    # Conteggio degli esiti sull'insieme dei record.
    status = Counter(r.get("status") for r in records)
    retried, non_complete = [], []
    deviation: dict[str, Counter] = {}
    for rec in sorted(records, key=lambda r: r["stage_id"]):
        ident = _ids(rec["stage_id"])
        fmt = rec.get("format") or {}
        # (3) Deviazione di formato registrata per questo stage, raggruppata per modello.
        deviation.setdefault(ident["model"], Counter())[fmt.get("deviation")] += 1
        # (1) Stage ritentati: piu' di un tentativo nella provenienza. Dei tentativi si
        # riportano solo i campi utili; l'errore del provider, spesso lungo, e' accorciato.
        attempts = ((rec.get("provenance") or {}).get("retry") or {}).get("attempts") or []
        if len(attempts) > 1:
            retried.append({
                "stage_id": rec["stage_id"], **ident,
                "attempts": [{k: _clip(a.get(k)) if k == "provider_error" else a.get(k)
                              for k in ("attempt", "status", "error_type", "provider_error",
                                        "api_attempts", "finish_reason", "elapsed_seconds")}
                             for a in attempts],
                "final_status": rec.get("status")})
        # (2) Stage non completi: si riportano esito, errore e risposta originale. Per gli
        # stage K con esito INVALID_OUTPUT si aggiunge la sonda del contratto, che spiega
        # perche' la risposta e' stata rifiutata.
        if rec.get("status") != COMPLETE:
            non_complete.append({
                "stage_id": rec["stage_id"], **ident, "status": rec.get("status"),
                "format_deviation": fmt.get("deviation"),
                "error_summary": _clip(rec.get("error_summary")),
                "original_response": _clip(fmt.get("original_response")),
                "contract_probe": (probe_k_contract(fmt.get("original_response"))
                                   if ident["stage"] == "K"
                                   and rec.get("status") == "INVALID_OUTPUT" else None),
                "blocked_by": rec.get("blocked_by")})
    return {
        "audit_version": VERSION, "records": len(records),
        "status": dict(sorted(status.items(), key=lambda kv: str(kv[0]))),
        "retried": retried, "non_complete": non_complete,
        "format_deviation_by_model": {m: {str(k): v for k, v in c.items()}
                                      for m, c in sorted(deviation.items())},
    }


def render(report: dict) -> str:
    """Trasforma il resoconto di `audit` in testo leggibile: stage ritentati (con ogni
    tentativo), stage non completi e deviazioni di formato per modello."""
    lines = [f"Record letti: {report['records']} | esiti: {report['status']}", "",
             f"Stage ritentati: {len(report['retried'])}"]
    for item in report["retried"]:
        lines.append(f"  - {item['stage_id']}  esito finale: {item['final_status']}")
        for a in item["attempts"]:
            lines.append(f"      tentativo {a['attempt']}: {a['status']}, errore={a['error_type']}, "
                         f"provider_error={a['provider_error']}, chiamate_api={a['api_attempts']}, "
                         f"finish={a['finish_reason']}, {a['elapsed_seconds']} s")
    lines += ["", f"Stage non completi: {len(report['non_complete'])}"]
    for item in report["non_complete"]:
        lines += [f"  - {item['stage_id']}  [{item['status']}]  formato: {item['format_deviation']}",
                  f"      error_summary: {item['error_summary']}",
                  f"      risposta originale: {item['original_response']}"]
        if item["contract_probe"]:
            lines.append(f"      sonda contratto K: {item['contract_probe']}")
        if item["blocked_by"]:
            lines.append(f"      bloccato da: {item['blocked_by']}")
    lines += ["", "Deviazioni di formato per modello:"]
    for model, counts in report["format_deviation_by_model"].items():
        lines.append(f"  {model}: {counts}")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    # Unico argomento: la cartella con i record V5 (V5_RECORD_*.json).
    print(render(audit(load_records(Path(sys.argv[1])))))
