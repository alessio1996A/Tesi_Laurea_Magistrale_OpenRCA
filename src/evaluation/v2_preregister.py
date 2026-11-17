"""V2.6: prepara un piano preregistrato per 40 run, nessuna chiamata LLM.

Di default stampa una PREVIEW. Con --write crea una SOLA volta un file
versionato nella cartella data/protocols/v2, mai in cartelle V1.
Non apre Market.zip, etichette, risultati o score.
"""
# ---------------------------------------------------------------------------------------
# Guida alla lettura (e' un commento, non una docstring: la docstring qui sopra e' anche il
# testo di `--help` e quindi resta identica all'originale).
#
# Scopo
#   Trasforma la proposta di coorte di `evaluation.v2_cohort_selector` (8 incidenti, 5 varianti,
#   cioe' 40 run) in un PIANO di esecuzione preregistrato: per ogni caso l'ordine delle cinque
#   varianti (rotazione ciclica in base all'indice del caso) e gli identificativi dei run, piu'
#   tutti i parametri fissi del protocollo (modello, limiti dei tool, fuso orario). Il piano
#   e' un file JSON scritto una sola volta ("create-only") e legato al commit Git del codice.
#
# Contenuto
#   - `EXPECTED_CASES`: gli otto casi che la proposta deve contenere (gia' verificati a mano);
#   - `_overlap`: due finestre dello stesso cloudbed si sovrappongono?
#   - `build_preregistered_plan`: controlla la proposta e compone il piano (fail-closed);
#   - `_git_head_clean`: pretende un repository pulito sul ramo V2 e ne restituisce il commit;
#   - `write_plan_exclusive`: scrive il piano senza mai sovrascrivere un file esistente;
#   - `main`: interfaccia a riga di comando (preview oppure `--write`).
# ---------------------------------------------------------------------------------------
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess

from evaluation.v2_cohort_selector import (
    PROTOCOL, VARIANTS, propose_v2_cohort,
)

# Gli otto incidenti della coorte V3 (4 per cloudbed): la proposta del selettore deve
# coincidere esattamente con questo insieme, altrimenti il piano non viene prodotto.
EXPECTED_CASES = frozenset({
    "cloudbed-1_q005", "cloudbed-1_q066",
    "cloudbed-1_q027", "cloudbed-1_q013",
    "cloudbed-2_q071", "cloudbed-2_q020",
    "cloudbed-2_q034", "cloudbed-2_q024",
})


def _overlap(a: dict, b: dict) -> bool:
    """True se due casi dello STESSO cloudbed hanno finestre [start, end) che si sovrappongono.

    Qui `start_unix`/`end_unix` sono gia' numeri interi (come nella proposta); non e' la
    funzione omonima di `v2_case_window_audit`, che lavora sulle stringhe lette dal CSV.
    """
    return (
        a["cloudbed"] == b["cloudbed"]
        and a["start_unix"] < b["end_unix"]
        and b["start_unix"] < a["end_unix"]
    )


