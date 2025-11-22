import streamlit as st
import pandas as pd
from get_bigquery_client import get_bigquery_client
from datetime import date


#@st.cache_data(ttl=600, show_spinner=False)
def read_revenue_period(start_date: date, end_date: date, sales_channel: str = None, customer_type: str = None):
    """
    Retorna métricas de faturamento, custo, lucro, margem e clientes
    entre as datas informadas (inclusive).

    :param start_date: Data inicial (datetime.date)
    :param end_date: Data final (datetime.date)
    :param sales_channel: Canal de vendas (opcional)
    """

    client = get_bigquery_client()

    # Converter para string no formato YYYY-MM-DD
    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")

    # Cláusula WHERE condicional para o canal de vendas
    where_channel_clause = ""
    if sales_channel:
        where_channel_clause = f"AND ot.sales_channel = '{sales_channel}'"

    where_customer_clause = ""
    if customer_type == "Novo":
        where_customer_clause = """
        AND (
            (ot.SALES_CHANNEL = 'iFood' AND ot.TOTAL_ORDERS = 1)
            OR (ot.SALES_CHANNEL = '99food' AND ot.TOTAL_ORDERS <= 2)
        )
        """
    elif customer_type == "Recorrente":
        where_customer_clause = """
        AND (
            (ot.SALES_CHANNEL = 'iFood' AND ot.TOTAL_ORDERS > 1)
            OR (ot.SALES_CHANNEL = '99food' AND ot.TOTAL_ORDERS > 2)
        )
        """

    query = f"""
    SELECT
        DATE(ot.CREATED_AT, "America/Sao_Paulo") AS order_date,
        STRING_AGG(DISTINCT OT.SALES_CHANNEL, ', ' ORDER BY OT.SALES_CHANNEL) AS Canais,
        SUM(bi.sub_total_value) AS revenue,








        COUNT(1) AS items,
        QOT.QTY_PEDIDOS AS orders_count,
        QOT.NOVOS_CLIENTES AS new_customers,
        QOT.CLIENTES_RECORRENTES AS returning_customers ,
        ROUND( ANY_VALUE( QOT.TP7)/QOT.QTY_PEDIDOS * 100 ,2) AS TP7,
       ROUND( ANY_VALUE(  QOT.TP6)/QOT.QTY_PEDIDOS * 100,2) AS TP6,
       ROUND( ANY_VALUE( QOT.TP5) /QOT.QTY_PEDIDOS * 100 ,2)AS TP5

    FROM BAG_ITEMS bi
    INNER JOIN ORDERS_TABLE ot ON ot.id = bi.ORDER_ID
    LEFT JOIN (SELECT P.NAME, P.COST, p.VALID_FROM_DATE, p.VALID_TO_DATE, CH.SALES_CHANNEL_ID AS SALES_CHANNEL FROM PRODUCT P
INNER JOIN SALES_CHANNEL CH ON CH.ID = P.SALES_CHANNEL) p
        ON p.name = bi.name
        AND p.sales_channel = OT.SALES_CHANNEL
        AND DATE(ot.CREATED_AT, "America/Sao_Paulo") BETWEEN P.VALID_FROM_DATE AND P.VALID_TO_DATE
    LEFT JOIN CUSTOMER C ON C.ID = OT.CUSTOMER_ID

    LEFT JOIN (
        SELECT DATE(ot.CREATED_AT, "America/Sao_Paulo") AS order_date,
               COUNT(1) AS QTY_PEDIDOS,
               SUM(
                   CASE 
                       WHEN ot.SALES_CHANNEL = 'iFood' AND ot.TOTAL_ORDERS = 1 THEN 1
                       WHEN ot.SALES_CHANNEL = '99food' AND ot.TOTAL_ORDERS <= 2 THEN 1
                       ELSE 0
                   END
               ) AS NOVOS_CLIENTES,
               SUM(
                   CASE 
                       WHEN ot.SALES_CHANNEL = 'iFood' AND ot.TOTAL_ORDERS > 1 THEN 1
                       WHEN ot.SALES_CHANNEL = '99food' AND ot.TOTAL_ORDERS > 2 THEN 1
                       ELSE 0
                   END
               ) AS CLIENTES_RECORRENTES ,
                       SUM(CASE WHEN ot.PREPARATION_TIME > 7
                 THEN 1
                 ELSE 0 END ) AS TP7 ,
                 SUM(CASE WHEN ot.PREPARATION_TIME > 6
                 THEN 1
                 ELSE 0 END ) AS TP6 ,
                 SUM(CASE WHEN ot.PREPARATION_TIME > 5
                 THEN 1
                 ELSE 0 END ) AS TP5
        FROM ORDERS_TABLE ot
        WHERE DATE(ot.CREATED_AT, "America/Sao_Paulo") BETWEEN '{start_date_str}' AND '{end_date_str}'
        {where_channel_clause} -- Adicionei o filtro aqui
        {where_customer_clause}  -- <-- agora entra junto com AND

        GROUP BY DATE(ot.CREATED_AT, "America/Sao_Paulo")
    ) QOT ON QOT.order_date = DATE(ot.CREATED_AT, "America/Sao_Paulo")

    WHERE ot.current_status IN ('CONCLUDED', 'PARTIALLY_CANCELLED')
      AND DATE(ot.CREATED_AT, "America/Sao_Paulo") BETWEEN '{start_date_str}' AND '{end_date_str}'
      {where_channel_clause} -- E adicionei o filtro aqui também
      {where_customer_clause}  -- <-- agora entra junto com AND

    GROUP BY
        DATE(ot.CREATED_AT, "America/Sao_Paulo"),
        QOT.QTY_PEDIDOS,
        QOT.NOVOS_CLIENTES,
        QOT.CLIENTES_RECORRENTES
    ORDER BY DATE(ot.CREATED_AT, "America/Sao_Paulo") DESC
    """

    try:
        query_job = client.query(query)
        df = query_job.to_dataframe()
        df = df.rename(columns={
            'order_date': 'Data',
            'revenue': 'Faturamento',
            'cost': 'Custo',
            'items': 'Itens Vendidos',
            'orders_count': 'Qtd. Pedidos',
            'new_customers': 'Novos Clientes',
            'returning_customers': 'Clientes Recorrentes',
            'TP7': 'TP>7 (%)',
            'TP6': 'TP>6 (%)',
            'TP5': 'TP>5 (%)'
            
        })
        return df
    except Exception as e:
        st.error(f"Erro ao buscar métricas de faturamento: {e}")
        return pd.DataFrame()
    
#start_date = st.date_input("Start Date", value=date(2025, 8, 1))
#end_date = st.date_input("End Date", value=date(2025, 8, 31))
##
#df = read_revenue_period(start_date, end_date , sales_channel='iFood' , customer_type = 'new')
#print(df)