
"""
R09 - Consumo di I/O di lettura del disco di un nodo (classe "node disk read I/O consumption").

Rileva aumenti persistenti delle operazioni di lettura
rispetto alla baseline del nodo.

Il risultato e' un'ipotesi osservativa, NON una root cause
confermata.

Non utilizza ground truth, Gemini o etichette Market.

Involucro sottile: la logica e' in `_node_rule_common.evaluate_node_signal`.
"""

from __future__ import annotations

from ._node_rule_common import evaluate_node_signal


# KPI principali del detector: letture al secondo (segnale che decide) e kB/s letti (solo accessorio).
READ_RATE = "system.io.r_s"
READ_THROUGHPUT = "system.io.rkb_s"


def valuta_r09_node_disk_read_io(
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
    Rileva un incremento persistente delle letture/s.

    READ_RATE: segnale principale.
    READ_THROUGHPUT: evidenza accessoria.

    Le soglie sono provvisorie e non calibrate
    sulla ground truth.

    Argomenti come in R07. Qui le due soglie si possono ridefinire (default: +50% sulla
    mediana di baseline e +5 letture/s assolute); i parametri di campionamento restano
    quelli di default del rilevatore comune (3 campioni consecutivi, minimo 8 in baseline).
    """

    # Si passano gli argomenti per nome al rilevatore comune, che fa tutto il calcolo.
    return evaluate_node_signal(
        telemetry=telemetria,
        component=componente,
        start_unix=start_unix,
        baseline_end_unix=baseline_end_unix,
        end_unix=end_unix,
        rule_id="R09",
        cls="node disk read I/O consumption",
        metric=READ_RATE,
        extra_metric=READ_THROUGHPUT,
        relative_increase=relative_increase,
        absolute_increase=absolute_increase,
    )
