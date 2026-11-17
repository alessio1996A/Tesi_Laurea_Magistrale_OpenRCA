"""RQ2-K: inventario delle regole candidate rispetto al catalogo dei KPI (solo lettura).

Senza etichette, senza telemetria, senza chiamate API. Per ogni regola `candidate`
dice quali KPI cita, se esistono nel catalogo dei 4 incidenti di scoperta e a quale
livello (node/container), e per ogni caso quanti componenti del livello hanno quel
KPI. "Supportata dal catalogo" vuol dire SOLO che i nomi esistono: l'esecuzione sui
dati reali dira' il resto. Non assegna classi: la tabella famiglia-classe e' una
decisione di protocollo ancora da approvare.

Come si usa
-----------
    python -m evaluation.rq2_k_rule_inventory <cartella_record_V5> <catalogo.json>
dove il catalogo e' il file `catalog_discovery.json` scritto da `evaluation.rq2_k_catalog`. Stampa, per ogni regola
candidata proposta dall'agente nello stadio K, le metriche citate e dove esistono.

Contenuto
---------
- `rule_metrics`: nomi delle metriche citate dalle condizioni di una regola;
- `inventory_entry`: confronto di una regola con il catalogo (livelli e copertura per caso);
- `inventory`: lo stesso, per tutte le regole candidate;
- `render`: testo leggibile del risultato.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from evaluation import rq2_k_records as rk

VERSION = "rq2_k_rule_inventory_v1"


def rule_metrics(rule: dict) -> list[str]:
    """Nomi (ordinati, senza duplicati) delle metriche citate dalle condizioni di una regola.

    Argomenti: `rule` e' la regola candidata (dizionario con una lista `conditions`).
    Le condizioni malformate (non dizionari, o con `metric` che non e' una stringa) si ignorano.
    """
    return sorted({c["metric"] for c in rule.get("conditions") or []
                   if isinstance(c, dict) and isinstance(c.get("metric"), str)})


def inventory_entry(entry: dict, catalog: dict) -> dict:
    """Confronta UNA regola candidata con il catalogo dei KPI.

    Argomenti:
      entry    voce K letta da `rq2_k_records` (con `stage_id`, `case_id`, `model`, `harness`, `rule`);
      catalog  catalogo dei KPI (`aggregate`: livello -> KPI; `per_case`: per caso, componenti
               per livello e statistiche per metrica).

    Restituisce un dizionario con l'identita' della regola, la sua ipotesi di guasto, il
    giudizio `support` e, per ogni metrica, i livelli in cui esiste e i casi che la contengono.
    `support` vale `metrica_non_nel_catalogo` (nessuna metrica, o una non presente),
    `livelli_misti` (metriche su livelli diversi) oppure `nomi_presenti_a_livello_<livello>`.
    """
    # Per ogni metrica citata: in quali livelli (node/container) compare e, per ogni caso,
    # quanti componenti di quel livello la misurano.
    metrics, levels_seen = {}, set()
    for metric in rule_metrics(entry["rule"]):
        levels = sorted(level for level, kpis in catalog["aggregate"].items() if metric in kpis)
        per_case = {}
        for case_id, info in catalog["per_case"].items():
            for level in levels:
                stats = info["levels"].get(level, {}).get(metric)
                if stats:
                    per_case[case_id] = {"level": level, "with_metric": stats["components"],
                                         "components_total": info["components_total"][level]}
        metrics[metric] = {"levels": levels, "per_case": per_case}
        levels_seen.update(levels)
    # Giudizio sintetico: basta una metrica assente dal catalogo per dire "non nel catalogo".
    if not metrics or any(not m["levels"] for m in metrics.values()):
        support = "metrica_non_nel_catalogo"
    elif len(levels_seen) > 1:
        support = "livelli_misti"
    else:
        support = f"nomi_presenti_a_livello_{next(iter(levels_seen))}"
    return {"stage_id": entry["stage_id"], "case_id": entry["case_id"], "model": entry["model"],
            "harness": entry["harness"], "rule_name": entry["rule"].get("rule_name"),
            "hypothesized_fault_type": entry["rule"].get("hypothesized_fault_type"),
            "support": support, "metrics": metrics}


def inventory(entries: list[dict], catalog: dict) -> list[dict]:
    """Inventario di tutte le regole con esito `candidate` (le altre voci K si saltano)."""
    return [inventory_entry(e, catalog) for e in entries if e["outcome"] == "candidate"]


def render(items: list[dict]) -> str:
    """Testo leggibile dell'inventario: una sezione per regola, con le metriche e la
    copertura per caso ("componenti del livello che hanno il KPI")."""
    lines = [f"Regole candidate: {len(items)}"]
    for it in items:
        lines += ["-" * 60, f"{it['case_id']} {it['model']} {it['harness']}",
                  f"  regola: {it['rule_name']}", f"  supporto catalogo: {it['support']}"]
        for metric, info in it["metrics"].items():
            lines.append(f"  metrica: {metric}  livelli: {info['levels'] or 'nessuno'}")
            for case_id, c in sorted(info["per_case"].items()):
                lines.append(f"      {case_id}: {c['with_metric']}/{c['components_total']} "
                             f"componenti {c['level']} con il KPI")
    return "\n".join(lines)


if __name__ == "__main__":
    # Argomenti: 1) cartella dei record V5, 2) file JSON del catalogo dei KPI.
    entries = rk.load_k_entries(Path(sys.argv[1]))
    print(render(inventory(entries, json.loads(Path(sys.argv[2]).read_text(encoding="utf-8")))))
