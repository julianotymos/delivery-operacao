import streamlit as st
from datetime import date
import altair as alt

from read_revenue_period import read_revenue_period
from read_order_performance import read_order_performance
from read_product_performance import read_product_performance

def tab_revenue_analysis(start_date: date, end_date: date, sales_channel: str , customer_type: str = None, use_estimated: bool = True):
    """
    Exibe o resumo detalhado de volumes e performance operacional (sem faturamento).
    """

    # ---- CHAMADAS DE DADOS ----
    revenue_df = read_revenue_period(start_date, end_date, sales_channel , customer_type = customer_type, use_estimated=use_estimated)

    if not revenue_df.empty:
        # ---- TOTAL (última linha somada) ----
        total_row = revenue_df.sum(numeric_only=True)

        # 1ª Linha: Resumo de Volume e Clientes
        st.markdown("#### 👥 Resumo de Pedidos e Clientes")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("👥 Total Pedidos", int(total_row['Qtd. Pedidos']))
        c2.metric("📦 Itens Vendidos", int(total_row['Itens Vendidos']))
        c3.metric("🆕 Novos Clientes", int(total_row['Novos Clientes']))
        c4.metric("🔁 Clientes Recorrentes", int(total_row['Clientes Recorrentes']))

        # 2ª Linha: Dados de Tempo e Eficiência
        st.markdown("#### ⏱️ Performance Operacional (Tempo de Preparo)")
        e1, e2, e3, e4 = st.columns(4)
        
        e1.metric("⏱️ Pedidos p/ Efic.", int(total_row['Pedidos p/ Eficiência']))
        e2.metric("🚫 Pedidos s/ Tempo", int(total_row['Pedidos s/ Tempo']))
        e3.metric("🖱️ Deu Pronto", int(total_row['Deu Pronto']))
        e4.metric("⚠️ Não deu Pronto", int(total_row['Não deu Pronto']))

        # 3ª Linha: Percentuais de Eficiência
        st.markdown("#### ✅ Percentuais de Sucesso (Eficiência)")
        p1, p2, p3 = st.columns(3)
        
        com_tempo = total_row['Pedidos p/ Eficiência']
        efic_5 = (total_row['Pedidos ≤ 5min'] / com_tempo * 100) if com_tempo > 0 else 0
        efic_6 = (total_row['Pedidos ≤ 6min'] / com_tempo * 100) if com_tempo > 0 else 0
        efic_7 = (total_row['Pedidos ≤ 7min'] / com_tempo * 100) if com_tempo > 0 else 0

        p1.metric("🎯 Efic. ≤ 5min", f"{efic_5:.2f}%")
        p2.metric("🎯 Efic. ≤ 6min", f"{efic_6:.2f}%")
        p3.metric("🎯 Efic. ≤ 7min", f"{efic_7:.2f}%")
            
        st.markdown("---")

        # ---- Analise periodo ----
        st.subheader("Análise Detalhada do Período")
        if not revenue_df.empty:
            # Exibir grid removendo a coluna de faturamento
            df_display = revenue_df.drop(columns=['Faturamento'], errors='ignore')
            selection = st.dataframe(
                df_display,
                width='stretch',
                on_select="rerun",
                selection_mode="single-row",
                hide_index=True
            )
            
            if selection["selection"]["rows"]:
                selected_index = selection["selection"]["rows"][0]
                selected_row = df_display.iloc[[selected_index]]
                order_date = selected_row["Data"].iloc[0]

                st.subheader(f"Pedidos do dia {order_date.strftime('%d/%m/%Y')}")
                transactions_df = read_order_performance(order_date = order_date , sales_channel=sales_channel , customer_type= customer_type)
                if not transactions_df.empty:
                    # Remove faturamento também do detalhe do dia se existir
                    if 'Faturamento' in transactions_df.columns:
                        transactions_df = transactions_df.drop(columns=['Faturamento'])
                    st.dataframe(transactions_df, width='stretch' , hide_index=True)
    else:
        st.warning("⚠️ Não há dados disponíveis para o período selecionado.")
