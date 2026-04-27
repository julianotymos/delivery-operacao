import streamlit as st
import pandas as pd
import altair as alt
from read_operational_performance import read_operational_performance

def tab_operational_analysis(sales_channel: str = None, use_estimated: bool = True):
    st.subheader("⏱️ Evolução Mensal da Eficiência de Preparo")
    st.markdown("Acompanhamento do percentual de pedidos preparados dentro das metas estabelecidas (5, 6 e 7 min).")

    df = read_operational_performance(sales_channel=sales_channel, use_estimated=use_estimated)

    if not df.empty:
        # --- GRÁFICO DE EFICIÊNCIA ---
        df_melted = df.melt(
            id_vars=['mes', 'Mês'], 
            value_vars=['% <= 5 min', '% <= 6 min', '% <= 7 min'],
            var_name='Meta', 
            value_name='Percentual'
        )

        line_chart = alt.Chart(df_melted).mark_line(point=True).encode(
            x=alt.X('mes:T', title='Mês de Referência'),
            y=alt.Y('Percentual:Q', title='Eficiência (%)', scale=alt.Scale(domain=[0, 100])),
            color=alt.Color('Meta:N', 
                           scale=alt.Scale(domain=['% <= 5 min', '% <= 6 min', '% <= 7 min'], 
                                         range=['#2a9d8f', '#264653', '#e63946']),
                           title="Limite de Tempo"),
            tooltip=['Mês', 'Meta', alt.Tooltip('Percentual:Q', format='.2f')]
        ).properties(height=450).interactive()

        st.altair_chart(line_chart, use_container_width=True)

        # --- TABELA DETALHADA ---
        st.markdown("### 📊 Detalhamento Mensal")
        st.dataframe(
            df[['Mês', 'total_bruto_pedidos', 'pedidos_com_tempo', '% <= 5 min', '% <= 6 min', '% <= 7 min']]
            .rename(columns={
                'total_bruto_pedidos': 'Total Pedidos',
                'pedidos_com_tempo': 'Pedidos p/ Efic.'
            })
            .style.format({
                '% <= 5 min': '{:.2f}%',
                '% <= 6 min': '{:.2f}%',
                '% <= 7 min': '{:.2f}%'
            }), 
            use_container_width=True,
            hide_index=True
        )
        
        st.caption(f"Nota: Eficiência calculada considerando {'tempo real + estimado' if use_estimated else 'apenas tempo real (Pronto)'}.")
    else:
        st.info("Nenhum dado encontrado para os últimos 12 meses.")
