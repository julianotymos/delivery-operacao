import streamlit as st
import pandas as pd
from get_bigquery_client import get_bigquery_client
from datetime import date

def read_revenue_period(start_date: date, end_date: date, sales_channel: str = None, customer_type: str = None, use_estimated: bool = True):
    client = get_bigquery_client()
    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")

    where_channel_clause = f"AND ot.sales_channel = '{sales_channel}'" if sales_channel else ""

    where_customer_clause = ""
    if customer_type == "Novo":
        where_customer_clause = "AND ((ot.SALES_CHANNEL = 'iFood' AND ot.TOTAL_ORDERS = 1) OR (ot.SALES_CHANNEL = '99food' AND ot.TOTAL_ORDERS <= 2))"
    elif customer_type == "Recorrente":
        where_customer_clause = "AND ((ot.SALES_CHANNEL = 'iFood' AND ot.TOTAL_ORDERS > 1) OR (ot.SALES_CHANNEL = '99food' AND ot.TOTAL_ORDERS > 2))"

    # Lógica de Tempo Unificado: Real (se existir) ou Estimado
    if use_estimated:
        # Pega Real, se for 0/NULL pega o Estimado
        time_field = "COALESCE(NULLIF(ot.PREPARATION_TIME, 0), ot.ESTIMATED_PREP_TIME)"
        denom_condition = "(ot.PREPARATION_TIME > 0 OR ot.ESTIMATED_PREP_TIME > 0)"
    else:
        # Apenas Real
        time_field = "ot.PREPARATION_TIME"
        denom_condition = "ot.PREPARATION_TIME > 0"

    query = f"""
    SELECT
        DATE(ot.CREATED_AT, "America/Sao_Paulo") AS order_date,
        STRING_AGG(DISTINCT OT.SALES_CHANNEL, ', ' ORDER BY OT.SALES_CHANNEL) AS Canais,
        SUM(bi.sub_total_value) AS revenue,
        COUNT(1) AS items,
        QOT.QTY_PEDIDOS AS orders_count,
        QOT.NOVOS_CLIENTES AS new_customers,
        QOT.CLIENTES_RECORRENTES AS returning_customers,
        QOT.QTY_COM_PRONTO AS pedidos_com_pronto,
        QOT.QTY_SEM_PRONTO AS pedidos_sem_pronto,
        QOT.QTY_VALIDA_EFIC AS pedidos_com_tempo,
        QOT.QTY_SEM_TEMPO_GERAL AS pedidos_s_tempo_total,
        QOT.ATE_5MIN AS pedidos_ate_5min,
        QOT.ATE_6MIN AS pedidos_ate_6min,
        QOT.ATE_7MIN AS pedidos_ate_7min,
        ROUND( (QOT.ATE_7MIN / NULLIF(QOT.QTY_VALIDA_EFIC, 0)) * 100, 2) AS EFIC_7MIN_PERC
    FROM BAG_ITEMS bi
    INNER JOIN ORDERS_TABLE ot ON ot.id = bi.ORDER_ID
    LEFT JOIN (
        SELECT DATE(ot.CREATED_AT, "America/Sao_Paulo") AS order_date,
               COUNT(1) AS QTY_PEDIDOS,
               SUM(CASE WHEN ot.SALES_CHANNEL = 'iFood' AND ot.TOTAL_ORDERS = 1 THEN 1
                        WHEN ot.SALES_CHANNEL = '99food' AND ot.TOTAL_ORDERS <= 2 THEN 1 ELSE 0 END) AS NOVOS_CLIENTES,
               SUM(CASE WHEN ot.SALES_CHANNEL = 'iFood' AND ot.TOTAL_ORDERS > 1 THEN 1
                        WHEN ot.SALES_CHANNEL = '99food' AND ot.TOTAL_ORDERS > 2 THEN 1 ELSE 0 END) AS CLIENTES_RECORRENTES,
               COUNTIF(ot.IS_READY_CLICKED = 1) AS QTY_COM_PRONTO,
               COUNTIF(ot.IS_READY_CLICKED = 0 AND ot.ESTIMATED_PREP_TIME > 0) AS QTY_SEM_PRONTO,
               COUNTIF({denom_condition}) AS QTY_VALIDA_EFIC,
               COUNTIF(NOT ({denom_condition})) AS QTY_SEM_TEMPO_GERAL,
               COUNTIF({time_field} <= 5 AND {denom_condition}) AS ATE_5MIN,
               COUNTIF({time_field} <= 6 AND {denom_condition}) AS ATE_6MIN,
               COUNTIF({time_field} <= 7 AND {denom_condition}) AS ATE_7MIN
        FROM ORDERS_TABLE ot
        WHERE DATE(ot.CREATED_AT, "America/Sao_Paulo") BETWEEN '{start_date_str}' AND '{end_date_str}'
        {where_channel_clause} {where_customer_clause}
        GROUP BY 1
    ) QOT ON QOT.order_date = DATE(ot.CREATED_AT, "America/Sao_Paulo")
    WHERE ot.current_status IN ('CONCLUDED', 'PARTIALLY_CANCELLED')
      AND DATE(ot.CREATED_AT, "America/Sao_Paulo") BETWEEN '{start_date_str}' AND '{end_date_str}'
      {where_channel_clause} {where_customer_clause}
    GROUP BY 1, QOT.QTY_PEDIDOS, QOT.NOVOS_CLIENTES, QOT.CLIENTES_RECORRENTES, QOT.QTY_COM_PRONTO, QOT.QTY_SEM_PRONTO, QOT.QTY_VALIDA_EFIC, QOT.QTY_SEM_TEMPO_GERAL, QOT.ATE_5MIN, QOT.ATE_6MIN, QOT.ATE_7MIN
    ORDER BY 1 DESC
    """

    try:
        query_job = client.query(query)
        df = query_job.to_dataframe()
        df = df.rename(columns={
            'order_date': 'Data', 'revenue': 'Faturamento', 'items': 'Itens Vendidos', 'orders_count': 'Qtd. Pedidos',
            'new_customers': 'Novos Clientes', 'returning_customers': 'Clientes Recorrentes',
            'pedidos_com_pronto': 'Deu Pronto', 'pedidos_sem_pronto': 'Não deu Pronto',
            'pedidos_com_tempo': 'Pedidos p/ Eficiência', 'pedidos_s_tempo_total': 'Pedidos s/ Tempo',
            'pedidos_ate_5min': 'Pedidos ≤ 5min', 'pedidos_ate_6min': 'Pedidos ≤ 6min', 'pedidos_ate_7min': 'Pedidos ≤ 7min',
            'EFIC_7MIN_PERC': 'Eficiência ≤ 7min (%)'
        })
        return df
    except Exception as e:
        st.error(f"Erro ao buscar faturamento: {e}")
        return pd.DataFrame()
