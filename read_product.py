from get_bigquery_client import get_bigquery_client
import streamlit as st
import pandas as pd
from datetime import date

#@st.cache_data(ttl=600)
def read_product(
    product_name: str = None, 
    sales_channel: str = None, 
    start_date: date = None, 
    end_date: date = None
):
    """
    Busca todos os registros de um produto específico em um canal de vendas e
    dentro de um período de validade.
    Todos os parâmetros são opcionais.
    """
    client = get_bigquery_client()
    
    where_clause = "WHERE 1=1"
    
    if sales_channel:
        where_clause += f" AND SC.SALES_CHANNEL_ID = '{sales_channel}'"
    
    if product_name:
        where_clause += f" AND P.NAME = '{product_name}'"
        
    # Adiciona o filtro de datas apenas se ambos os campos forem fornecidos
    if start_date and end_date:
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")
        where_clause += f"""
        AND P.VALID_FROM_DATE <= '{end_date_str}'
        AND P.VALID_TO_DATE >= '{start_date_str}'
        """

    query = f"""
    SELECT 
        P.ID,
        P.NAME,
        SC.SALES_CHANNEL_ID AS CHANNEL,
        P.CATEGORY,
        P.COST,
        S.SHORT_DESC AS STATUS,
        P.VALID_FROM_DATE,
        P.VALID_TO_DATE ,
        
    FROM
        PRODUCT P
    INNER JOIN
        STATUS S ON S.ID = P.STATUS
    INNER JOIN
        SALES_CHANNEL SC ON SC.ID = P.SALES_CHANNEL
    {where_clause}
    ORDER BY
        P.VALID_FROM_DATE DESC
    """
    
    try:
        query_job = client.query(query)
        df = query_job.to_dataframe()
        
        # O problema está aqui. A linha estava faltando a reatribuição.
        df = df.rename(columns={
            "CHANNEL": 'Canal' ,
            "NAME": "Produto",
            "COST": "Custo de Materia Prima",
            "STATUS": "Status na Plataforma",
            "VALID_FROM_DATE": "Custo vigente de",
            "VALID_TO_DATE": "Custo vigente até" 
            
        })
    
        if not df.empty:
            return df, df.iloc[0]
        else:
            return pd.DataFrame(), None
        
    except Exception as e:
        st.error(f"Erro ao buscar dados: {e}")
        return pd.DataFrame(), None
            
    except Exception as e:
        st.error(f"Erro ao buscar dados para edição: {e}")
        return pd.DataFrame(), None


# Exemplo 1: Buscar um produto específico em um canal e dentro de um período
#all_records_df_specific, last_df_specific = read_products_for_editing(
#    #product_name='Barato do Dia - Marmita de Açaí Tradicional 1100 ml', 
#    #sales_channel='iFood',
#    start_date=date(2025, 1, 2),
#    end_date=date(2025, 8, 20))
##)
##print("--- Busca com Produto, Canal e Datas ---")
#print(all_records_df_specific)
#if last_df_specific is not None:
#    print(last_df_specific)
#
## Exemplo 2: Buscar todos os produtos de um canal dentro de um período
#all_records_df_by_date, _ = read_products_for_editing(
#    sales_channel='iFood',
#    start_date=date(2025, 8, 1),
#    end_date=date(2025, 8, 31)
#)
#print("\n--- Busca por Canal e Datas ---")
#print(all_records_df_by_date)