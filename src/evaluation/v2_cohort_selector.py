"""V2.5: proposta riproducibile di una NUOVA coorte GT-free, solo development.

Selezione solo dagli split+manifest originali, dai piani congelati e dal
report A/2 (network KPI inventory). Nessun log, metrica, predizione, score,
query.csv/record.csv o API. Nessun file sovrascritto. La selezione di
finestre NON e' una misura dell'indipendenza statistica degli incidenti.

Esempio:
 python -m evaluation.v2_cohort_selector --data-dir ... \
   --inventory /content/network_kpi_inventory_v1.json
"""
# ---------------------------------------------------------------------------------------
# Guida alla lettura (e' un commento, non una docstring: la docstring qui sopra e' anche il
# testo di `--help` e quindi resta identica all'originale).
#
# Scopo
#   Sceglie in modo deterministico 8 incidenti dello split `development` (4 per cloudbed)
#   che coprano tutte e sette le task e contengano almeno un guasto multiplo per cloudbed,
#   escludendo i casi gia' visti e quelli temporalmente sovrapposti a casi protetti.
#   Il risultato e' una PROPOSTA: questo modulo non scrive nulla; la preregistrazione
#   (il piano firmato dei 40 run) la prepara `evaluation.v2_preregister`.
#
# Contenuto
#   - `_rank`: ordine pseudo-casuale ma riproducibile (SHA-256 di seme e id del caso);
#   - `_select_balanced`: ricerca con backtracking della coorte bilanciata;
#   - `propose_v2_cohort`: verifica tutti i prerequisiti e restituisce la proposta (un dizionario);
#   - `main`: interfaccia a riga di comando, stampa la proposta in JSON.
# ---------------------------------------------------------------------------------------
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from evaluation.v2_case_window_audit import (
    MANIFEST_COLUMNS, MANIFEST_SHA256, PROTOCOLS,
    SPLIT_COLUMNS, SPLIT_SHA256, _overlap, _read_csv, _sha, _window,
)
from output.v2_contract import infer_requested_faults

# Nome del protocollo: compare nei piani, negli id dei run e nei nomi dei file.
PROTOCOL = "openrca_harness_v2_five_agents_development_v3"
# Seme della prima selezione V2 (in questo file non e' usato: resta per chi lo importa).
SEED = "openrca-harness-v2-five-agents-2026-11-03-v1"
# Seme con cui l'audit A/2 (network KPI inventory) ha scelto le sue quattro finestre.
AUDIT_SEED = "network-kpi-inventory-2026-11-03-v1"
# ORDINE STORICO DEL PROTOCOLLO V3 CONGELATO: NON RINOMINARE.
# I nuovi esperimenti usano agent.variant_names.VARIANTI_FINALI.
VARIANTS = ("A0", "A1_V2", "A1", "A1_VERIFY", "A1_VERIFY_ST")
# Seme della selezione bilanciata (sette task + guasti multipli): fissa l'ordine dei candidati.
BALANCED_SEED = "openrca-harness-v2-balanced-seven-tasks-2026-11-03-v1"
# Snapshot letterale di SEEN_CASE_IDS in src/evaluation/network_kpi_inventory.py
# del branch feature/r03-r05-feasibility-schema-v1.
# Include 12 piloti/coorte iniziale, 8 ST, q009 e ulteriori batch development.
HISTORICAL_SEEN = frozenset({
    "cloudbed-1_q002", "cloudbed-1_q009", "cloudbed-1_q016",
    "cloudbed-1_q034", "cloudbed-1_q035", "cloudbed-1_q036",
    "cloudbed-1_q038", "cloudbed-1_q040", "cloudbed-1_q043",
    "cloudbed-1_q052", "cloudbed-1_q063", "cloudbed-1_q065",
    "cloudbed-1_q067",
    "cloudbed-2_q006", "cloudbed-2_q007", "cloudbed-2_q012",
    "cloudbed-2_q015", "cloudbed-2_q033", "cloudbed-2_q046",
    "cloudbed-2_q053", "cloudbed-2_q055", "cloudbed-2_q066",
    "cloudbed-2_q067", "cloudbed-2_q068", "cloudbed-2_q073",
})


def _rank(seed: str, case_id: str) -> str:
    """Chiave di ordinamento pseudo-casuale ma riproducibile per un caso.

    Argomenti: `seed` (seme di selezione) e `case_id` (identificativo del caso).
    Restituisce l'SHA-256 esadecimale di "seme|case_id": stessi input, stessa chiave.
    """
    return hashlib.sha256(f"{seed}|{case_id}".encode("utf-8")).hexdigest()



