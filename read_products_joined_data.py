from get_bigquery_client import get_bigquery_client
import streamlit as st
import pandas as pd

#st.cache_data.clear()

#@st.cache_data(ttl=600)
def read_products_joined_data():
    """
    Busca e retorna dados do produto com informações de status e canal de vendas.
    """
    client = get_bigquery_client()
    
    query = """
    SELECT 
        P.NAME,
        P.CATEGORY,
        P.COST,
        SC.SHORT_DESC AS CHANNEL,
        S.SHORT_DESC AS STATUS
    FROM
        PRODUCT P
    INNER JOIN
        STATUS S ON S.ID = P.STATUS
    INNER JOIN
        SALES_CHANNEL SC ON SC.ID = P.SALES_CHANNEL
    INNER JOIN (
        SELECT 
            SALES_CHANNEL,
            NAME,
            MAX(VALID_FROM_DATE) AS VALID_FROM_DATE
        FROM 
            PRODUCT
        GROUP BY 
            SALES_CHANNEL, NAME 
    ) M_P ON M_P.NAME = P.NAME AND P.VALID_FROM_DATE = M_P.VALID_FROM_DATE
    ORDER BY
        SC.SHORT_DESC DESC , S.SHORT_DESC ASC
    """
    
    try:
        print(query)
        query_job = client.query(query)
        print(query_job)
        df = query_job.to_dataframe()
        print(df)

        return df
    except Exception as e:
        st.error(f"Erro ao buscar dados com JOINs: {e}")
        return pd.DataFrame()

# ---

# Exemplo de uso
df_joined = read_products_joined_data()
print(df_joined)