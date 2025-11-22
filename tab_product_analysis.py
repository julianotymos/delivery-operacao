import streamlit as st
from datetime import date, timedelta
from read_product_performance import read_product_performance
from read_product import read_product
# --- Configurações da Página ---
def tab_product_analysis(start_date: date, end_date: date, sales_channel: str , customer_type: str = None):
    """
    Exibe a aba de Performance de Produtos.
    Inclui métricas resumidas, top 5 produtos e tabela completa de produtos.
    """
    #st.header(f"📦 Performance de Produtos - Canal: {sales_channel}")

    # ---- Buscar dados ----
    product_df_performance = read_product_performance(start_date, end_date, sales_channel , customer_type = customer_type)
    product_df ,product_df_0  = read_product(start_date=start_date, end_date=end_date, sales_channel=sales_channel)
    #print(product_df)
    product_df_display = product_df.drop(columns=['ID', 'CATEGORY'])

    if not product_df_performance.empty:
        

        # ---- Tabela completa de produtos ----
        st.subheader("Resultado por Produto")
        st.dataframe(product_df_performance, use_container_width=True ,hide_index=True )
        
        
    else:
        st.info("Nenhum dado de performance de produtos encontrado para o período e canal selecionados.")

    if not product_df.empty:

        st.subheader("Vingencia de custos de Produtos")
        st.dataframe(product_df_display, use_container_width=True ,hide_index=True )
        
    else:
        st.info("Nenhum dado de custos de produtos encontrado para o período e canal selecionados.")