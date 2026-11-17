"""RQ2: verifica di integrita' e provenance dei record del run V5 (SOLA LETTURA).

Cosa controlla (nessuna scrittura, nessuna API, nessun mkdir)
-------------------------------------------------------------
Per ognuno degli stage del piano offline:
  * il record esiste al percorso atteso (hash del `stage_id`), e' JSON valido e il
    suo `record_sha256` coincide con l'hash ricalcolato con la STESSA funzione del
    runner (`_sha`), cioe' il contenuto non e' stato alterato dopo la scrittura;
  * schema, protocollo e identita' (`stage_id`, stage, caso, modello, harness)
    coincidono con quelli del piano;
  * per gli stage ESEGUITI: esiste il claim, il suo `claim_sha256` e' valido,
    `claim_sha256` del record e' lo stesso del claim, e `source_commit` di claim e
    record e' il commit congelato atteso;
  * per gli stage BLOCCATI (BLOCKED_DEPENDENCY): nessun claim, `source_commit` e
    `claim_sha256` nulli, e il genitore indicato e' davvero un genitore del piano
    con lo stato dichiarato e non completo;
  * nessuno stage e' stato eseguito con un genitore non completo;
  * nessun orfano (claim senza record) e nessun file estraneo al piano.
Riporta anche i claim rilasciati (`released_claims/log.jsonl`) e un'IMPRONTA
dell'insieme dei record (SHA-256 degli `record_sha256` ordinati), da citare nel
congelamento del protocollo.

Non decide nulla di scientifico: dice solo se i dati registrati sono quelli prodotti
dal run congelato e non sono stati toccati.

Come si usa
-----------
    python -m evaluation.rq2_k_run_integrity <cartella_archivio> [--expected-commit <hash>]
Esce con codice 0 se non ci sono violazioni, 1 altrimenti.

Contenuto
---------
- `_read_json`, `_verify_hash`, `_violation`: attrezzi di lettura, verifica dell'hash e
  registrazione di una violazione;
- `_check_identity`, `_check_blocked`: controlli sull'identita' di un record/claim e sugli
  stage bloccati;
- `check_integrity`: il controllo completo dell'archivio, restituisce il resoconto;
- `render`: il resoconto in testo; `main`: la riga di comando.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from evaluation import rq2_v5_matrix_runner as mr

VERSION = "rq2_k_run_integrity_v1"
# Commit Git del codice con cui e' stato eseguito il run congelato: ogni record e ogni
# claim deve citarlo come `source_commit`.
FROZEN_COMMIT = "ddb2ca499c4b41aa32a36fdc2f9850cb09bb75c3"
# Nome del file manifest nella cartella dell'archivio.
MANIFEST = "manifest_v1.json"
# Campi che identificano uno stage: record e claim devono coincidere con la riga del piano.
IDENTITY_FIELDS = ("stage", "case_id", "logical_model", "model_id",
                   "model_provider", "harness")


def _read_json(path: Path):
    """(payload, None) oppure (None, motivo). Non solleva mai."""
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except OSError as exc:
        return None, f"illeggibile:{type(exc).__name__}"
    except ValueError:
        return None, "json_non_valido"


def _verify_hash(payload, sha_field: str) -> str | None:
    """None se l'hash e' valido, altrimenti il motivo.

    Argomenti: `payload` (record o claim letto dal file) e `sha_field` (nome del campo che
    contiene l'hash: `record_sha256` o `claim_sha256`). L'hash si ricalcola con la STESSA
    funzione del runner (`mr._sha`) su tutto il contenuto tranne il campo dell'hash stesso.
    Motivi possibili: `non_e_un_oggetto`, `hash_assente`, `hash_non_coerente`.
    """
    if type(payload) is not dict:
        return "non_e_un_oggetto"
    if sha_field not in payload:
        return "hash_assente"
    core = {k: v for k, v in payload.items() if k != sha_field}
    if mr._sha(core) != payload[sha_field]:
        return "hash_non_coerente"
    return None


def _violation(stage_id: str, check: str, detail: str = "") -> dict:
    """Una violazione: lo stage interessato, il nome del controllo fallito e un dettaglio."""
    return {"stage_id": stage_id, "check": check, "detail": detail}


def _check_identity(stage_id: str, row: dict, payload: dict, what: str) -> list[dict]:
    """Controlla che un record o un claim abbia l'identita' prevista dal piano.

    Argomenti: `stage_id` e `row` (riga del piano), `payload` (record o claim letto),
    `what` ("record" o "claim", usato nel nome del controllo).
    Restituisce la lista delle violazioni: `stage_id` diverso, uno dei campi di
    `IDENTITY_FIELDS` diverso dalla riga del piano, protocollo diverso.
    """
    out = []
    if payload.get("stage_id") != stage_id:
        out.append(_violation(stage_id, f"{what}_stage_id_diverso",
                              str(payload.get("stage_id"))))
    for field in IDENTITY_FIELDS:
        if payload.get(field) != row[field]:
            out.append(_violation(stage_id, f"{what}_{field}_diverso",
                                  f"{payload.get(field)!r} != {row[field]!r}"))
    if payload.get("protocol") != mr.PROTOCOL:
        out.append(_violation(stage_id, f"{what}_protocollo_diverso",
                              str(payload.get("protocol"))))
    return out


def _check_blocked(stage_id: str, row: dict, record: dict,
                   parent_status: dict[str, str]) -> list[dict]:
    """Controlla un record BLOCKED_DEPENDENCY (stage mai eseguito perche' un genitore e' fallito).

    Argomenti: `stage_id` e `row` (riga del piano), `record` (il record bloccato),
    `parent_status` (esito di ogni stage letto, per ricavare quello del genitore).
    Restituisce le violazioni: uno stage bloccato non puo' avere `claim_sha256` ne'
    `source_commit` (non e' mai partito); `blocked_by` deve indicare un vero genitore del
    piano, NON completo, e con lo stesso stato che il record dichiara.
    """
    out = []
    # Uno stage mai eseguito non ha claim ne' commit di codice.
    if record.get("claim_sha256") is not None:
        out.append(_violation(stage_id, "bloccato_con_claim_sha256"))
    if record.get("source_commit") is not None:
        out.append(_violation(stage_id, "bloccato_con_source_commit"))
    # Il genitore che ha causato il blocco.
    by = record.get("blocked_by") or {}
    parent = by.get("stage_id")
    if parent not in mr.required_parents(row):
        out.append(_violation(stage_id, "bloccato_da_non_genitore", str(parent)))
    elif parent_status.get(parent) in (None, mr.STATUS_COMPLETE):
        out.append(_violation(stage_id, "bloccato_da_genitore_completo_o_assente",
                              str(parent_status.get(parent))))
    elif by.get("status") != parent_status.get(parent):
        out.append(_violation(stage_id, "stato_del_genitore_diverso",
                              f"{by.get('status')} != {parent_status.get(parent)}"))
    return out


def check_integrity(root: Path, plan_rows: list[dict], *,
                    expected_commit: str = FROZEN_COMMIT,
                    plan_preview_sha256: str | None = None) -> dict:
    """Verifica l'archivio `root` (cartella con claims/, records/, released_claims/).

    Argomenti:
      root                  cartella dell'archivio del run;
      plan_rows             righe del piano offline (una per stage);
      expected_commit       commit con cui il run doveva essere eseguito;
      plan_preview_sha256   hash dell'anteprima del piano: se dato, il manifest deve citarlo.

    Restituisce il resoconto: conteggi (stage, record e claim validi), orfani, esiti,
    `source_commit` osservati, claim rilasciati, manifest, impronta dei record, lista delle
    `violations`, `notes` informative e `ok` (True solo senza violazioni). Non scrive nulla.

    Passi:
      1. legge record e claim di ogni stage del piano e ne verifica l'hash;
      2. cerca orfani (claim senza record), record mancanti e file fuori piano;
      3. controlla stage per stage schema, identita', claim, commit e genitori;
      4. legge il registro dei claim rilasciati;
      5. controlla il manifest;
      6. calcola l'impronta dell'insieme dei record e compone il resoconto.
    """
    root = Path(root)
    claims_dir, records_dir = root / "claims", root / "records"
    released_dir = root / "released_claims"
    violations: list[dict] = []
    notes: list[str] = []

    # --- 1. lettura di tutti i record del piano (gli hash si controllano qui)
    # `records` e `claims` contengono solo i file letti e con hash valido, per stage_id.
    records: dict[str, dict] = {}
    claims: dict[str, dict] = {}
    expected_record_files, expected_claim_files = set(), set()
    for row in plan_rows:
        sid = row["stage_id"]
        # Il nome del file deriva dall'SHA-256 dello stage_id (`mr._key`).
        key = mr._key(sid)
        rec_name, claim_name = f"V5_RECORD_{key}.json", f"V5_CLAIM_{key}.json"
        expected_record_files.add(rec_name)
        expected_claim_files.add(claim_name)
        rec_path, claim_path = records_dir / rec_name, claims_dir / claim_name

        if rec_path.exists():
            payload, why = _read_json(rec_path)
            if payload is None:
                violations.append(_violation(sid, "record_non_leggibile", why))
            else:
                bad = _verify_hash(payload, "record_sha256")
                if bad:
                    violations.append(_violation(sid, "record_" + bad))
                else:
                    records[sid] = payload
        if claim_path.exists():
            payload, why = _read_json(claim_path)
            if payload is None:
                violations.append(_violation(sid, "claim_non_leggibile", why))
            else:
                bad = _verify_hash(payload, "claim_sha256")
                if bad:
                    violations.append(_violation(sid, "claim_" + bad))
                else:
                    claims[sid] = payload

    # --- 2. orfani, record mancanti, file estranei
    # Orfano = esiste il claim (lo stage e' partito) ma non il record (non e' stato chiuso).
    orphans = sorted(
        row["stage_id"] for row in plan_rows
        if (claims_dir / f"V5_CLAIM_{mr._key(row['stage_id'])}.json").exists()
        and not (records_dir / f"V5_RECORD_{mr._key(row['stage_id'])}.json").exists())
    for sid in orphans:
        violations.append(_violation(sid, "orfano_claim_senza_record"))
    for row in plan_rows:
        sid = row["stage_id"]
        if not (records_dir / f"V5_RECORD_{mr._key(sid)}.json").exists() and sid not in orphans:
            violations.append(_violation(sid, "record_mancante"))
    # File presenti nelle cartelle ma non previsti dal piano.
    present_records = {p.name for p in records_dir.glob("*")} if records_dir.is_dir() else set()
    present_claims = {p.name for p in claims_dir.glob("*")} if claims_dir.is_dir() else set()
    for name in sorted(present_records - expected_record_files):
        violations.append(_violation("(fuori piano)", "file_record_estraneo", name))
    for name in sorted(present_claims - expected_claim_files):
        violations.append(_violation("(fuori piano)", "file_claim_estraneo", name))

    # --- 3. coerenza stage per stage
    # Esito di ogni stage, per controllare lo stato dei genitori.
    status_of = {sid: rec.get("status") for sid, rec in records.items()}
    for row in plan_rows:
        sid = row["stage_id"]
        record = records.get(sid)
        # Record assente o illeggibile: la violazione e' gia' stata registrata sopra.
        if record is None:
            continue
        if record.get("schema") != mr.RECORD_SCHEMA:
            violations.append(_violation(sid, "record_schema_diverso", str(record.get("schema"))))
        violations += _check_identity(sid, row, record, "record")
        status = record.get("status")
        # Stage bloccato: non deve avere claim; i suoi controlli sono a parte.
        if status == mr.STATUS_BLOCKED:
            if sid in claims:
                violations.append(_violation(sid, "bloccato_ma_claim_presente"))
            violations += _check_blocked(sid, row, record, status_of)
            continue
        # Stage eseguito: serve il claim, con lo stesso hash citato dal record.
        claim = claims.get(sid)
        if claim is None:
            violations.append(_violation(sid, "eseguito_senza_claim", str(status)))
            continue
        if claim.get("schema") != mr.CLAIM_SCHEMA:
            violations.append(_violation(sid, "claim_schema_diverso", str(claim.get("schema"))))
        violations += _check_identity(sid, row, claim, "claim")
        if record.get("claim_sha256") != claim.get("claim_sha256"):
            violations.append(_violation(sid, "claim_sha256_del_record_diverso_dal_claim"))
        # Record e claim devono citare il commit congelato come `source_commit`.
        for name, payload in (("record", record), ("claim", claim)):
            if payload.get("source_commit") != expected_commit:
                violations.append(_violation(sid, f"{name}_source_commit_diverso",
                                             str(payload.get("source_commit"))))
        # Uno stage eseguito richiede che tutti i suoi genitori siano completi.
        for parent in mr.required_parents(row):
            if status_of.get(parent) != mr.STATUS_COMPLETE:
                violations.append(_violation(sid, "eseguito_con_genitore_non_completo",
                                             f"{parent}={status_of.get(parent)}"))

    # --- 4. claim rilasciati (registro `log.jsonl`: una riga JSON per claim rilasciato)
    released = []
    log_path = released_dir / "log.jsonl"
    if log_path.is_file():
        for line in log_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    released.append(json.loads(line))
                except ValueError:
                    violations.append(_violation("(released_claims)", "log_riga_non_valida"))
    archived = sorted(p.name for p in released_dir.glob("V5_CLAIM_*")) if released_dir.is_dir() else []
    if released or archived:
        notes.append(f"claim rilasciati: {len(released)} nel log, {len(archived)} file archiviati")

    # --- 5. manifest: deve esistere, citare il protocollo atteso e (se dato) l'anteprima del piano
    manifest_info = None
    manifest_path = root / MANIFEST
    if not manifest_path.is_file():
        violations.append(_violation("(manifest)", "manifest_assente"))
    else:
        manifest, why = _read_json(manifest_path)
        if manifest is None:
            violations.append(_violation("(manifest)", "manifest_non_leggibile", why))
        else:
            manifest_info = {k: manifest.get(k) for k in
                             ("protocol", "plan_preview_sha256", "created_commit",
                              "format_policy", "retry_policy", "runner_version")}
            if manifest.get("protocol") != mr.PROTOCOL:
                violations.append(_violation("(manifest)", "manifest_protocollo_diverso"))
            if plan_preview_sha256 and manifest.get("plan_preview_sha256") != plan_preview_sha256:
                violations.append(_violation("(manifest)", "manifest_piano_diverso",
                                             str(manifest.get("plan_preview_sha256"))))
            if manifest.get("created_commit") != expected_commit:
                notes.append("created_commit del manifest diverso dal commit congelato "
                             f"({manifest.get('created_commit')}): conta source_commit di ogni stage")

    # --- 6. sintesi
    # Impronta dell'insieme dei record: SHA-256 degli `record_sha256` ordinati e uniti da
    # a capo. Cambia se anche un solo record cambia: da citare nel congelamento.
    fingerprint = hashlib.sha256("\n".join(sorted(
        rec["record_sha256"] for rec in records.values())).encode("utf-8")).hexdigest()
    return {
        "version": VERSION,
        "expected_commit": expected_commit,
        "stages_in_plan": len(plan_rows),
        "records_valid": len(records),
        "claims_valid": len(claims),
        "orphans": orphans,
        "status_counts": dict(sorted(Counter(status_of.values()).items())),
        "source_commit_counts": dict(sorted(Counter(
            str(r.get("source_commit")) for r in records.values()).items())),
        "released_claims": released,
        "manifest": manifest_info,
        "records_fingerprint_sha256": fingerprint,
        "violations": violations,
        "notes": notes,
        "ok": not violations,
    }


def render(report: dict) -> str:
    """Trasforma il resoconto di `check_integrity` in testo: riepilogo, note, violazioni
    (una per riga: stage | controllo | dettaglio) ed esito finale."""
    lines = [f"Integrita' e provenance del run ({report['version']})",
             f"  commit congelato atteso : {report['expected_commit']}",
             f"  stage nel piano         : {report['stages_in_plan']}",
             f"  record con hash valido  : {report['records_valid']}",
             f"  claim con hash valido   : {report['claims_valid']}",
             f"  orfani                  : {len(report['orphans'])}",
             f"  esiti                   : {report['status_counts']}",
             f"  source_commit           : {report['source_commit_counts']}",
             f"  claim rilasciati        : {len(report['released_claims'])}",
             f"  impronta dei record     : {report['records_fingerprint_sha256']}"]
    if report["manifest"]:
        lines.append(f"  manifest                : {report['manifest']}")
    for note in report["notes"]:
        lines.append("  nota: " + note)
    if report["violations"]:
        lines.append(f"VIOLAZIONI ({len(report['violations'])}):")
        for v in report["violations"]:
            lines.append(f"  - {v['stage_id']} | {v['check']} | {v['detail']}")
    lines.append("ESITO: " + ("OK, nessuna violazione" if report["ok"] else "CI SONO VIOLAZIONI"))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Riga di comando: verifica l'archivio indicato e stampa il resoconto.

    Argomenti: `argv` (lista di argomenti; None usa quelli del processo).
    Restituisce 0 se non ci sono violazioni, 1 altrimenti.
    """
    # Import locali: il piano offline si costruisce solo quando si usa la riga di comando.
    import argparse

    from evaluation.rq2_v5_run_cli import _plan_rows

    # Come descrizione di `--help` si usa solo la prima riga della docstring del modulo.
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("store_root", help="cartella dell'archivio (claims/, records/, ...)")
    parser.add_argument("--expected-commit", default=FROZEN_COMMIT)
    args = parser.parse_args(argv)
    # Piano offline (stage attesi) e anteprima da confrontare con il manifest.
    plan, rows = _plan_rows()
    report = check_integrity(Path(args.store_root), rows,
                             expected_commit=args.expected_commit,
                             plan_preview_sha256=plan["preview_sha256"])
    print(render(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
