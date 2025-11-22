import streamlit as st
from datetime import date, timedelta
from read_item_sales_analysis import read_item_sales_analysis
# --- Configurações da Página ---
def tab_subitem_analysis(start_date: date, end_date: date, sales_channel: str , customer_type: str = None):
    """
    Exibe a aba de Performance de Produtos.
    Inclui métricas resumidas, top 5 produtos e tabela completa de produtos.
    """
    #st.header(f"📦 Performance de Produtos - Canal: {sales_channel}")

    # ---- Buscar dados ----
    sub_item_df = read_item_sales_analysis(start_date=start_date, end_date=end_date, sales_channel=sales_channel)
    #print(sub_item_df)

    if not sub_item_df.empty:
        
        #print(sub_item_df)
    
        # ---- Tabela completa de produtos ----
        st.subheader("Preferencia dos Clientes")
        st.dataframe(sub_item_df, use_container_width=True ,hide_index=True )
        
        
    else:
        st.info("Nenhum dado Preferencia dos Clientes encontrado para o período e canal selecionados.")

  