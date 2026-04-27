import streamlit as st
import pandas as pd
from get_bigquery_client import get_bigquery_client

@st.cache_data(ttl=3600, show_spinner="Calculando performance operacional...")
def read_operational_performance(sales_channel: str = None, use_estimated: bool = True):
    client = get_bigquery_client()
    where_channel_clause = f"AND ot.SALES_CHANNEL = '{sales_channel}'" if sales_channel else ""

    if use_estimated:
        time_field = "COALESCE(NULLIF(ot.preparation_time, 0), ot.estimated_prep_time)"
        denom_cond = "(ot.preparation_time > 0 OR ot.estimated_prep_time > 0)"
    else:
        time_field = "ot.preparation_time"
        denom_cond = "ot.preparation_time > 0"

    query = f"""
    SELECT 
        DATE_TRUNC(DATE(ot.CREATED_AT, "America/Sao_Paulo"), MONTH) AS mes,
        SUM(ot.total_bag_detail) AS faturamento,
        COUNT(1) AS total_bruto_pedidos,
        COUNTIF({denom_cond}) AS pedidos_com_tempo,
        COUNTIF({time_field} <= 5 AND {denom_cond}) AS ate_5min,
        COUNTIF({time_field} <= 6 AND {denom_cond}) AS ate_6min,
        COUNTIF({time_field} <= 7 AND {denom_cond}) AS ate_7min
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
            denom = df['pedidos_com_tempo'].replace(0, pd.NA)
            df['% <= 5 min'] = (df['ate_5min'] / denom) * 100
            df['% <= 6 min'] = (df['ate_6min'] / denom) * 100
            df['% <= 7 min'] = (df['ate_7min'] / denom) * 100
            df['Mês'] = pd.to_datetime(df['mes']).dt.strftime('%b/%Y')
        return df
    except Exception as e:
        st.error(f"Erro ao buscar performance operacional: {e}")
        return pd.DataFrame()
