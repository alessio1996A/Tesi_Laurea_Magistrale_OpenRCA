"""R08 — node memory consumption. Observational usage shift, not OOM proof."""
from __future__ import annotations
from ._node_rule_common import evaluate_node_signal
MEM_PCT = "system.mem.pct_usage"
MEM_USED = "system.mem.used"

def valuta_r08_node_memory(telemetria, componente, start_unix, baseline_end_unix, end_unix, **kwargs):
    return evaluate_node_signal(
        telemetria, componente, start_unix, baseline_end_unix, end_unix,
        rule_id="R08", cls="node memory consumption", metric=MEM_PCT,
        extra_metric=MEM_USED,
        relative_increase=.10, absolute_increase=3., **kwargs)
