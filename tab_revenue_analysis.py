import streamlit as st
from datetime import date
import altair as alt

from read_revenue_period import read_revenue_period
from read_order_performance import read_order_performance
from read_product_performance import read_product_performance

def tab_revenue_analysis(start_date: date, end_date: date, sales_channel: str , customer_type: str = None):
    """
    Exibe o resumo geral com todas as métricas financeiras e operacionais agrupadas.
    """

    # ---- CHAMADAS DE DADOS ----
    revenue_df = read_revenue_period(start_date, end_date, sales_channel , customer_type = customer_type)

    if not revenue_df.empty:
        # ---- TOTAL (última linha somada) ----
        total_row = revenue_df.sum(numeric_only=True)

        # Primeira Linha: Vendas e Clientes
        st.markdown("#### 💰 Resumo Financeiro e Clientes")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("💰 Faturamento", f"R$ {total_row['Faturamento']:,.2f}")
        c2.metric("👥 Total Pedidos", int(total_row['Qtd. Pedidos']))
        c3.metric("🆕 Novos Clientes", int(total_row['Novos Clientes']))
        c4.metric("🔁 Clientes Recorrentes", int(total_row['Clientes Recorrentes']))
        c5.metric("📦 Itens Vendidos", int(total_row['Itens Vendidos']))

        # Segunda Linha: Operação e Eficiência
        st.markdown("#### ⏱️ Performance Operacional (Eficiência)")
        e1, e2, e3, e4, e5 = st.columns(5)
        
        pedidos_com_tempo = total_row['Pedidos c/ Tempo']
        efic_5 = (total_row['Pedidos ≤ 5min'] / pedidos_com_tempo * 100) if pedidos_com_tempo > 0 else 0
        efic_6 = (total_row['Pedidos ≤ 6min'] / pedidos_com_tempo * 100) if pedidos_com_tempo > 0 else 0
        efic_7 = (total_row['Pedidos ≤ 7min'] / pedidos_com_tempo * 100) if pedidos_com_tempo > 0 else 0

        e1.metric("⏱️ Pedidos c/ Tempo", int(pedidos_com_tempo))
        e2.metric("🚫 Pedidos s/ Tempo", int(total_row['Pedidos s/ Tempo']))
        e3.metric("✅ Eficiência ≤ 5min", f"{efic_5:.2f}%")
        e4.metric("✅ Eficiência ≤ 6min", f"{efic_6:.2f}%")
        e5.metric("✅ Eficiência ≤ 7min", f"{efic_7:.2f}%")
            
        st.markdown("---")

        # ---- Analise periodo ----
        st.subheader("Análise Detalhada do Período")
        if not revenue_df.empty:
            selection = st.dataframe(
                revenue_df,
                use_container_width=True,
                on_select="rerun",
                selection_mode="single-row",
                hide_index=True
            )
            
            if selection["selection"]["rows"]:
                selected_index = selection["selection"]["rows"][0]
                selected_row = revenue_df.iloc[[selected_index]]
                order_date = selected_row["Data"].iloc[0]

                st.subheader(f"Pedidos do dia {order_date.strftime('%d/%m/%Y')}")
                transactions_df = read_order_performance(order_date = order_date , sales_channel=sales_channel , customer_type= customer_type)
                if not transactions_df.empty:
                    st.dataframe(transactions_df, use_container_width=True , hide_index=True)
        else:
            st.info("Nenhum dado encontrado no período.")
    else:
        st.warning("⚠️ Não há dados de vendas para o período selecionado.")
