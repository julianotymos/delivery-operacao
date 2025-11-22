import streamlit as st
import pandas as pd
from get_bigquery_client import get_bigquery_client
from datetime import date

#@st.cache_data(ttl=600, show_spinner=False)
def read_order_performance(order_date: date, sales_channel: str = None , customer_type: str = None):
    """
    Retorna métricas detalhadas por pedido (itens, valor, custo, lucro, markup)
    no período informado e para o canal de vendas especificado (opcional).
    """

    client = get_bigquery_client()
    
    # Removi a lógica de sales_channel_id, pois não é utilizada na query SQL.
    # O filtro agora é feito diretamente pelo nome do canal.

    # Converter datas para string no formato YYYY-MM-DD
    order_date_str = order_date.strftime("%Y-%m-%d")
    
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
        FORMAT_TIMESTAMP('%d/%m/%Y %H:%M', MAX(OT.CREATED_AT), 'America/Sao_Paulo') AS Data_Pedido,
        MAX(OT.SHORT_ID) AS N_Pedido, 
        OT.SALES_CHANNEL AS Canal,
        MAX(OT.TOTAL_ORDERS) AS N_Pedidos_Cliente, 
        STRING_AGG(p.NAME, '/') AS Itens, 
        SUM(BI.Quantity) AS qtd_itens,
        ROUND(SUM(bi.sub_total_value), 2) AS total_venda,
        ANY_VALUE(ot.preparation_time) as preparation_time ,
        ot.ID AS id
    FROM BAG_ITEMS bi 
    INNER JOIN ORDERS_TABLE ot 
        ON ot.id = bi.ORDER_ID 
    LEFT JOIN (SELECT P.NAME, P.COST, p.VALID_FROM_DATE, p.VALID_TO_DATE, CH.SALES_CHANNEL_ID AS SALES_CHANNEL FROM PRODUCT P 
INNER JOIN SALES_CHANNEL CH ON CH.ID = P.SALES_CHANNEL) p 
        ON p.name = bi.name 
        AND p.sales_channel = OT.SALES_CHANNEL
        AND DATE(ot.CREATED_AT) BETWEEN p.VALID_FROM_DATE AND p.VALID_TO_DATE
    WHERE DATE(ot.CREATED_AT) = '{order_date_str}'
        {where_channel_clause}
        {where_customer_clause}  

    GROUP BY ot.ID, OT.SALES_CHANNEL
    ORDER BY Data_Pedido DESC
    """

    try:
        query_job = client.query(query)
        df = query_job.to_dataframe()
        df = df.rename(columns={
            "Data_Pedido": "Data do Pedido",
            "N_Pedido": "Nº Pedido",
            "N_Pedidos_Cliente": "Qtd. Pedidos Cliente",
            "Itens": "Itens do Pedido",
            "qtd_itens": "Qtd. Itens",
            "total_venda": "Faturamento",
            "preparation_time" : "Tempo de Preparo",
            "id": "ID Interno" ,
        })
        return df
    except Exception as e:
        st.error(f"Erro ao buscar detalhes de pedidos: {e}")
        return pd.DataFrame()
    
#order_date = st.date_input("Start Date", value=date(2025, 8, 21))
#end_date = st.date_input("End Date", value=date(2025, 8, 31))
#df = read_order_performance(order_date = order_date , sales_channel='99food')
#print(df)