def build_preregistered_plan(proposal: dict, *, code_commit: str) -> dict:
    """Fa fail-closed se la proposta differisce da quella vista in Colab.

    Argomenti:
      proposal     dizionario prodotto da `propose_v2_cohort` (stato PROPOSED_NOT_FROZEN_NOT_EXECUTED);
      code_commit  hash Git completo (40 caratteri esadecimali) del codice che eseguira' i run.

    Restituisce il piano preregistrato (dizionario pronto per essere scritto in JSON), con
    stato `PREREGISTERED_NOT_EXECUTED`: nessuna predizione, nessun punteggio, nessuna API.
    Solleva `ValueError` se qualunque prerequisito non e' rispettato.

    Passi:
      1. controlla il formato del commit e i campi di stato della proposta;
      2. controlla i casi: esattamente gli otto attesi, 4+4 per cloudbed, sette task,
         almeno un guasto multiplo per cloudbed, finestre intere di 30 minuti e disgiunte;
      3. controlla che l'ordine delle varianti sia quello storico;
      4. assegna a ogni caso un ordine delle varianti ruotato (rotazione ciclica) e gli id
         dei 40 run (devono essere tutti distinti);
      5. compone il piano con hash della proposta e parametri fissi del protocollo.
    """
    # 1. Il commit deve essere un hash Git completo in minuscolo.
    if not re.fullmatch(r"[0-9a-f]{40}", code_commit):
        raise ValueError("Commit Git non valido")
    # La proposta deve avere esattamente lo stato e le dichiarazioni GT-free previste.
    if (
        proposal.get("status") != "PROPOSED_NOT_FROZEN_NOT_EXECUTED"
        or proposal.get("protocol") != PROTOCOL
        or proposal.get("output_contract_mode") != "v2_enforce"
        or proposal.get("case_count") != 8
        or proposal.get("planned_runs") != 40
        or proposal.get("replicas_per_case_variant") != 1
        or proposal.get("gemini_calls") != 0
        or proposal.get("read_ground_truth") is not False
        or proposal.get("read_predictions") is not False
        or proposal.get("read_scorer") is not False
    ):
        raise ValueError("Proposta V2 non conforme ai prerequisiti")
    # 2. Controlli sui casi della coorte.
    cases = proposal.get("selected_cases")
    if not isinstance(cases, list) or len(cases) != 8:
        raise ValueError("Servono esattamente otto incidenti")
    if {x["case_id"] for x in cases} != EXPECTED_CASES:
        raise ValueError("La proposta non coincide con gli otto casi verificati")
    if len({x["case_id"] for x in cases}) != 8:
        raise ValueError("ID duplicati")
    counts = Counter(x["cloudbed"] for x in cases)
    if counts != {"cloudbed-1": 4, "cloudbed-2": 4}:
        raise ValueError("Ripartizione cloudbed non 4+4")
    if {x["task_index"] for x in cases} != {
        f"task_{i}" for i in range(1, 8)
    }:
        raise ValueError("Sette task non coperte")
    for cb in counts:
        if sum(x["requested_fault_count"] >= 2
               for x in cases if x["cloudbed"] == cb) < 1:
            raise ValueError("Guasti multipli mancanti per cloudbed")
    # Finestre: istanti Unix interi (non stringhe), durata 1800 s, nessuna coppia sovrapposta.
    for i, item in enumerate(cases):
        if type(item["start_unix"]) is not int or type(item["end_unix"]) is not int:
            raise ValueError("Timestamp Unix non interi")
        if item["end_unix"] - item["start_unix"] != 1800:
            raise ValueError("Durata finestra diversa da 30 minuti")
        if any(_overlap(item, other) for other in cases[i + 1:]):
            raise ValueError("Finestre sovrapposte")
    # 3. Le cinque varianti, nell'ordine storico del protocollo.
    variant_order = tuple(proposal.get("variant_order") or ())
    if variant_order != VARIANTS:
        raise ValueError("Cinque varianti inattese")

    # 4. Rotazione ciclica: il caso i parte dalla variante i mod 5, cosi' nessuna variante
    # e' sempre la prima o l'ultima. Ogni run ha un id "protocollo__caso__variante__r01".
    plan_rows = []
    for i, item in enumerate(cases):
        rotated = list(variant_order[i % 5:] + variant_order[:i % 5])
        run_ids = [
            f"{PROTOCOL}__{item['case_id']}__{v.lower()}__r01"
            for v in rotated
        ]
        plan_rows.append({
            **item,
            "ordered_variants": rotated,
            "run_ids": run_ids,
        })
    # 8 casi x 5 varianti = 40 run, tutti con id distinto.
    all_ids = [r for item in plan_rows for r in item["run_ids"]]
    if len(all_ids) != 40 or len(set(all_ids)) != 40:
        raise ValueError("Run ID non univoci")

    # 5. Piano finale. L'hash della proposta (JSON canonico) lega il piano a quella
    # specifica proposta; il resto sono i parametri fissi del protocollo.
    return {
        "protocol": PROTOCOL,
        "status": "PREREGISTERED_NOT_EXECUTED",
        "git_commit": code_commit,
        "proposal_sha256": hashlib.sha256(
            json.dumps(proposal, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest(),
        "selection_seed": proposal["seed"],
        "selection_policy": proposal["selection_policy"],
        "split_sha256": proposal["split_sha256"],
        "manifest_sha256": proposal["manifest_sha256"],
        "network_inventory_sha256": proposal["network_inventory_sha256"],
        "model_provider": "google",
        "model_name": "gemini-3.5-flash-lite",
        "output_contract_mode": "v2_enforce",
        "max_tool_rounds": 6,
        "max_verification_checks": 2,
        "recursion_limit": 30,
        "timestamp_zone": "Asia/Shanghai",
        "telemetry_window": "[start_unix,end_unix)",
        "execution_order_policy": "cyclic_rotation_by_case_index",
        "replicas_per_case_variant": 1,
        "case_count": 8,
        "run_count": 40,
        "cases": plan_rows,
        "ground_truth_accessed": False,
        "scoring_performed": False,
        "gemini_calls": 0,
        "notes": [
            "Pre-registrazione, NON contiene predizioni o punteggi.",
            "Ablation 4+2 contro 5+1 NON inclusa.",
            "La separazione temporale non prova indipendenza statistica.",
            "Nessuna run deve partire senza consenso esplicito al costo API.",
        ],
    }


def _git_head_clean(repo_dir: Path) -> str:
    """Restituisce il commit HEAD di `repo_dir` solo se il repository e' pronto per il congelamento.

    Condizioni (altrimenti `ValueError`): nessuna modifica non committata e ramo corrente
    `feature/harness-v2-clean-2026-11-03`. Un comando Git fallito solleva
    `subprocess.CalledProcessError`.
    """
    def git(*args):
        """Esegue `git -C <repo> <args>` e restituisce l'output senza spazi finali."""
        return subprocess.run(
            ["git", "-C", str(repo_dir), *args],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
    # `status --porcelain` stampa qualcosa solo se ci sono file modificati o non tracciati.
    if git("status", "--porcelain"):
        raise ValueError("Repository Git non pulito: freeze bloccato")
    if git("branch", "--show-current") != "feature/harness-v2-clean-2026-11-03":
        raise ValueError("Branch Git diverso dalla V2")
    return git("rev-parse", "HEAD")


def write_plan_exclusive(plan: dict, destination: Path) -> Path:
    """Scrive create-only, senza alterare alcun file esistente.

    Argomenti: `plan` (il piano da salvare) e `destination` (percorso del file JSON).
    Restituisce il percorso scritto. La modalita' "x" fa fallire (`FileExistsError`) la
    scrittura se il file esiste gia': un piano congelato non si sovrascrive mai.
    """
    destination = Path(destination)
    # Crea la cartella di destinazione se manca (data/protocols/v2).
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8") as stream:
        json.dump(plan, stream, ensure_ascii=False, indent=2,
                  sort_keys=True, allow_nan=False)
        stream.write("\n")
    return destination


def main():
    """Punto d'ingresso da riga di comando.

    Senza `--write` stampa la PREVIEW del piano; con `--write` lo scrive una sola volta in
    `<data-dir>/data/protocols/v2/<PROTOCOL>_plan_v1.json` e stampa percorso, SHA-256,
    numero di run e commit.
    """
    # La descrizione di `--help` e' la docstring del modulo.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--repo-dir", required=True, type=Path)
    parser.add_argument("--write", action="store_true",
                        help="Freeze create-only dopo test e autorizzazione")
    args = parser.parse_args()
    # Repository pulito e sul ramo V2, poi proposta e piano (entrambi con controlli).
    commit = _git_head_clean(args.repo_dir)
    proposal = propose_v2_cohort(args.data_dir, args.inventory)
    plan = build_preregistered_plan(proposal, code_commit=commit)
    if args.write:
        destination = (
            args.data_dir / "data/protocols/v2" /
            f"{PROTOCOL}_plan_v1.json"
        )
        write_plan_exclusive(plan, destination)
        print(json.dumps({
            "written": str(destination),
            "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
            "run_count": plan["run_count"],
            "git_commit": commit,
        }, indent=2))
    else:
        print(json.dumps(plan, indent=2, ensure_ascii=False,
                         allow_nan=False))


if __name__ == "__main__":
    main()
