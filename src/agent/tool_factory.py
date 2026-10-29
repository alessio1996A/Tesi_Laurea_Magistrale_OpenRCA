from typing import Optional, Literal

from langchain_core.tools import tool, BaseTool

import agent.tools


def crea_tools_openrca(
    cloudbed: str,
    start_unix: int,
    end_unix: int
) -> list[BaseTool]:
    """
    Crea i cinque tool LangChain utilizzati dagli agenti.

    Ogni tool viene vincolato:
    - al cloudbed dell'incidente;
    - alla finestra temporale ufficiale.

    La factory non utilizza ground truth e non esegue
    chiamate Gemini.
    """

    # ======================================================
    # 1. VALIDAZIONE DELLA CONFIGURAZIONE
    # ======================================================

    if cloudbed not in ("cloudbed-1", "cloudbed-2"):
        raise ValueError("Cloudbed non valido.")

    if start_unix >= end_unix:
        raise ValueError("Intervallo temporale non valido.")

    def controlla_intervallo(
        inizio: int,
        fine: int
    ) -> Optional[str]:
        """
        Impedisce ai tool di accedere a dati esterni
        alla finestra ufficiale dell'incidente.
        """

        if (
            inizio < start_unix
            or fine > end_unix
            or inizio >= fine
        ):
            return (
                "Errore: intervallo non consentito. "
                f"Utilizza [{start_unix}, {end_unix})."
            )

        return None

    # ======================================================
    # 2. METRICHE DEI SERVIZI
    # ======================================================

    @tool("tool_get_service_metrics")
    def service_metrics(
        start_unix: int,
        end_unix: int,
        service_name: Optional[str] = None,
        max_rows: int = 30
    ) -> str:
        """Legge response rate, success rate e response time dei servizi."""

        errore = controlla_intervallo(start_unix, end_unix)

        if errore:
            return errore

        return agent.tools.tool_get_service_metrics(
            start_unix=start_unix,
            end_unix=end_unix,
            service_name=service_name,
            max_rows=max_rows,
            market_system=cloudbed
        )

    # ======================================================
    # 3. METRICHE DEI CONTAINER
    # ======================================================

    @tool("tool_get_container_metrics")
    def container_metrics(
        start_unix: int,
        end_unix: int,
        cmdb_id: Optional[str] = None,
        kpi_name: Optional[str] = None,
        max_rows: int = 100
    ) -> str:
        """Restituisce statistiche delle metriche container per componente e KPI."""

        errore = controlla_intervallo(start_unix, end_unix)

        if errore:
            return errore

        return agent.tools.tool_get_container_metrics(
            start_unix=start_unix,
            end_unix=end_unix,
            cmdb_id=cmdb_id,
            kpi_name=kpi_name,
            max_rows=max_rows,
            market_system=cloudbed
        )

    # ======================================================
    # 4. METRICHE DEI NODI
    # ======================================================

    @tool("tool_get_node_metrics")
    def node_metrics(
        start_unix: int,
        end_unix: int,
        cmdb_id: Optional[str] = None,
        kpi_name: Optional[str] = None,
        max_rows: int = 100
    ) -> str:
        """Restituisce statistiche delle metriche dei nodi per componente e KPI."""

        errore = controlla_intervallo(start_unix, end_unix)

        if errore:
            return errore

        return agent.tools.tool_get_node_metrics(
            start_unix=start_unix,
            end_unix=end_unix,
            cmdb_id=cmdb_id,
            kpi_name=kpi_name,
            max_rows=max_rows,
            market_system=cloudbed
        )

    # ======================================================
    # 5. LOG
    # ======================================================

    @tool("tool_get_logs")
    def logs(
        start_unix: int,
        end_unix: int,
        log_type: Literal["service", "proxy"] = "service",
        cmdb_id: Optional[str] = None,
        keyword: Optional[str] = None,
        max_rows: int = 30
    ) -> str:
        """Legge log di servizio o proxy nella finestra ufficiale."""

        errore = controlla_intervallo(start_unix, end_unix)

        if errore:
            return errore

        return agent.tools.tool_get_logs(
            start_unix=start_unix,
            end_unix=end_unix,
            log_type=log_type,
            cmdb_id=cmdb_id,
            keyword=keyword,
            max_rows=max_rows,
            market_system=cloudbed
        )

    # ======================================================
    # 6. TRACE
    # ======================================================

    @tool("tool_get_traces")
    def traces(
        start_unix: int,
        end_unix: int,
        cmdb_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        min_duration_ms: Optional[int] = None,
        max_rows: int = 30
    ) -> str:
        """Legge span delle trace distribuite nella finestra ufficiale."""

        errore = controlla_intervallo(start_unix, end_unix)

        if errore:
            return errore

        return agent.tools.tool_get_traces(
            start_unix=start_unix,
            end_unix=end_unix,
            cmdb_id=cmdb_id,
            trace_id=trace_id,
            min_duration_ms=min_duration_ms,
            max_rows=max_rows,
            market_system=cloudbed
        )

    # ======================================================
    # 7. RESTITUZIONE DEI CINQUE TOOL
    # ======================================================

    return [
        service_metrics,
        container_metrics,
        node_metrics,
        logs,
        traces
    ]