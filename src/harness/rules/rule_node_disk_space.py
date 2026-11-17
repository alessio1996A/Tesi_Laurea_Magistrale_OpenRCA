"""R11 - consumo di SPAZIO su disco del nodo (classe "node disk space consumption"), NON I/O di lettura/scrittura.

Rileva un aumento sostenuto della percentuale di disco occupata rispetto alla finestra di
riferimento indicata dal chiamante. Non afferma che il disco sia pieno ne' che l'I/O sia saturo.

Involucro sottile: la logica e' in `_node_rule_common.evaluate_node_signal`.
"""
from __future__ import annotations
from ._node_rule_common import evaluate_node_signal

# KPI principale (percentuale di disco occupata) e accessorio (spazio occupato in valore assoluto).
DISK_PCT = "system.disk.pct_usage"
DISK_USED = "system.disk.used"

def valuta_r11_node_disk_space(telemetria, componente, start_unix, baseline_end_unix, end_unix, **kwargs):
    """Valuta R11 su un nodo: restituisce l'esito del rilevatore comune per lo spazio su disco.

    Argomenti come in R07. Soglie fissate qui, piu' basse di quelle delle altre regole:
    +3% sulla mediana di baseline e +1 punto percentuale assoluto.
    `kwargs`: solo parametri di campionamento (robust_factor, consecutive, min_baseline,
    max_gap_factor).
    """
    return evaluate_node_signal(
        telemetria, componente, start_unix, baseline_end_unix, end_unix,
        rule_id="R11", cls="node disk space consumption", metric=DISK_PCT,
        extra_metric=DISK_USED,
        relative_increase=.03, absolute_increase=1., **kwargs)
