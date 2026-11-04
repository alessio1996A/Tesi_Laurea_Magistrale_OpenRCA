"""Profilazione offline delle 40 run congelate OpenRCA V3.

Legge soltanto i JSON di esecuzione: NON accede a Market.zip, query.csv,
record.csv, scoring_points, chiavi Gemini o API. Non modifica file.
L'analisi dei tool distingue ripetizioni di *famiglia* da duplicati esatti:
interrogazioni allo stesso tool su finestre diverse NON sono equivalenti.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

# ID della campagna originale: non rinominare i file su Drive.
PROTOCOLLO_V3 = "openrca_harness_v2_five_agents_development_v3"


@dataclass(frozen=True)
class Profilo:
    caso: str
    variante_storica: str
    chiamate_llm: int
    round_tool: int
    chiamate_tool: int
    ripetizioni_famiglia_tool: int
    duplicati_esatti_tool: int
    token: int
    tempo_totale_s: float
    preprocessing_s: float

    @property
    def tempo_modello_e_tool_s(self) -> float:
        """Tempo rimanente dopo il preprocessing, non solo tempo LLM."""
        return max(0.0, self.tempo_totale_s - self.preprocessing_s)


def profilo_run(run: dict) -> Profilo:
    """Estrae solo metadati di performance da una run salvata.

    Le predizioni, le motivazioni e la ground truth NON sono ispezionate.
    La funzione non effettua alcuna chiamata esterna.
    """
    if not isinstance(run, dict):
        raise TypeError("La run deve essere un dizionario JSON")

    metriche = run.get("metrics")
    traiettoria = run.get("tool_trajectory", [])
    if not isinstance(metriche, dict) or not isinstance(traiettoria, list):
        raise ValueError("Metriche o traiettoria assenti/incoerenti")

    chiamate = [
        evento for evento in traiettoria
        if isinstance(evento, dict) and evento.get("tipo") == "tool_call"
    ]
    strumenti = [evento.get("nome", "") for evento in chiamate]
    if any(not isinstance(nome, str) or not nome for nome in strumenti):
        raise ValueError("Nome del tool assente")

    # Canonicalizzazione completa: nome tool + parametri (inclusa finestra).
    firme = [
        json.dumps(
            {"nome": evento["nome"], "parametri": evento.get("parametri", {})},
            ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        )
        for evento in chiamate
    ]

    per_nome = Counter(strumenti)
    per_firma = Counter(firme)

    try:
        profilo = Profilo(
            caso=str(run["case_id"]),
            variante_storica=str(run["variant"]),
            chiamate_llm=int(metriche["llm_calls"]),
            round_tool=int(metriche["tool_rounds"]),
            chiamate_tool=len(chiamate),
            ripetizioni_famiglia_tool=sum(n - 1 for n in per_nome.values()),
            duplicati_esatti_tool=sum(n - 1 for n in per_firma.values()),
            token=int(metriche["total_tokens"]),
            tempo_totale_s=float(metriche["end_to_end_seconds"]),
            preprocessing_s=float(metriche.get("preprocessing_seconds", 0)),
        )
    except (KeyError, ValueError, TypeError) as errore:
        raise ValueError("Metadati di performance incompleti") from errore

    if (
        profilo.chiamate_llm < 0
        or profilo.round_tool < 0
        or profilo.token < 0
        or profilo.tempo_totale_s < 0
        or not 0 <= profilo.preprocessing_s <= profilo.tempo_totale_s
    ):
        raise ValueError("Metriche di performance impossibili")
    return profilo


def leggi_profili(cartella: Path, *, protocollo: str = PROTOCOLLO_V3) -> list[Profilo]:
    """Legge ogni JSON run V3 una sola volta, ignorando i file .claim.json."""
    if not cartella.is_dir():
        raise FileNotFoundError(f"Cartella V3 non trovata: {cartella}")
    percorsi = sorted(cartella.glob(f"{protocollo}__*__r01.json"))
    if not percorsi:
        raise FileNotFoundError("Nessuna run V3 trovata")
    profili = []
    for percorso in percorsi:
        with percorso.open("r", encoding="utf-8") as file:
            profili.append(profilo_run(json.load(file)))
    return profili


def riepilogo_varianti(profili: list[Profilo]) -> list[dict]:
    """Statistiche descrittive per variante, senza metriche di accuratezza."""
    gruppi: dict[str, list[Profilo]] = defaultdict(list)
    for profilo in profili:
        gruppi[profilo.variante_storica].append(profilo)

    righe = []
    for variante, runs in sorted(gruppi.items()):
        n = len(runs)
        righe.append({
            "variante": variante,
            "run": n,
            "llm_medi": round(sum(x.chiamate_llm for x in runs) / n, 2),
            "tool_medi": round(sum(x.chiamate_tool for x in runs) / n, 2),
            "token_medi": round(sum(x.token for x in runs) / n, 1),
            "tempo_medio_s": round(sum(x.tempo_totale_s for x in runs) / n, 2),
            "preprocess_medio_s": round(sum(x.preprocessing_s for x in runs) / n, 2),
            "ripetizioni_famiglia_totali": sum(
                x.ripetizioni_famiglia_tool for x in runs
            ),
            "duplicati_esatti_totali": sum(x.duplicati_esatti_tool for x in runs),
        })
    return righe


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Profilo offline, sola lettura, delle run OpenRCA V3."
    )
    parser.add_argument(
        "cartella",
        type=Path,
        help="Cartella Drive data/results/v2/<protocollo> con i 40 JSON",
    )
    parser.add_argument("--top", type=int, default=5)
    args = parser.parse_args()
    if args.top < 1:
        parser.error("--top deve essere >= 1")

    profili = leggi_profili(args.cartella)
    print(f"Run lette: {len(profili)} (nessuna chiamata Gemini)")
    for riga in riepilogo_varianti(profili):
        print(json.dumps(riga, ensure_ascii=False))

    print("\nRun con tempi piu' lunghi:")
    for p in sorted(profili, key=lambda x: x.tempo_totale_s, reverse=True)[:args.top]:
        print(
            f"{p.caso:20} {p.variante_storica:13} "
            f"tempo={p.tempo_totale_s:8.2f}s "
            f"preprocess={p.preprocessing_s:6.2f}s "
            f"llm={p.chiamate_llm} tool={p.chiamate_tool} "
            f"ripetizioni_famiglia={p.ripetizioni_famiglia_tool} "
            f"duplicati_esatti={p.duplicati_esatti_tool}"
        )


if __name__ == "__main__":
    main()
