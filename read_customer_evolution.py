import streamlit as st
import pandas as pd
from get_bigquery_client import get_bigquery_client
from datetime import date
from typing import Optional

#@st.cache_data(ttl=600, show_spinner=False)
def read_customer_evolution( sales_channel: Optional[str] = None):
    """
    Retorna métricas diárias e acumuladas de Novos e Recorrentes,
    incluindo percentuais, para um gráfico de evolução.
    
    :param start_date: Data inicial (datetime.date)
    :param end_date: Data final (datetime.date)
    :param sales_channel: Canal de vendas (opcional, ex: 'iFood')
    """

    client = get_bigquery_client()

    #start_date_str = start_date.strftime("%Y-%m-%d")
    #end_date_str = end_date.strftime("%Y-%m-%d")

    # Cláusula WHERE condicional para o canal de vendas
    where_channel_clause = ""
    if sales_channel and sales_channel != 'iFood - 99food': # Mantendo o filtro se for um canal específico
        where_channel_clause = f"AND ot.SALES_CHANNEL = '{sales_channel}'"

    query = f"""
    WITH DailyMetrics AS (
        -- 1. Calcula as métricas diárias (Pedidos, Novos e Recorrentes)
        SELECT 
            DATE(ot.CREATED_AT, "America/Sao_Paulo") AS order_date,
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
            ) AS CLIENTES_RECORRENTES
        FROM 
            ORDERS_TABLE ot
        WHERE 1=1
            {where_channel_clause}
            
        GROUP BY 
            1
    )
    -- 2. Aplica a soma acumulada e calcula os percentuais arredondados e multiplicados por 100
    SELECT
        order_date,
        QTY_PEDIDOS,
        NOVOS_CLIENTES,
        CLIENTES_RECORRENTES,
        
        -- Colunas Acumuladas
        SUM(QTY_PEDIDOS) OVER (ORDER BY order_date ASC) AS QTY_PEDIDOS_ACUMULADO,
        SUM(NOVOS_CLIENTES) OVER (ORDER BY order_date ASC) AS NOVOS_CLIENTES_ACUMULADO,
        SUM(CLIENTES_RECORRENTES) OVER (ORDER BY order_date ASC) AS CLIENTES_RECORRENTES_ACUMULADO,
        
        -- Colunas Percentuais Acumuladas (Multiplicadas por 100.0 e ARREDONDADAS)
        ROUND(
            SAFE_DIVIDE(
                SUM(CLIENTES_RECORRENTES) OVER (ORDER BY order_date ASC), 
                SUM(QTY_PEDIDOS) OVER (ORDER BY order_date ASC)
            ) * 100.0, 
        2) AS PCT_RECORRENTES_ACUMULADO,
        
        ROUND(
            SAFE_DIVIDE(
                SUM(NOVOS_CLIENTES) OVER (ORDER BY order_date ASC), 
                SUM(QTY_PEDIDOS) OVER (ORDER BY order_date ASC)
            ) * 100.0, 
        2) AS PCT_NOVOS_ACUMULADO

    FROM 
        DailyMetrics
    ORDER BY  
        order_date ASC
    """

    try:
        query_job = client.query(query)
        df = query_job.to_dataframe()
        return df
    except Exception as e:
        st.error(f"Erro ao buscar evolução de clientes: {e}")
        return pd.DataFrame()

    
#df = read_customer_evolution(sales_channel = 'iFood')
#print(df)