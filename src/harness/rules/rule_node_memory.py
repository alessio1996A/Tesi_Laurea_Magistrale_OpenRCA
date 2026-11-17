"""R08 - consumo di memoria del nodo (classe candidata "node memory consumption").

Rileva uno spostamento PERSISTENTE della percentuale di memoria usata rispetto alla baseline.
E' un'osservazione sull'uso, NON la prova di un esaurimento di memoria (OOM).

Involucro sottile: la logica e' in `_node_rule_common.evaluate_node_signal`.
"""
from __future__ import annotations
from ._node_rule_common import evaluate_node_signal

# KPI principale (percentuale di memoria usata) e accessorio (memoria usata in valore assoluto).
MEM_PCT = "system.mem.pct_usage"
MEM_USED = "system.mem.used"

def valuta_r08_node_memory(telemetria, componente, start_unix, baseline_end_unix, end_unix, **kwargs):
    """Valuta R08 su un nodo: restituisce l'esito del rilevatore comune per il KPI di memoria.

    Argomenti come in R07. Soglie fissate qui: +10% sulla mediana di baseline e +3 punti
    percentuali assoluti. `kwargs`: solo parametri di campionamento (robust_factor, consecutive,
    min_baseline, max_gap_factor).
    """
    return evaluate_node_signal(
        telemetria, componente, start_unix, baseline_end_unix, end_unix,
        rule_id="R08", cls="node memory consumption", metric=MEM_PCT,
        extra_metric=MEM_USED,
        relative_increase=.10, absolute_increase=3., **kwargs)
