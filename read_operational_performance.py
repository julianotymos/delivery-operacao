import streamlit as st
import pandas as pd
from get_bigquery_client import get_bigquery_client

@st.cache_data(ttl=3600, show_spinner="Calculando performance operacional...")
def read_operational_performance(sales_channel: str = None):
    """
    Retorna estatísticas de tempo de preparo e faturamento mensal,
    alinhado com os critérios de sucesso das vendas (Concluídos/Parcialmente Cancelados).
    """
    client = get_bigquery_client()

    where_channel_clause = ""
    if sales_channel:
        where_channel_clause = f"AND ot.SALES_CHANNEL = '{sales_channel}'"

    query = f"""
    SELECT 
        DATE_TRUNC(DATE(ot.CREATED_AT, "America/Sao_Paulo"), MONTH) AS mes,
        SUM(ot.total_bag_detail) AS faturamento,
        COUNT(1) AS total_bruto_pedidos,
        COUNTIF(ot.preparation_time > 0) AS pedidos_com_tempo,
        COUNTIF(ot.preparation_time > 0 AND ot.preparation_time <= 5) AS ate_5min,
        COUNTIF(ot.preparation_time > 0 AND ot.preparation_time <= 6) AS ate_6min,
        COUNTIF(ot.preparation_time > 0 AND ot.preparation_time <= 7) AS ate_7min
    FROM `ORDERS_TABLE` ot
    WHERE ot.current_status IN ('CONCLUDED', 'PARTIALLY_CANCELLED')
        AND DATE(ot.CREATED_AT, "America/Sao_Paulo") >= DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 12 MONTH), MONTH)
        {where_channel_clause}
    GROUP BY 1
    ORDER BY 1 DESC
    """

    try:
        query_job = client.query(query)
        df = query_job.to_dataframe()
        
        if not df.empty:
            # Calcular percentuais de eficiência sobre pedidos medidos
            df['% <= 5 min'] = (df['ate_5min'] / NULLIF_SERIES(df['pedidos_com_tempo'])) * 100
            df['% <= 6 min'] = (df['ate_6min'] / NULLIF_SERIES(df['pedidos_com_tempo'])) * 100
            df['% <= 7 min'] = (df['ate_7min'] / NULLIF_SERIES(df['pedidos_com_tempo'])) * 100
            
            # Formatar mês para exibição
            df['Mês'] = pd.to_datetime(df['mes']).dt.strftime('%b/%Y')
            
        return df
    except Exception as e:
        st.error(f"Erro ao buscar performance operacional: {e}")
        return pd.DataFrame()

def NULLIF_SERIES(series):
    """Função auxiliar para evitar divisão por zero no Pandas."""
    return series.replace(0, pd.NA)
