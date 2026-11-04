from dataclasses import dataclass
from pathlib import Path
from typing import Literal
import re


# Nomi operativi finali e identificativi legacy dei risultati V3.
from agent.variant_names import variante_canonica

Variant = Literal["A0", "A1", "A1_8R", "A1_8R_Planning", "A1_PAVE"]
HistoricalVariant = Literal["A0", "A1_V2", "A1", "A1_VERIFY", "A1_VERIFY_ST"]


@dataclass(frozen=True)
class ExperimentConfig:
    """
    Configurazione di un esperimento OpenRCA.

    Le cinque varianti condividono modello e budget totale di tool.
    La nomenclatura 'historic_v3' va dichiarata per leggere i vecchi piani:
    il vecchio 'A1' include le otto regole; il nuovo 'A1' non le include.

    Non contiene:
    - chiavi API;
    - etichette dei guasti;
    - risultati attesi;
    - logica specifica di Gemini.
    """

    variant: Variant | HistoricalVariant
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
    output_contract_mode: Literal["legacy", "audit", "structured", "v2_audit", "v2_enforce"] = "legacy"

    # A1_VERIFY e A1_VERIFY_ST: stesso budget di 4 esplorazioni + 2 verifiche.
    # Posizionato alla fine per preservare le firme storiche.
    max_verification_checks: int = 2

    # Le nuove run utilizzano i nomi finali. I piani già congelati,
    # che contengono stringhe potenzialmente ambigue, usano historic_v3.
    variant_scheme: Literal["current", "historic_v3"] = "current"

    @property
    def canonical_variant(self) -> str:
        """Etichetta finale utilizzata dalle scelte logiche del runner."""
        return variante_canonica(self.variant, schema=self.variant_scheme)

    def __post_init__(self):
        """
        Verifica la validità della configurazione.
        """

        # 'A1' significa cose diverse nei due schemi: niente auto-detection.
        _ = self.canonical_variant

        if not re.fullmatch(
            r"cloudbed-[12]_q\d+",
            self.case_id
        ):
            raise ValueError("Formato case_id non valido.")

        if not self.model_name.strip():
            raise ValueError("Nome modello mancante.")

        if not isinstance(self.model_provider, str) or not self.model_provider.strip():
            raise ValueError("Provider LLM mancante.")

        if self.output_contract_mode not in ("legacy", "audit", "structured", "v2_audit", "v2_enforce"):
            raise ValueError("Modalita\u0027 output contract non valida.")

        if self.max_tool_rounds < 1:
            raise ValueError(
                "max_tool_rounds deve essere positivo."
            )

        if self.canonical_variant in ("A1_8R_Planning", "A1_PAVE"):
            if (
                type(self.max_verification_checks) is not int
                or not 0 <= self.max_verification_checks < self.max_tool_rounds
            ):
                raise ValueError(
                    "Planning/PAVE richiedono 0 <= max_verification_checks < max_tool_rounds"
                )
            if self.recursion_limit < 2 * self.max_tool_rounds + 5:
                raise ValueError(
                    "Planning/PAVE richiedono recursion_limit maggiore per il planner"
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
        destinazione = (
            self.results_dir / "final_names_v1"
            if self.variant_scheme == "current"
            else self.results_dir
        )
        return destinazione / f"{nome}_pilot_{self.case_id}.json"

    @property
    def evidence_path(self) -> Path | None:
        """
        Le varianti diverse da A0 hanno report deterministici distinti.
        I file dei nuovi esperimenti restano separati da quelli storici.
        """

        if self.canonical_variant == "A0":
            return None

        destinazione = self.data_dir / "data/processed"
        if self.variant_scheme == "current":
            destinazione = destinazione / "final_names_v1"
        return destinazione / f"evidence_{self.variant}_v1_{self.case_id}.json"


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