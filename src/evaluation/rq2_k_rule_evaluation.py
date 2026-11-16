"""RQ2-K: valutazione CON riferimento di una regola K gia' eseguita (processo GT-only).

Questo modulo e' il solo punto in cui le etichette incontrano i risultati
dell'esecutore. Va usato in un processo SEPARATO, dopo che le decisioni di gruppo
sono state salvate (con hash) e il protocollo e' congelato. Non e' un modulo
dell'esecutore e non deve essere importato da nulla che giri prima dello scoring.

Cosa calcola, per una regola R associata alla classe c
------------------------------------------------------
  * conteggi per gruppo temporale (TP, FP, TN, FN, astensioni, errori, gruppi non
    valutabili) riusando `rq2_rule_group_scorer.evaluate_group_decisions`;
  * localizzazione e tempo sui gruppi rilevati: il componente di riferimento deve
    essere tra quelli su cui R scatta e il suo PRIMO scatto deve cadere in
    [t_gt - H_pre, t_gt + H] (H_pre e H: parametri di questa verifica, in secondi);
  * copertura decisionale su positivi e negativi;
  * intervalli esatti di Clopper-Pearson (95 %) per k su n.

Verdetti (protocollo K, proposta)
---------------------------------
  NON_VERIFICATA            almeno un FN, o un FP, o un rilevamento non localizzato;
  NON_VALUTABILE            nessun FN/FP osservato ma copertura insufficiente
                            (astensioni o errori sui positivi, negativi coperti meno
                            di `negative_coverage_min`, nessun gruppo positivo);
  VERIFICATA_OPERATIVAMENTE tutto il resto. Vale SUL CAMPIONE osservato: niente
                            affermazione di generalizzazione.
Un FP o un FN osservato prevale sulla copertura: e' una prova, non una lacuna.
La soglia 2/3 sui negativi e' un criterio ESPLORATIVO dichiarato.

Popolazione (esecutore v2, decisione approvata il 16 nov)
---------------------------------------------------------
L'esecutore valuta solo i componenti che espongono tutti i KPI della regola. Se il
componente di RIFERIMENTO di un gruppo positivo e' fuori dalla popolazione, quel positivo e'
NON_VALUTABILE: esce dai denominatori di TP/FN, viene contato e nominato a parte, e non
vale come FN. Un negativo (TN) vale SOLO per i componenti osservabili: la copertura della
popolazione e' riportata e non se ne trae nessuna conclusione sull'intero livello.
"""
from __future__ import annotations

from math import comb

from evaluation.rq2_rule_group_scorer import evaluate_group_decisions

VERSION = "rq2_k_rule_evaluation_v2"
VERIFIED = "VERIFICATA_OPERATIVAMENTE"
NOT_VERIFIED = "NON_VERIFICATA"
NOT_EVALUABLE = "NON_VALUTABILE"
NEGATIVE_COVERAGE_MIN = 2 / 3     # esplorativa

_SCORER_KEYS = ("group_id", "case_ids", "fault_types", "reference_complete")


def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> tuple[float | None, float | None]:
    """Intervallo esatto di Clopper-Pearson bilaterale, per bisezione (solo stdlib)."""
    if n <= 0:
        return None, None

    def upper_tail(p: float) -> float:        # P[X >= k]
        return sum(comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k, n + 1))

    def lower_tail(p: float) -> float:        # P[X <= k]
        return sum(comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(0, k + 1))

    def bisect(fn, target, increasing):
        lo, hi = 0.0, 1.0
        for _ in range(80):
            mid = (lo + hi) / 2
            if (fn(mid) < target) == increasing:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2

    lower = 0.0 if k == 0 else bisect(upper_tail, alpha / 2, increasing=True)
    upper = 1.0 if k == n else bisect(lower_tail, alpha / 2, increasing=False)
    return lower, upper


def _localization(group: dict, result: dict, target: str, h_pre: int, h: int) -> dict:
    """Esito di localizzazione per un gruppo rilevato (decisione 'positive')."""
    fires = result.get("first_fire_unix_by_component") or {}
    faults = [f for f in group["faults"] if f["fault_type"] == target]
    outcomes, located = [], set()
    for fault in faults:
        first = fires.get(fault["component"])
        if first is None:
            outcomes.append("component_not_firing")
        elif not (fault["t_gt"] - h_pre <= first <= fault["t_gt"] + h):
            outcomes.append("time_out_of_window")
        else:
            outcomes.append("ok")
            located.add(fault["component"])
    return {
        "faults_checked": len(faults),
        "all_located": bool(faults) and all(o == "ok" for o in outcomes),
        "outcomes": outcomes,
        "other_components_firing": len(set(fires) - located),
    }


