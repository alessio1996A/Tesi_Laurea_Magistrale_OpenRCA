"""R07 — node CPU load. Persistent increase only; not held-out 'node CPU spike'."""
from __future__ import annotations
from ._node_rule_common import evaluate_node_signal
CPU_USAGE = "system.cpu.pct_usage"
CPU_IOWAIT = "system.cpu.iowait"

def valuta_r07_node_cpu_load(telemetria, componente, start_unix, baseline_end_unix, end_unix, **kwargs):
    return evaluate_node_signal(
        telemetria, componente, start_unix, baseline_end_unix, end_unix,
        rule_id="R07", cls="node CPU load", metric=CPU_USAGE,
        extra_metric=CPU_IOWAIT,
        relative_increase=.20, absolute_increase=5., **kwargs)
