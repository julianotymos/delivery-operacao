import streamlit as st
import pandas as pd
from get_bigquery_client import get_bigquery_client
from datetime import date

#@st.cache_data(ttl=600, show_spinner=False)
def read_product_performance(start_date: date, end_date: date, sales_channel: str = None, customer_type: str = None):
    """
    Retorna métricas de vendas por produto (quantidade, valor, custo, lucro, markup)
    no período informado e para o canal de vendas especificado (opcional).
    """

    client = get_bigquery_client()

    # Converter datas para string no formato YYYY-MM-DD
    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")

    # Cláusula WHERE condicional para o canal de vendas
    where_channel_clause = ""
    if sales_channel:
        where_channel_clause = f"AND ot.SALES_CHANNEL = '{sales_channel}'"
        
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
        p.NAME,
        STRING_AGG(DISTINCT OT.SALES_CHANNEL, ', ' ORDER BY OT.SALES_CHANNEL) AS Canais,
        SUM(BI.Quantity) AS qtd_itens,
        ROUND(SUM(bi.sub_total_value), 2) AS total_venda,
    FROM BAG_ITEMS bi 
    INNER JOIN ORDERS_TABLE ot 
        ON ot.id = bi.ORDER_ID 
    LEFT JOIN (SELECT P.NAME ,P.COST, p.VALID_FROM_DATE , p.VALID_TO_DATE , CH.SALES_CHANNEL_ID AS SALES_CHANNEL FROM PRODUCT P 
INNER JOIN SALES_CHANNEL CH ON CH.ID = P.SALES_CHANNEL) p 
        ON p.name = bi.name 
        AND p.sales_channel = OT.SALES_CHANNEL
        AND DATE(ot.CREATED_AT) BETWEEN p.VALID_FROM_DATE AND p.VALID_TO_DATE
    WHERE
        DATE(ot.CREATED_AT) BETWEEN '{start_date_str}' AND '{end_date_str}'
        {where_channel_clause}
        {where_customer_clause}  

    GROUP BY p.NAME
    ORDER BY qtd_itens DESC
    """

    try:
        query_job = client.query(query)
        df = query_job.to_dataframe()
        df = df.rename(columns={
            "NAME": "Produto",
            "qtd_itens": "Quantidade",
            "total_venda": "Faturamento",
        })
        return df
    except Exception as e:
        st.error(f"Erro ao buscar métricas de produtos: {e}")
        return pd.DataFrame()
# --------------------------
# Interface Streamlit
# --------------------------
#start_date = st.date_input("Start Date", value=date(2025, 8, 1))
#end_date = st.date_input("End Date", value=date(2025, 8, 31))
#
#
#
#df = read_product_performance(start_date, end_date, sales_channel='99food')
#print(df)
