"""R11 — node disk space consumption, NOT disk read/write I/O.

Detects sustained increase in occupied disk percentage relative to the provided
reference window; it does not claim the disk is full or I/O is saturated.
"""
from __future__ import annotations
from ._node_rule_common import evaluate_node_signal
DISK_PCT = "system.disk.pct_usage"
DISK_USED = "system.disk.used"

def valuta_r11_node_disk_space(telemetria, componente, start_unix, baseline_end_unix, end_unix, **kwargs):
    return evaluate_node_signal(
        telemetria, componente, start_unix, baseline_end_unix, end_unix,
        rule_id="R11", cls="node disk space consumption", metric=DISK_PCT,
        extra_metric=DISK_USED,
        relative_increase=.03, absolute_increase=1., **kwargs)