def _select_balanced(eligible, manifest, per_cloudbed):
    """Selezione GT-free: tutte le sette task, 4+4 e un multi per cloudbed.

    Argomenti:
      eligible      righe dello split gia' ritenute eleggibili (casi non visti, senza
                    sovrapposizioni con casi protetti);
      manifest      dizionario case_id -> riga del manifest (istruzione e task);
      per_cloudbed  quanti casi scegliere per ciascun cloudbed.

    Restituisce la lista dei casi scelti, ordinata per cloudbed e poi per chiave di hash.
    Solleva `ValueError` se non esiste nessuna coorte che rispetti tutti i vincoli.

    Passi:
      1. controlli preliminari: il campione deve poter coprire sette task e ogni
         cloudbed deve avere abbastanza candidati e almeno un guasto multiplo;
      2. i candidati si ordinano con l'hash del seme (ordine riproducibile);
      3. ricerca con backtracking: prima un caso per ognuna delle sette task (partendo
         dalla task con meno candidati, per potare presto), poi i posti rimasti da
         qualunque task, senza superare `per_cloudbed` per cloudbed e senza finestre
         sovrapposte; la ricerca e' limitata a 200000 visite (nessun ripiego).
    """
    # (L'import e' ripetuto: `Counter` e' gia' importato in cima al file; e' innocuo.)
    from collections import Counter

    # 1. Con meno di sette posti non si possono coprire le sette task.
    if 2 * per_cloudbed < 7:
        raise ValueError("Campione troppo piccolo per sette task")
    # Ogni candidato riceve la task e il numero di guasti richiesti, ricavati dalla sola
    # istruzione ufficiale (mai da etichette o punteggi).
    ranked = []
    for row in eligible:
        info = manifest[row["case_id"]]
        n = infer_requested_faults(info["instruction"])
        if info["task_index"] not in {f"task_{i}" for i in range(1, 8)} or n is None:
            raise ValueError("Task o cardinalita' non riconosciuta")
        ranked.append({**row, "task": info["task_index"], "faults": n})
    # Per ogni cloudbed servono abbastanza finestre indipendenti e almeno un guasto multiplo.
    for cb in ("cloudbed-1", "cloudbed-2"):
        if sum(r["cloudbed"] == cb for r in ranked) < per_cloudbed:
            raise ValueError(f"Finestre development indipendenti insufficienti: {cb}")
        if not any(
            r["cloudbed"] == cb and r["faults"] >= 2 for r in ranked
        ):
            raise ValueError(f"Guasti multipli development mancanti: {cb}")
    # 2. Ordine riproducibile: hash del seme, a parita' l'id del caso.
    ranked.sort(key=lambda r: (
        hashlib.sha256(
            f"{BALANCED_SEED}|{r['case_id']}".encode()
        ).hexdigest(), r["case_id"]
    ))
    # Candidati raggruppati per task; ogni task deve averne almeno uno.
    tasks = {f"task_{i}" for i in range(1, 8)}
    groups = {t: [r for r in ranked if r["task"] == t] for t in tasks}
    if not all(groups.values()):
        raise ValueError("Sette task non disponibili")
    # Si parte dalle task con meno candidati: la ricerca fallisce (o riesce) prima.
    order = sorted(tasks, key=lambda t: (len(groups[t]), t))
    # Contatore delle visite (lista per poterlo modificare dalla funzione interna).
    visits = [0]

    def search(chosen, step):
        """Backtracking: `chosen` sono i casi gia' scelti, `step` indica la task corrente
        (0-6) oppure 7 quando le sette task sono coperte e restano posti liberi.
        Restituisce la coorte completa oppure None se questo ramo non porta a nulla."""
        visits[0] += 1
        if visits[0] > 200000:
            raise ValueError("Limite ricerca coorte: stop senza fallback")
        counts = Counter(r["cloudbed"] for r in chosen)
        # Coorte piena: vale solo se sette task sono coperte, i cloudbed sono
        # bilanciati e ognuno ha almeno un guasto multiplo.
        if len(chosen) == 2 * per_cloudbed:
            multi = Counter(
                r["cloudbed"] for r in chosen if r["faults"] >= 2
            )
            if step == 7 and all(
                counts[c] == per_cloudbed and multi[c] >= 1
                for c in ("cloudbed-1", "cloudbed-2")
            ):
                return chosen
            return None
        # Nei primi sette passi si pesca dalla task `order[step]`, poi da tutti i candidati.
        pool = groups[order[step]] if step < 7 else ranked
        for r in pool:
            # Il cloudbed e' gia' completo.
            if counts[r["cloudbed"]] >= per_cloudbed:
                continue
            # Caso gia' scelto o finestra sovrapposta a uno dei casi scelti.
            if any(r["case_id"] == x["case_id"] or _overlap(r, x)
                   for x in chosen):
                continue
            # `step + (step < 7)` avanza di uno finche' ci sono task da coprire.
            found = search(chosen + [r], step + (step < 7))
            if found is not None:
                return found
        return None

    # 3. Avvio della ricerca da coorte vuota.
    selected = search([], 0)
    if selected is None:
        raise ValueError("Nessuna coorte bilanciata senza sovrapposizioni")
    # Ordine finale stabile: per cloudbed, poi per hash del seme.
    return sorted(selected, key=lambda r: (
        r["cloudbed"],
        hashlib.sha256(
            f"{BALANCED_SEED}|{r['case_id']}".encode()
        ).hexdigest()
    ))

