import streamlit as st
import pandas as pd
from read_bonus_calculation import read_bonus_calculation


def tab_bonus_analysis(sales_channel: str = None, use_estimated: bool = True):
    df = read_bonus_calculation(sales_channel=sales_channel, use_estimated=use_estimated)

    if df.empty:
        st.subheader("🎯 Simulador de Bônus de Delivery")
        st.info("Nenhum dado encontrado para calcular o bônus.")
        return

    latest = df.iloc[0]
    periodo_atual = latest["Período"]

    st.subheader(f"🎯 Simulador de Bônus de Delivery — Período atual: {periodo_atual}")
    st.markdown("Cálculo do bônus com base no tempo de preparo dos pedidos.")

    # ── MÉTRICAS DO PERÍODO ATUAL ────────────────────────────────────────────
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric(
        "Pedidos Válidos",
        f"{int(latest['pedidos_validos']):,}",
        help="Pedidos com tempo de preparo registrado (dias de fechamento excluídos)"
    )
    col2.metric(
        "% Pedidos ≤7min",
        f"{latest['pct_ate_7min']:.1f}%",
        help="Meta: 90%+"
    )
    col3.metric(
        "Multiplicador de Consistência",
        f"{latest['multiplicador'] * 100:.0f}%",
    )
    col4.metric(
        "Bônus Estimado",
        f"R$ {latest['bonus_final']:,.2f}",
        help="Após consistência e penalidades registradas"
    )
    col5.metric(
        "Perdido (Fechamentos)",
        f"R$ {latest['valor_perdido_fechamento']:,.2f}",
        delta=f"-R$ {latest['valor_perdido_fechamento']:,.2f}" if latest['valor_perdido_fechamento'] > 0 else None,
        delta_color="inverse",
        help="Bônus que seria ganho nos dias de fechamento de loja"
    )

    st.markdown("---")

    # ── GRID POR PERÍODO ─────────────────────────────────────────────────────
    st.markdown("### 📝 Bônus por Período")
    st.caption(
        "Penalidades e valor perdido por fechamento são calculados automaticamente "
        "a partir dos registros da aba **Ocorrências**."
    )

    grid_df = df[[
        "Período", "pedidos_validos", "ate_6min", "entre_6_7min", "acima_7min",
        "pct_ate_7min", "multiplicador", "bonus_bruto",
        "bonus_apos_consistencia", "total_erros", "penalidades",
        "valor_perdido_fechamento", "bonus_final"
    ]].copy()

    grid_df["multiplicador"] = (grid_df["multiplicador"] * 100).round(0)

    grid_df.rename(columns={
        "pedidos_validos":          "Pedidos Válidos",
        "ate_6min":                 "≤6min (R$1,00)",
        "entre_6_7min":             "6-7min (R$0,80)",
        "acima_7min":               ">7min",
        "pct_ate_7min":             "% ≤7min",
        "multiplicador":            "Multiplicador (%)",
        "bonus_bruto":              "Bônus Bruto (R$)",
        "bonus_apos_consistencia":  "c/ Consistência (R$)",
        "total_erros":              "Erros Registrados",
        "penalidades":              "Penalidades (R$)",
        "valor_perdido_fechamento": "Perdido Fechamento (R$)",
        "bonus_final":              "Bônus Final (R$)",
    }, inplace=True)

    st.dataframe(
        grid_df.style.format({
            "% ≤7min":               "{:.2f}%",
            "Multiplicador (%)":     "{:.0f}%",
            "Bônus Bruto (R$)":      "R$ {:,.2f}",
            "c/ Consistência (R$)":  "R$ {:,.2f}",
            "Penalidades (R$)":      "R$ {:,.2f}",
            "Perdido Fechamento (R$)": "R$ {:,.2f}",
            "Bônus Final (R$)":      "R$ {:,.2f}",
        }).map(
            lambda v: "color: #d62728; font-weight: bold" if isinstance(v, (int, float)) and v > 0 else "",
            subset=["Perdido Fechamento (R$)"]
        ),
        use_container_width=True,
        hide_index=True,
    )

    total_bonus = df["bonus_final"].sum()
    total_perdido = df["valor_perdido_fechamento"].sum()

    col_t1, col_t2 = st.columns(2)
    col_t1.success(f"💰 **Total bônus: R$ {total_bonus:,.2f}**")
    if total_perdido > 0:
        col_t2.error(f"📉 **Total perdido por fechamentos: R$ {total_perdido:,.2f}**")

    # ── REGRAS ───────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📋 Regras do Bônus de Delivery")

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown(
            """
**💰 Bônus por pedido**
- Até 6 minutos → **R$ 1,00**
- De 6 a 7 minutos → **R$ 0,80**
- Acima de 7 minutos → sem bônus

---

**📊 Consistência (% de pedidos ≤7min)**
- 90% ou mais → **100%** do bônus
- 85% a 89% → **90%** do bônus
- 80% a 84% → **80%** do bônus
- Abaixo de 80% → **0%** (não recebe)
"""
        )

    with col_b:
        st.markdown(
            """
**⚠️ Penalidades**
- Erro de montagem ou reenvio → **R$ 8,00** de penalidade (já inclui perda do bônus do pedido)
- Falta no mês (qualquer motivo) → **perde o bônus total do mês**

---

**🚫 Pedidos que não contam**
- Pedido não marcado como "pronto" no sistema
- Loja fechada por qualquer motivo → **todos os pedidos do dia são desconsiderados**
- Em caso de golpe: não é penalizado
"""
        )

    st.info("Este bônus é provisório e pode ser alterado ou encerrado dependendo dos resultados.")
