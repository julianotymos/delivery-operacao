import streamlit as st
import pandas as pd
from get_bigquery_client import get_bigquery_client
from datetime import date


#@st.cache_data(ttl=600, show_spinner=False)
def read_revenue_period(start_date: date, end_date: date, sales_channel: str = None, customer_type: str = None):
    """
    Retorna métricas de faturamento, clientes e eficiência de tempo (5, 6 e 7 min).
    """

    client = get_bigquery_client()

    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")

    where_channel_clause = f"AND ot.sales_channel = '{sales_channel}'" if sales_channel else ""

    where_customer_clause = ""
    if customer_type == "Novo":
        where_customer_clause = "AND ((ot.SALES_CHANNEL = 'iFood' AND ot.TOTAL_ORDERS = 1) OR (ot.SALES_CHANNEL = '99food' AND ot.TOTAL_ORDERS <= 2))"
    elif customer_type == "Recorrente":
        where_customer_clause = "AND ((ot.SALES_CHANNEL = 'iFood' AND ot.TOTAL_ORDERS > 1) OR (ot.SALES_CHANNEL = '99food' AND ot.TOTAL_ORDERS > 2))"

    query = f"""
    SELECT
        DATE(ot.CREATED_AT, "America/Sao_Paulo") AS order_date,
        STRING_AGG(DISTINCT OT.SALES_CHANNEL, ', ' ORDER BY OT.SALES_CHANNEL) AS Canais,
        SUM(bi.sub_total_value) AS revenue,
        COUNT(1) AS items,
        QOT.QTY_PEDIDOS AS orders_count,
        QOT.NOVOS_CLIENTES AS new_customers,
        QOT.CLIENTES_RECORRENTES AS returning_customers,
        QOT.QTY_COM_TEMPO AS pedidos_com_tempo,
        QOT.QTY_SEM_TEMPO AS pedidos_sem_tempo,
        QOT.ATE_5MIN AS pedidos_ate_5min,
        QOT.ATE_6MIN AS pedidos_ate_6min,
        QOT.ATE_7MIN AS pedidos_ate_7min,
        ROUND( (QOT.ATE_5MIN / NULLIF(QOT.QTY_COM_TEMPO, 0)) * 100, 2) AS EFIC_5MIN_PERC,
        ROUND( (QOT.ATE_6MIN / NULLIF(QOT.QTY_COM_TEMPO, 0)) * 100, 2) AS EFIC_6MIN_PERC,
        ROUND( (QOT.ATE_7MIN / NULLIF(QOT.QTY_COM_TEMPO, 0)) * 100, 2) AS EFIC_7MIN_PERC
    FROM BAG_ITEMS bi
    INNER JOIN ORDERS_TABLE ot ON ot.id = bi.ORDER_ID
    LEFT JOIN (SELECT P.NAME, P.COST, p.VALID_FROM_DATE, p.VALID_TO_DATE, CH.SALES_CHANNEL_ID AS SALES_CHANNEL FROM PRODUCT P
               INNER JOIN SALES_CHANNEL CH ON CH.ID = P.SALES_CHANNEL) p
        ON p.name = bi.name AND p.sales_channel = OT.SALES_CHANNEL
        AND DATE(ot.CREATED_AT, "America/Sao_Paulo") BETWEEN P.VALID_FROM_DATE AND P.VALID_TO_DATE
    
    LEFT JOIN (
        SELECT DATE(ot.CREATED_AT, "America/Sao_Paulo") AS order_date,
               COUNT(1) AS QTY_PEDIDOS,
               SUM(CASE WHEN ot.SALES_CHANNEL = 'iFood' AND ot.TOTAL_ORDERS = 1 THEN 1
                        WHEN ot.SALES_CHANNEL = '99food' AND ot.TOTAL_ORDERS <= 2 THEN 1 ELSE 0 END) AS NOVOS_CLIENTES,
               SUM(CASE WHEN ot.SALES_CHANNEL = 'iFood' AND ot.TOTAL_ORDERS > 1 THEN 1
                        WHEN ot.SALES_CHANNEL = '99food' AND ot.TOTAL_ORDERS > 2 THEN 1 ELSE 0 END) AS CLIENTES_RECORRENTES,
               COUNTIF(ot.PREPARATION_TIME > 0) AS QTY_COM_TEMPO,
               COUNTIF(ot.PREPARATION_TIME IS NULL OR ot.PREPARATION_TIME <= 0) AS QTY_SEM_TEMPO,
               COUNTIF(ot.PREPARATION_TIME > 0 AND ot.PREPARATION_TIME <= 5) AS ATE_5MIN,
               COUNTIF(ot.PREPARATION_TIME > 0 AND ot.PREPARATION_TIME <= 6) AS ATE_6MIN,
               COUNTIF(ot.PREPARATION_TIME > 0 AND ot.PREPARATION_TIME <= 7) AS ATE_7MIN
        FROM ORDERS_TABLE ot
        WHERE DATE(ot.CREATED_AT, "America/Sao_Paulo") BETWEEN '{start_date_str}' AND '{end_date_str}'
        {where_channel_clause} {where_customer_clause}
        GROUP BY 1
    ) QOT ON QOT.order_date = DATE(ot.CREATED_AT, "America/Sao_Paulo")

    WHERE ot.current_status IN ('CONCLUDED', 'PARTIALLY_CANCELLED')
      AND DATE(ot.CREATED_AT, "America/Sao_Paulo") BETWEEN '{start_date_str}' AND '{end_date_str}'
      {where_channel_clause} {where_customer_clause}
    GROUP BY 1, QOT.QTY_PEDIDOS, QOT.NOVOS_CLIENTES, QOT.CLIENTES_RECORRENTES, QOT.QTY_COM_TEMPO, QOT.QTY_SEM_TEMPO, QOT.ATE_5MIN, QOT.ATE_6MIN, QOT.ATE_7MIN
    ORDER BY 1 DESC
    """

    try:
        query_job = client.query(query)
        df = query_job.to_dataframe()
        df = df.rename(columns={
            'order_date': 'Data',
            'revenue': 'Faturamento',
            'items': 'Itens Vendidos',
            'orders_count': 'Qtd. Pedidos',
            'new_customers': 'Novos Clientes',
            'returning_customers': 'Clientes Recorrentes',
            'pedidos_com_tempo': 'Pedidos c/ Tempo',
            'pedidos_sem_tempo': 'Pedidos s/ Tempo',
            'pedidos_ate_5min': 'Pedidos ≤ 5min',
            'pedidos_ate_6min': 'Pedidos ≤ 6min',
            'pedidos_ate_7min': 'Pedidos ≤ 7min',
            'EFIC_5MIN_PERC': 'Eficiência ≤ 5min (%)',
            'EFIC_6MIN_PERC': 'Eficiência ≤ 6min (%)',
            'EFIC_7MIN_PERC': 'Eficiência ≤ 7min (%)'
        })
        return df
    except Exception as e:
        st.error(f"Erro ao buscar métricas de faturamento: {e}")
        return pd.DataFrame()