def propose_v2_cohort(
    data_dir: Path,
    inventory_path: Path,
    *,
    per_cloudbed: int = 4,
    verify_original_hashes: bool = True,
    historical_seen: frozenset[str] = HISTORICAL_SEEN,
) -> dict:
    """Costruisce la proposta di coorte V2 dopo aver verificato tutti i prerequisiti.

    Argomenti:
      data_dir               cartella dei dati (contiene `data/processed` e `data/protocols`);
      inventory_path         file JSON dell'inventario di rete A/2 (network KPI inventory);
      per_cloudbed           casi da scegliere per ogni cloudbed (4 -> 8 incidenti, 40 run);
      verify_original_hashes se True (consigliato) controlla gli SHA-256 e la distribuzione
                             dello split originali; False serve solo ai test con dati finti;
      historical_seen        id dei casi gia' consumati da esplorazioni precedenti.

    Restituisce un dizionario con stato `PROPOSED_NOT_FROZEN_NOT_EXECUTED`, gli SHA-256 di
    split, manifest e inventario, i casi scelti e le dichiarazioni "nessun accesso" a
    ground truth, telemetria, predizioni, scorer e API. Solleva `ValueError` al primo
    prerequisito violato (nessun ripiego silenzioso).

    Passi:
      1. valida i parametri e legge split e manifest (con controllo degli hash);
      2. controlla coerenza tra split e manifest, registro storico e distribuzione;
      3. controlla la provenienza delle due coorti V1 (otto casi, tutti gia' visti);
      4. verifica l'inventario A/2 e ne ricostruisce la selezione dal seme;
      5. determina casi visti, protetti ed eleggibili, e sceglie la coorte bilanciata;
      6. controlla che non ci siano sovrapposizioni e compone la proposta.
    """
    # 1. Parametri e file di input.
    if type(per_cloudbed) is not int or per_cloudbed < 1:
        raise ValueError("per_cloudbed deve essere positivo")
    root = Path(data_dir)
    split_path = root / "data/processed/split_market_v1.csv"
    manifest_path = root / "data/processed/benchmark_inputs_market.csv"
    split_sha, manifest_sha = _sha(split_path), _sha(manifest_path)
    # I due file devono essere esattamente quelli originali (SHA-256 congelati).
    if verify_original_hashes and (
        split_sha != SPLIT_SHA256 or manifest_sha != MANIFEST_SHA256
    ):
        raise ValueError("SHA-256 split/manifest GT-free non originali")
    split = _read_csv(split_path, SPLIT_COLUMNS)
    manifest = _read_csv(manifest_path, MANIFEST_COLUMNS)
    # 2. Coerenza tra split, manifest e registro storico.
    if set(split) != set(manifest):
        raise ValueError("Split/manifest: insieme di case_id diverso")
    if not historical_seen.issubset(split):
        raise ValueError("Registro storico cita ID non presenti nello split")
    # Distribuzione dei casi per split: 92 development, 23 evaluation, 18 quarantena, 15 OOD.
    if verify_original_hashes and dict(Counter(
        r["split"] for r in split.values()
    )) != {
        "development": 92, "evaluation": 23,
        "mixed_quarantine": 18, "ood_holdout": 15,
    }:
        raise ValueError("Distribuzione dello split incoerente")
    # Ogni riga: cloudbed valido, id coerente con il cloudbed, split e manifest concordi
    # su cloudbed e finestra, finestra Unix canonica (`_window` solleva in caso contrario).
    for case_id, row in split.items():
        if (
            row["cloudbed"] not in ("cloudbed-1", "cloudbed-2")
            or not case_id.startswith(row["cloudbed"] + "_q")
        ):
            raise ValueError(f"{case_id}: cloudbed non valido")
        if any(
            row[k] != manifest[case_id][k]
            for k in ("start_unix", "end_unix", "cloudbed")
        ):
            raise ValueError(f"{case_id}: manifest e split non concordano")
        _window(row)

    # 3. Verifica che i casi V1 non possano cadere fuori dal registro storico: per ognuno
    # dei due protocolli V1 il piano di coorte deve avere la provenienza attesa (stesso
    # protocollo, stessi hash di split e manifest) e otto coppie, tutte gia' registrate.
    for protocol in PROTOCOLS:
        plan_path = root / "data/protocols" / f"{protocol}_cohort_v1.json"
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        if (
            plan.get("protocol") != protocol
            or plan.get("split_file_sha256") != split_sha
            or plan.get("input_manifest_sha256") != manifest_sha
        ):
            raise ValueError(f"Provenienza coorte V1 incoerente: {protocol}")
        pairs = plan.get("pairs")
        if not isinstance(pairs, list) or len(pairs) != 8:
            raise ValueError(f"Coorte V1 non completa: {protocol}")
        observed = {x["case_id"] for x in pairs}
        if len(observed) != 8 or not observed.issubset(historical_seen):
            raise ValueError(f"Registro storico incompleto: {protocol}")

    # 4. A/2 deve essere un inventario realmente eseguito, non un riepilogo
    # riscritto a mano. Verifichiamo anche la selezione originale via seed.
    # Si tengono i byte grezzi: servono per calcolarne l'SHA-256 nella proposta.
    raw = Path(inventory_path).read_bytes()
    inventory = json.loads(raw.decode("utf-8"))
    # L'inventario deve dichiarare: audit e seme attesi, stessi hash di split e manifest,
    # nessuna lettura di ground truth o valori di metrica, zero chiamate al modello.
    if not isinstance(inventory, dict) or any((
        inventory.get("audit") != "network_kpi_inventory_v1",
        inventory.get("selection_seed") != AUDIT_SEED,
        inventory.get("split_sha256") != split_sha,
        inventory.get("manifest_sha256") != manifest_sha,
        inventory.get("read_ground_truth") is not False,
        inventory.get("read_metric_values") is not False,
        inventory.get("gemini_calls") != 0,
    )):
        raise ValueError("Inventario rete A/2 non coerente/GT-free")
    # Le quattro finestre scelte da A/2 e i casi di sviluppo che l'audit ha "consumato".
    network_windows = inventory.get("selected_windows")
    network_consumed = inventory.get("development_case_ids_now_seen")
    if (
        not isinstance(network_windows, list)
        or len(network_windows) != 4
        or not isinstance(network_consumed, list)
        or len(set(network_consumed)) != len(network_consumed)
    ):
        raise ValueError("Inventario A/2 non contiene le quattro finestre")

    # Reimplementiamo la scelta A/2 senza leggerne il codice al runtime.
    # Casi gia' protetti prima di A/2: tutto cio' che non e' development, piu' i casi visti.
    previously_protected = [
        row for row in split.values()
        if row["split"] != "development"
        or row["case_id"] in historical_seen
    ]
    # Candidati di A/2: casi development mai visti e senza sovrapposizioni con i protetti.
    original_candidates = [
        row for row in split.values()
        if row["split"] == "development"
        and row["case_id"] not in historical_seen
        and not any(_overlap(row, other) for other in previously_protected)
    ]
    # Per ogni cloudbed si prendono, in ordine di hash del seme di A/2, le prime due
    # finestre che non si sovrappongono alle gia' scelte.
    expected_a2 = []
    for cb in ("cloudbed-1", "cloudbed-2"):
        chosen = []
        for row in sorted(
            (r for r in original_candidates if r["cloudbed"] == cb),
            key=lambda r: (_rank(AUDIT_SEED, r["case_id"]), r["case_id"]),
        ):
            if not any(_overlap(row, old) for old in chosen):
                chosen.append(row)
            if len(chosen) == 2:
                break
        if len(chosen) != 2:
            raise ValueError("Non posso ricostruire la selezione A/2")
        expected_a2.extend(chosen)
    # Confronto tra le finestre dichiarate dall'inventario e quelle ricostruite dal seme,
    # sui soli campi identificativi (in ordine e come stringhe).
    canonical_keys = ("case_id", "cloudbed", "start_unix", "end_unix", "split")
    def canonical(row):
        """Forma canonica di una riga: tupla di stringhe nei campi di `canonical_keys`."""
        return tuple(str(row.get(k)) for k in canonical_keys)
    if (
        [canonical(x) for x in network_windows]
        != [canonical(x) for x in expected_a2]
    ):
        raise ValueError("Finestre A/2 non riproducibili dal seed")
    # Casi development "consumati" da A/2: quelli che si sovrappongono alle sue finestre.
    actual_consumed = sorted(
        row["case_id"] for row in split.values()
        if row["split"] == "development"
        and any(_overlap(row, win) for win in expected_a2)
    )
    if sorted(network_consumed) != actual_consumed:
        raise ValueError("Il registro consumato dall'audit A/2 non coincide")

    # 5. Casi visti = storico + consumati da A/2; protetti = non development oppure visti;
    # eleggibili = development non visti e senza sovrapposizioni con i protetti.
    seen = historical_seen | frozenset(actual_consumed)
    protected = [
        row for row in split.values()
        if row["split"] != "development" or row["case_id"] in seen
    ]
    eligible = [
        row for row in split.values()
        if row["split"] == "development"
        and row["case_id"] not in seen
        and not any(_overlap(row, old) for old in protected)
    ]
    selected = _select_balanced(eligible, manifest, per_cloudbed)
    # 6. Controllo finale: nessuna coppia di casi scelti con finestre sovrapposte.
    if any(
        _overlap(a, b)
        for i, a in enumerate(selected) for b in selected[i + 1:]
    ):
        raise ValueError("La nuova coorte contiene intervalli sovrapposti")
    # Righe della proposta: solo metadati pubblici (finestra, task, guasti richiesti).
    selected_rows = []
    for row in selected:
        case_id = row["case_id"]
        expected = infer_requested_faults(manifest[case_id]["instruction"])
        if expected is None:
            raise ValueError(f"Cardinalita' task sconosciuta: {case_id}")
        selected_rows.append({
            "case_id": case_id, "cloudbed": row["cloudbed"],
            "start_unix": int(row["start_unix"]),
            "end_unix": int(row["end_unix"]),
            "task_index": manifest[case_id]["task_index"],
            "requested_fault_count": expected,
        })
    return {
        # Identita' e stato: la proposta NON e' congelata e NON e' stata eseguita.
        "protocol": PROTOCOL,
        "status": "PROPOSED_NOT_FROZEN_NOT_EXECUTED",
        "seed": BALANCED_SEED,
        "selection_policy": "seven_tasks_and_multifault_per_cloudbed_v1",
        # Copertura raggiunta: task presenti e guasti multipli per cloudbed.
        "task_coverage": sorted({x["task"] for x in selected}),
        "multi_fault_cases_per_cloudbed": dict(sorted(Counter(
            x["cloudbed"] for x in selected if x["faults"] >= 2
        ).items())),
        # Provenienza: hash dei tre file di ingresso e registri dei casi gia' usati.
        "split_sha256": split_sha,
        "manifest_sha256": manifest_sha,
        "network_inventory_sha256": hashlib.sha256(raw).hexdigest(),
        "historical_case_ids": sorted(historical_seen),
        "network_audit_consumed_case_ids": actual_consumed,
        # Coorte proposta e piano di esecuzione (5 varianti x casi x 1 replica).
        "selected_cases": selected_rows,
        "case_count": len(selected_rows),
        "per_cloudbed": per_cloudbed,
        "variant_order": list(VARIANTS),
        "output_contract_mode": "v2_enforce",
        "replicas_per_case_variant": 1,
        "planned_runs": len(selected_rows) * len(VARIANTS),
        # Dichiarazioni GT-free: nulla e' stato letto o chiamato.
        "read_ground_truth": False,
        "read_telemetry": False,
        "read_predictions": False,
        "read_scorer": False,
        "gemini_calls": 0,
        "files_written": False,
        "limitations": [
            "Finestre separate non provano indipendenza causale/statistica.",
            "La selezione e' una PROPOSTA, non preregistrazione firmata.",
            "Nessun risultato su questa coorte e' stato ancora prodotto.",
            "Il registro storico necessita conferma delle altre possibili esplorazioni.",
        ],
    }


def main() -> None:
    """Punto d'ingresso da riga di comando: stampa la proposta di coorte in JSON.

    Opzioni: `--data-dir` (cartella dei dati), `--inventory` (inventario A/2) e
    `--per-cloudbed` (casi per cloudbed, 4 di default). Non scrive nessun file.
    """
    # La descrizione di `--help` e' la docstring del modulo.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--per-cloudbed", type=int, default=4)
    args = parser.parse_args()
    proposal = propose_v2_cohort(
        args.data_dir, args.inventory, per_cloudbed=args.per_cloudbed,
    )
    print(json.dumps(proposal, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
