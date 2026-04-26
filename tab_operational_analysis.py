import streamlit as st
import pandas as pd
import altair as alt
from read_operational_performance import read_operational_performance

def tab_operational_analysis(sales_channel: str = None):
    st.subheader("⏱️ Eficiência de Preparo vs Faturamento Mensal")
    st.markdown("Relacionamento entre o volume faturado e a eficiência operacional (até 5, 6 e 7 min).")

    df = read_operational_performance(sales_channel=sales_channel)

    if not df.empty:
        # --- GRÁFICO DE EIXO DUPLO ---
        
        # 1. Base: Faturamento (Barras)
        bar_chart = alt.Chart(df).mark_bar(opacity=0.3, color='#8884d8').encode(
            x=alt.X('mes:T', title='Mês'),
            y=alt.Y('faturamento:Q', title='Faturamento (R$)', axis=alt.Axis(titleColor='#8884d8')),
            tooltip=['Mês', alt.Tooltip('faturamento:Q', format=',.2f', title='Faturamento R$')]
        )

        # 2. Linhas de Eficiência
        df_melted = df.melt(
            id_vars=['mes', 'Mês'], 
            value_vars=['% <= 5 min', '% <= 6 min', '% <= 7 min'],
            var_name='Métrica', 
            value_name='Percentual'
        )

        line_chart = alt.Chart(df_melted).mark_line(point=True).encode(
            x=alt.X('mes:T'),
            y=alt.Y('Percentual:Q', title='Eficiência (%)', scale=alt.Scale(domain=[0, 100])),
            color=alt.Color('Métrica:N', 
                           scale=alt.Scale(domain=['% <= 5 min', '% <= 6 min', '% <= 7 min'], 
                                         range=['#2a9d8f', '#264653', '#e63946']),
                           title="Metas"),
            tooltip=['Mês', 'Métrica', alt.Tooltip('Percentual:Q', format='.2f')]
        )

        # Combinar gráficos
        combined_chart = alt.layer(bar_chart, line_chart).resolve_scale(
            y='independent'
        ).properties(height=450).interactive()

        st.altair_chart(combined_chart, use_container_width=True)

        # --- TABELA DETALHADA ---
        st.markdown("### 📊 Detalhamento Mensal")
        st.dataframe(
            df[['Mês', 'faturamento', 'total_bruto_pedidos', 'pedidos_com_tempo', '% <= 5 min', '% <= 6 min', '% <= 7 min']]
            .rename(columns={
                'faturamento': 'Faturamento (R$)',
                'total_bruto_pedidos': 'Total Pedidos',
                'pedidos_com_tempo': 'Pedidos c/ Tempo'
            })
            .style.format({
                'Faturamento (R$)': 'R$ {:,.2f}',
                '% <= 5 min': '{:.2f}%',
                '% <= 6 min': '{:.2f}%',
                '% <= 7 min': '{:.2f}%'
            }), 
            use_container_width=True,
            hide_index=True
        )
        
        st.caption("Nota: As barras cinzas representam o faturamento. As linhas representam a eficiência operacional.")
    else:
        st.info("Nenhum dado encontrado para os últimos 12 meses.")
