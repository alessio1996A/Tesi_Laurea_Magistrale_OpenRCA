from dataclasses import dataclass
from pathlib import Path
from typing import Literal
import re


# Varianti sperimentali supportate.
Variant = Literal["A0", "A1"]


@dataclass(frozen=True)
class ExperimentConfig:
    """
    Configurazione di un esperimento OpenRCA.

    La stessa configurazione viene utilizzata da A0 e A1.

    Non contiene:
    - chiavi API;
    - etichette dei guasti;
    - risultati attesi;
    - logica specifica di Gemini.
    """

    variant: Variant
    case_id: str

    # Parametri condivisi dai due agenti.
    model_name: str = "gemini-3.5-flash-lite"
    max_tool_rounds: int = 6
    recursion_limit: int = 30

    # Percorsi dell'ambiente Colab.
    # Sono configurabili per consentire esecuzioni future
    # anche in altri ambienti.
    repo_dir: Path = Path("/content/Tesi_OpenRCA")

    data_dir: Path = Path(
        "/content/drive/MyDrive/Tesi_OpenRCA"
    )

    def __post_init__(self):
        """
        Verifica la validità della configurazione.
        """

        if self.variant not in ("A0", "A1"):
            raise ValueError("Variante non valida.")

        if not re.fullmatch(
            r"cloudbed-[12]_q\d+",
            self.case_id
        ):
            raise ValueError("Formato case_id non valido.")

        if not self.model_name.strip():
            raise ValueError("Nome modello mancante.")

        if self.max_tool_rounds < 1:
            raise ValueError(
                "max_tool_rounds deve essere positivo."
            )

        if self.recursion_limit < 2 * self.max_tool_rounds + 2:
            raise ValueError(
                "recursion_limit insufficiente."
            )

    @property
    def manifest_path(self) -> Path:
        """
        Percorso del manifest senza ground truth.
        """

        return (
            self.data_dir
            / "data/processed/benchmark_inputs_market.csv"
        )

    @property
    def market_zip_path(self) -> Path:
        """
        Archivio originale delle metriche OpenRCA.
        """

        return self.data_dir / "Market.zip"

    @property
    def results_dir(self) -> Path:
        """
        Directory dei risultati sperimentali.
        """

        return self.data_dir / "data/results"

    @property
    def output_path(self) -> Path:
        """
        A0 e A1 salvano risultati in file distinti.
        """

        nome = self.variant.lower()

        return (
            self.results_dir
            / f"{nome}_pilot_{self.case_id}.json"
        )

    @property
    def evidence_path(self) -> Path | None:
        """
        A1 utilizza un report deterministico.

        A0 non deve ricevere questo report.
        """

        if self.variant == "A0":
            return None

        return (
            self.data_dir
            / "data/processed"
            / f"evidence_A1_v1_{self.case_id}.json"
        )


# ============================================================
# TEST LOCALE: NESSUNA CHIAMATA A GEMINI
# ============================================================

if __name__ == "__main__":

    config_a0 = ExperimentConfig(
        variant="A0",
        case_id="cloudbed-1_q009"
    )

    config_a1 = ExperimentConfig(
        variant="A1",
        case_id="cloudbed-1_q009"
    )

    # Identica configurazione del modello.
    assert config_a0.model_name == config_a1.model_name

    # Identico budget di esplorazione.
    assert (
        config_a0.max_tool_rounds
        == config_a1.max_tool_rounds
    )

    # A0 non deve utilizzare il report deterministico.
    assert config_a0.evidence_path is None

    # A1 deve possedere il percorso del report.
    assert config_a1.evidence_path is not None

    # I due agenti non devono sovrascrivere
    # i rispettivi risultati.
    assert config_a0.output_path != config_a1.output_path

    print("CONFIGURAZIONE VERIFICATA")

    print("\nA0:")
    print("Modello:", config_a0.model_name)
    print("Round:", config_a0.max_tool_rounds)
    print("Evidence:", config_a0.evidence_path)
    print("Output:", config_a0.output_path)

    print("\nA1:")
    print("Modello:", config_a1.model_name)
    print("Round:", config_a1.max_tool_rounds)
    print("Evidence:", config_a1.evidence_path)
    print("Output:", config_a1.output_path)