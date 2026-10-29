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

    for nodo in sorted(nodi):

        containers = sorted(mappa.get(nodo, set()))

        servizi = set()

        for container in containers:

            # Separiamo il suffisso numerico della replica.
            # checkoutservice-0 -> checkoutservice
            nome, separatore, replica = container.rpartition("-")

            if separatore and replica.isdigit() and nome:
                servizi.add(nome)

        risultati.append({
            "nodo": nodo,
            "container_osservati": containers,
            "servizi_osservati": sorted(servizi),
            "numero_container": len(containers),
            "numero_servizi": len(servizi),
            "associazioni_disponibili": bool(containers)
        })

    return risultati