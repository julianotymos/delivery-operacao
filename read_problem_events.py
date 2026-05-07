import streamlit as st
import pandas as pd
from get_bigquery_client import get_bigquery_client

PROBLEM_TYPE_LABELS = {
    "CANCELAMENTO_TOTAL":  "Cancelamento Total",
    "CANCELAMENTO":        "Cancelamento",
    "REEMBOLSO":           "Reembolso",
    "REENVIO":             "Reenvio",
    "RECLAMACAO":          "Reclamação",
    "CANCELAMENTO_PARCIAL": "Cancelamento Parcial",
}


def translate_problem_type(value: str) -> str:
    return PROBLEM_TYPE_LABELS.get(value, value)


@st.cache_data(ttl=120, show_spinner="Buscando eventos de problemas...")
def read_pending_events(start_date, end_date, sales_channel: str = None) -> pd.DataFrame:
    """Eventos que ainda não têm ocorrência vinculada em bonus_ocorrencias."""
    client = get_bigquery_client()
    channel_clause = _channel_clause(sales_channel)

    query = f"""
    SELECT
        ot.id              AS order_id,
        ot.SALES_CHANNEL   AS canal,
        ot.SHORT_ID        AS short_id,
        DATE(ot.CREATED_AT, "America/Sao_Paulo") AS data_pedido,
        ot.CURRENT_STATUS  AS status,
        ot.NET_VALUE       AS valor_liquido,
        pe.PROBLEM_TYPE    AS problem_type,
        pe.CANCEL_CODE     AS cancel_code,
        pe.CANCEL_CODE_DESCRIPTION AS cancel_descricao,
        pe.CANCEL_REASON   AS cancel_motivo,
        pe.IS_PARTIAL_CANCELLATION AS cancelamento_parcial,
        pe.FINANCIAL_COMPLEMENT_COST AS custo_complemento,
        pe.FINANCIAL_STORE_REFUND    AS reembolso_loja,
        pe.INSERTED_AT     AS inserted_at
    FROM `ORDERS_TABLE` ot
    INNER JOIN `ORDER_PROBLEM_EVENTS` pe ON pe.ORDER_ID = ot.id
    WHERE ot.CURRENT_STATUS IN ('CONCLUDED', 'CANCELLED', 'PARTIALLY_CANCELLED')
      AND DATE(ot.CREATED_AT, "America/Sao_Paulo") BETWEEN '{start_date}' AND '{end_date}'
      {channel_clause}
      AND ot.id NOT IN (
          SELECT ORDER_ID FROM `BONUS_OCCURRENCES`
          WHERE ORDER_ID IS NOT NULL
            AND ID NOT IN (SELECT ID FROM `BONUS_OCCURRENCES_TOMBSTONE`)
      )
    ORDER BY ot.CREATED_AT DESC
    """
    return _run(client, query)


@st.cache_data(ttl=120, show_spinner="Buscando eventos processados...")
def read_processed_events(start_date, end_date, sales_channel: str = None) -> pd.DataFrame:
    """Eventos que já têm ocorrência vinculada."""
    client = get_bigquery_client()
    channel_clause = _channel_clause(sales_channel)

    query = f"""
    SELECT
        ot.id              AS order_id,
        ot.SALES_CHANNEL   AS canal,
        ot.SHORT_ID        AS short_id,
        DATE(ot.CREATED_AT, "America/Sao_Paulo") AS data_pedido,
        ot.CURRENT_STATUS  AS status,
        ot.NET_VALUE       AS valor_liquido,
        pe.PROBLEM_TYPE    AS problem_type,
        pe.CANCEL_CODE     AS cancel_code,
        oc.EMPLOYEE_NAME   AS responsavel,
        oc.CREATED_AT      AS processado_em
    FROM `ORDERS_TABLE` ot
    INNER JOIN `ORDER_PROBLEM_EVENTS` pe ON pe.ORDER_ID = ot.id
    INNER JOIN `BONUS_OCCURRENCES` oc ON oc.ORDER_ID = ot.id
    WHERE ot.CURRENT_STATUS IN ('CONCLUDED', 'CANCELLED', 'PARTIALLY_CANCELLED')
      AND DATE(ot.CREATED_AT, "America/Sao_Paulo") BETWEEN '{start_date}' AND '{end_date}'
      {channel_clause}
      AND oc.ID NOT IN (SELECT ID FROM `BONUS_OCCURRENCES_TOMBSTONE`)
    ORDER BY ot.CREATED_AT DESC
    """
    return _run(client, query)


def _channel_clause(sales_channel: str) -> str:
    if sales_channel == "iFood + 99food":
        return "AND ot.SALES_CHANNEL IN ('iFood', '99food')"
    if sales_channel:
        return f"AND ot.SALES_CHANNEL = '{sales_channel}'"
    return ""


def _run(client, query: str) -> pd.DataFrame:
    try:
        df = client.query(query).to_dataframe()
        if not df.empty and "problem_type" in df.columns:
            df["problema_exibicao"] = df["problem_type"].apply(translate_problem_type)
        return df
    except Exception as e:
        st.error(f"Erro ao buscar eventos: {e}")
        return pd.DataFrame()
