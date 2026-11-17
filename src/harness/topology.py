"""Topologia nodo -> container ricavata dai nomi dei componenti (`cmdb_id`) di OpenRCA.

Nel sistema Market un container si chiama `<nodo>.<servizio>-<replica>` (per esempio
`node-6.checkoutservice-0`): dal nome si legge su quale nodo gira e di quale servizio è una replica.
Questo modulo raccoglie quelle informazioni, senza guardare le dipendenze tra servizi.

Usato da `harness/evidence_builder.py`. Nessun LLM, nessuna ground truth.
"""

import re
from typing import Iterable


def costruisci_mappa_nodi_container(
    cmdb_ids: Iterable[str],
    nodi_interesse: Iterable[str] = ()
) -> list[dict]:
    """
    Ricava le associazioni nodo-container dai cmdb_id OpenRCA.

    Non ricostruisce le dipendenze tra servizi
    e non verifica relazioni causali.

    Argomenti:
      cmdb_ids         elenco dei nomi di componente osservati; quelli che non hanno la forma
                       `node-<numero>.<container>` vengono ignorati.
      nodi_interesse   nodi da includere anche se non risultano container osservati (per esempio i
                       nodi sui quali l'agente sta indagando).

    Restituisce una lista ordinata per nodo; ogni elemento riporta i container osservati, i servizi
    (nome del container senza il suffisso `-<replica>`), i loro conteggi e se esistono associazioni.
    """

    # Dizionario: nodo -> insieme dei container osservati.
    mappa = {}

    for identificativo in cmdb_ids:

        if not isinstance(identificativo, str):
            continue

        # Esempio: node-6.checkoutservice-0
        match = re.fullmatch(
            r"(node-\d+)\.(.+)",
            identificativo.strip()
        )

        if match is None:
            continue

        nodo, container = match.groups()

        # Gli insiemi evitano container duplicati.
        mappa.setdefault(nodo, set()).add(container)

    # Includiamo anche i nodi di interesse senza associazioni.
    nodi = set(mappa) | set(nodi_interesse)

    risultati = []

    # Ordine alfabetico dei nodi: il risultato non dipende dall'ordine in cui arrivano i dati.
    for nodo in sorted(nodi):

        containers = sorted(mappa.get(nodo, set()))

        servizi = set()

        for container in containers:

            # Separiamo il suffisso numerico della replica.
            # checkoutservice-0 -> checkoutservice
            nome, separatore, replica = container.rpartition("-")

            # Si accetta come servizio solo un nome che finisce con "-<numero>"; gli altri container
            # (per esempio senza suffisso di replica) restano elencati ma non producono un servizio.
            if separatore and replica.isdigit() and nome:
                servizi.add(nome)

        # Una riga per nodo, con i conteggi già calcolati.
        risultati.append({
            "nodo": nodo,
            "container_osservati": containers,
            "servizi_osservati": sorted(servizi),
            "numero_container": len(containers),
            "numero_servizi": len(servizi),
            "associazioni_disponibili": bool(containers)
        })

    return risultati