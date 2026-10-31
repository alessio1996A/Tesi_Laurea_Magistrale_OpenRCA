
"""
R10 - Node Disk Write I/O Consumption.

Rileva incrementi persistenti delle operazioni di
scrittura del disco rispetto alla baseline.

Le anomalie osservate non sono root cause confermate.
Nessun utilizzo di Gemini o della ground truth.
"""

from __future__ import annotations

from ._node_rule_common import evaluate_node_signal


WRITE_RATE = "system.io.w_s"
WRITE_AWAIT = "system.io.w_await"


def valuta_r10_node_disk_write_io(
    telemetria,
    componente,
    start_unix,
    baseline_end_unix,
    end_unix,
    *,
    relative_increase: float = 0.50,
    absolute_increase: float = 5.0,
):
    """
    Analizza un incremento persistente delle scritture/s.

    WRITE_RATE: segnale principale.
    WRITE_AWAIT: informazione accessoria sulla latenza.

    Soglie esplorative, non validate sulla ground truth.
    """

    return evaluate_node_signal(
        telemetry=telemetria,
        component=componente,
        start_unix=start_unix,
        baseline_end_unix=baseline_end_unix,
        end_unix=end_unix,
        rule_id="R10",
        cls="node disk write I/O consumption",
        metric=WRITE_RATE,
        extra_metric=WRITE_AWAIT,
        relative_increase=relative_increase,
        absolute_increase=absolute_increase,
    )
