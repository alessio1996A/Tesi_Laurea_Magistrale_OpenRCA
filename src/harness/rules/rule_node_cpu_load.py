"""R07 - carico di CPU del nodo (classe candidata "node CPU load").

Rileva solo un aumento PERSISTENTE dell'uso di CPU rispetto alla baseline. NON e' la classe
esclusa "node CPU spike" (picco breve di CPU del nodo), che il protocollo RQ2 lascia fuori da RQ1.

Involucro sottile: la logica e' in `_node_rule_common.evaluate_node_signal`; qui si scelgono
solo il KPI principale, quello accessorio e le soglie specifiche della regola.
"""
from __future__ import annotations
from ._node_rule_common import evaluate_node_signal

# KPI principale (percentuale di CPU usata) e accessorio (percentuale di tempo in attesa di I/O).
CPU_USAGE = "system.cpu.pct_usage"
CPU_IOWAIT = "system.cpu.iowait"

def valuta_r07_node_cpu_load(telemetria, componente, start_unix, baseline_end_unix, end_unix, **kwargs):
    """Valuta R07 su un nodo: restituisce l'esito del rilevatore comune per il KPI di CPU.

    `telemetria`: tabella con colonne timestamp, cmdb_id, kpi_name, value.
    `componente`: nome del nodo (valore di cmdb_id). Finestre in secondi unix: baseline
    [start_unix, baseline_end_unix) e ricerca [baseline_end_unix, end_unix).
    Soglie fissate qui: +20% sulla mediana di baseline e +5 punti percentuali assoluti.
    `kwargs`: solo parametri di campionamento (robust_factor, consecutive, min_baseline,
    max_gap_factor); le due soglie sopra non si possono ridefinire da qui.
    """
    return evaluate_node_signal(
        telemetria, componente, start_unix, baseline_end_unix, end_unix,
        rule_id="R07", cls="node CPU load", metric=CPU_USAGE,
        extra_metric=CPU_IOWAIT,
        relative_increase=.20, absolute_increase=5., **kwargs)