def evaluate_rule(*, target_fault_type: str, known_fault_types: tuple[str, ...],
                  group_references: list[dict], group_results: dict[str, dict],
                  h_pre_seconds: int, h_seconds: int,
                  negative_coverage_min: float = NEGATIVE_COVERAGE_MIN,
                  rules_tested: int | None = None) -> dict:
    """Valuta UNA regola. `group_results[group_id]` e' l'esito di `execute_rule`
    (o {"decision": "error"}); `group_references` contiene anche `faults`."""
    if not (type(h_pre_seconds) is int and type(h_seconds) is int
            and h_pre_seconds >= 0 and h_seconds > 0):
        raise ValueError("H_pre e H devono essere interi in secondi (H > 0)")
    by_id = {g["group_id"]: g for g in group_references}
    for group in group_references:
        if not set(f["fault_type"] for f in group["faults"]) <= set(group["fault_types"]):
            raise ValueError(f"Guasti incoerenti con le classi del gruppo {group['group_id']}")

    decisions = {gid: (group_results.get(gid) or {"decision": "error"}).get("decision", "error")
                 for gid in by_id}

    # Positivi il cui componente di riferimento e' fuori dalla popolazione: NON_VALUTABILE.
    not_observable: dict[str, list[str]] = {}
    for gid, group in by_id.items():
        if (group["reference_complete"] and target_fault_type in group["fault_types"]
                and decisions[gid] != "error"):
            result = group_results[gid]
            if "population" not in result:
                raise ValueError(f"Risultato senza popolazione (esecutore < v2): gruppo {gid}")
            population = set(result["population"])
            missing = sorted({f["component"] for f in group["faults"]
                              if f["fault_type"] == target_fault_type
                              and f["component"] not in population})
            if missing:
                not_observable[gid] = missing

    def _reference(g: dict) -> dict:
        record = {k: g[k] for k in _SCORER_KEYS}
        if g["group_id"] in not_observable:
            record["reference_complete"] = False          # fuori dai denominatori
        return record

    scorer = evaluate_group_decisions(
        target_fault_type=target_fault_type, known_fault_types=known_fault_types,
        group_references=[_reference(g) for g in group_references],
        group_decisions=decisions)
    counts = dict(scorer["counts"])
    counts["reference_unscorable_groups"] -= len(not_observable)     # solo GT davvero incompleta
    counts["positive_groups_reference_not_observable"] = len(not_observable)

    # Localizzazione sui soli gruppi positivi per la classe, completi e rilevati.
    localization = {}
    for gid, group in by_id.items():
        if (group["reference_complete"] and gid not in not_observable
                and target_fault_type in group["fault_types"] and decisions[gid] == "positive"):
            localization[gid] = _localization(
                group, group_results[gid], target_fault_type, h_pre_seconds, h_seconds)
    tp_localized = sum(1 for v in localization.values() if v["all_located"])

    positives = counts["complete_positive_groups"]
    negatives = counts["complete_negative_groups"]
    pos_hard = counts["tp"] + counts["fn"]
    neg_hard = counts["tn"] + counts["fp"]
    coverage_pos = pos_hard / positives if positives else None
    coverage_neg = neg_hard / negatives if negatives else None

    reasons = []
    if counts["fn"]:
        reasons.append("false_negative")
    if counts["fp"]:
        reasons.append("false_positive")
    if counts["tp"] and tp_localized < counts["tp"]:
        reasons.append("detected_but_not_localized_or_timed")
    if reasons:
        verdict = NOT_VERIFIED
    else:
        gaps = []
        if positives == 0:
            gaps.append("no_complete_positive_group")
            if not_observable:
                gaps.append("reference_component_not_observable")
        if counts["abstain_positive"] or counts["error_positive"]:
            gaps.append("abstention_or_error_on_positives")
        if negatives == 0 or (coverage_neg is not None and coverage_neg < negative_coverage_min):
            gaps.append("negative_coverage_below_exploratory_threshold")
        verdict, reasons = (NOT_EVALUABLE, gaps) if gaps else (VERIFIED, [])

    def _coverage_min(group_ids) -> float | None:
        values = [group_results[g]["population_coverage"] for g in group_ids
                  if g in group_results and group_results[g].get("population_coverage") is not None]
        return min(values) if values else None

    negative_ids = [gid for gid, g in by_id.items()
                    if g["reference_complete"] and target_fault_type not in g["fault_types"]
                    and decisions[gid] in ("negative", "positive")]
    positive_ids = [gid for gid, g in by_id.items()
                    if g["reference_complete"] and target_fault_type in g["fault_types"]
                    and gid not in not_observable and decisions[gid] in ("negative", "positive")]
    evaluable_positive_fraction = (positives / (positives + len(not_observable))
                                   if (positives + len(not_observable)) else None)

    recall_k = tp_localized
    return {
        "evaluation_version": VERSION, "verdict": verdict, "reasons": reasons,
        "target_fault_type": target_fault_type,
        "counts": counts,
        "detection": {"tp": counts["tp"], "fn": counts["fn"], "positives_complete": positives,
                      "tp_localized": tp_localized,
                      "interval95_localized_over_positives": clopper_pearson(recall_k, positives)},
        "false_positives": {"fp": counts["fp"], "negatives_complete": negatives,
                            "interval95": clopper_pearson(counts["fp"], negatives)},
        "coverage": {"positives": coverage_pos, "negatives": coverage_neg,
                     "negative_threshold_exploratory": negative_coverage_min,
                     "abstain_positive": counts["abstain_positive"],
                     "abstain_negative": counts["abstain_negative"],
                     "error_positive": counts["error_positive"],
                     "error_negative": counts["error_negative"],
                     "unscorable_groups": counts["reference_unscorable_groups"]},
        "positives_not_observable": {"groups": not_observable, "count": len(not_observable),
                                     "evaluable_positive_fraction": evaluable_positive_fraction},
        "population": {"negative_groups_coverage_min": _coverage_min(negative_ids),
                       "positive_groups_coverage_min": _coverage_min(positive_ids)},
        "localization_by_group": localization,
        "parameters": {"h_pre_seconds": h_pre_seconds, "h_seconds": h_seconds},
        "rules_tested": rules_tested,
        "caveat": ("Verdetto SUL CAMPIONE osservato; nessuna generalizzazione. Un negativo "
                   "vale per i soli componenti osservabili (popolazione), non per l'intero "
                   "livello; i positivi con riferimento non osservabile sono NON_VALUTABILI e "
                   "riportati a parte. Con molte regole in prova un esito perfetto puo' essere "
                   "casuale: riportare rules_tested."),
    }
