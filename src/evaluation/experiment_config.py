from dataclasses import dataclass
from pathlib import Path
from typing import Literal
import re


# Varianti sperimentali supportate.
# A1_V2 usa il report unificato senza la sezione delle regole.
Variant = Literal["A0", "A1", "A1_V2", "A1_VERIFY", "A1_VERIFY_ST"]


@dataclass(frozen=True)
class ExperimentConfig:
    """
    Configurazione di un esperimento OpenRCA.

    La stessa configurazione e i medesimi budget sono usati da A0, A1 e A1_V2.

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

    # Provider indipendente dalla variante sperimentale.
    # Posizionato alla fine per preservare le firme posizionali storiche.
    model_provider: str = "google"

    # Default storico: nessun cambiamento alla validazione delle predizioni.
    # audit: aggiunge una diagnosi della conformita\u0027 senza modificarle.
    output_contract_mode: Literal["legacy", "audit", "structured"] = "legacy"

    # A1_VERIFY e A1_VERIFY_ST: stesso budget di 4 esplorazioni + 2 verifiche.
    # Posizionato alla fine per preservare le firme storiche.
    max_verification_checks: int = 2

    def __post_init__(self):
        """
        Verifica la validità della configurazione.
        """

        if self.variant not in ("A0", "A1", "A1_V2", "A1_VERIFY", "A1_VERIFY_ST"):
            raise ValueError("Variante non valida.")

        if not re.fullmatch(
            r"cloudbed-[12]_q\d+",
            self.case_id
        ):
            raise ValueError("Formato case_id non valido.")

        if not self.model_name.strip():
            raise ValueError("Nome modello mancante.")

        if not isinstance(self.model_provider, str) or not self.model_provider.strip():
            raise ValueError("Provider LLM mancante.")

        if self.output_contract_mode not in ("legacy", "audit", "structured"):
            raise ValueError("Modalita\u0027 output contract non valida.")

        if self.max_tool_rounds < 1:
            raise ValueError(
                "max_tool_rounds deve essere positivo."
            )

        if self.variant in ("A1_VERIFY", "A1_VERIFY_ST"):
            if (
                type(self.max_verification_checks) is not int
                or not 0 <= self.max_verification_checks < self.max_tool_rounds
            ):
                raise ValueError(
                    "A1_VERIFY richiede 0 <= max_verification_checks < max_tool_rounds"
                )
            if self.recursion_limit < 2 * self.max_tool_rounds + 5:
                raise ValueError(
                    "A1_VERIFY richiede recursion_limit maggiore per il planner"
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
        A1 e A1_V2 hanno report deterministici con percorsi distinti.

        A0 non deve ricevere questo report.
        """

        if self.variant == "A0":
            return None

        return (
            self.data_dir
            / "data/processed"
            / f"evidence_{self.variant}_v1_{self.case_id}.json"
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