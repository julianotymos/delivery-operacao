import datetime
import random
import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
from read_process_last_run import read_process_last_run
from datetime import datetime, timedelta
from typing import List
from tab_revenue_analysis import tab_revenue_analysis  # <-- substitui tab_sales_total
from tab_product_analysis import tab_product_analysis  # <-- substitui tab_sales_total
from tab_subitem_analysis import tab_subitem_analysis
from tab_operational_analysis import tab_operational_analysis

# --- Início da Aplicação Streamlit ---

st.set_page_config(
    page_title="Dashboard de Vendas", # Aqui o título será sempre fixo
    layout="wide",
    initial_sidebar_state="expanded"
)
# --- Barra Lateral para Filtros e Status ---
st.sidebar.header("🗓️ Período de Análise")
sales_channels = ["","iFood", "99food"]
customer_type = ["","Novo", "Recorrente"]

start_date = st.sidebar.date_input("Data Inicial", (datetime.now() - timedelta(days=1)).date())
end_date = st.sidebar.date_input("Data Final", datetime.now().date())


# 1. ✅ Canal de vendas na barra lateral (Obtem a seleção do usuário)
f_sales_channel = st.sidebar.selectbox("Selecione o canal de vendas:", sales_channels)

# 2. ✅ Lógica para tratar a seleção vazia
if f_sales_channel == "":
    # Se nada foi selecionado, use a regra de 'Todos'
    channel_display_name = "iFood & 99food" 
else:
    # Se algo foi selecionado, use o nome selecionado
    channel_display_name = f_sales_channel

# 3. ✅ Atualiza o título do aplicativo com base na seleção
st.title(f"📊 Performance Delivery: {channel_display_name}") 

# ... (Restante do código continua a partir daqui)
f_customer_type = st.sidebar.selectbox("Tipo de Cliente:", customer_type)

if start_date > end_date:
    st.sidebar.error("⚠️ Erro: A data inicial não pode ser posterior à data final.")
else:
    # --- Criação das Abas ---
    tab_revenue, tab_products, tab_oper, tab_subitem = st.tabs(["Performance Vendas", "Performance de Produtos", "Performance Operacional", "Preferencias Cliente"])

    # ---- Aba de Resumo de Receita ----
    with tab_revenue:
        tab_revenue_analysis(start_date, end_date, sales_channel=f_sales_channel , customer_type= f_customer_type)

    # ---- Aba de Performance de Produtos ----
    with tab_products:
        product_df = tab_product_analysis(start_date, end_date, f_sales_channel , customer_type= f_customer_type )
        
    with tab_oper:
        tab_operational_analysis(sales_channel=f_sales_channel)

    with tab_subitem:
        product_df = tab_subitem_analysis(start_date, end_date, f_sales_channel , customer_type= f_customer_type)

    # --- Status de Processamento na Barra Lateral ---
    st.sidebar.markdown("---")
    st.sidebar.header("🔄 Status de Processamento")
    last_run_df = read_process_last_run(["BIG_QUERY_PROCESS"])
    if not last_run_df.empty:
        for index, row in last_run_df.iterrows():
            st.sidebar.info(f"**{row['name']}**\nÚltima atualização: {row['last_run_date'].strftime('%d/%m/%Y %H:%M:%S')}")
    else:
        st.sidebar.warning("Nenhum dado de status encontrado.")