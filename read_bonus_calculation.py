import streamlit as st
import pandas as pd
from get_bigquery_client import get_bigquery_client
from read_ocorrencias import read_fechamentos, read_penalidades_por_periodo

# Bônus iniciou em 25/04/2026 — primeiro período parcial: 25-30/Abr
# A partir de 01/05/2026 os períodos são meses fechados normais
BONUS_START_DATE = "2026-04-25"

_MESES_PT = {
    1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez"
}


@st.cache_data(ttl=3600, show_spinner="Calculando bônus de delivery...")
def read_bonus_calculation(sales_channel: str = None, use_estimated: bool = True):
    client = get_bigquery_client()

    where_channel_clause = ""
    if sales_channel == "iFood + 99food":
        where_channel_clause = "AND ot.sales_channel IN ('iFood', '99food')"
    elif sales_channel:
        where_channel_clause = f"AND ot.SALES_CHANNEL = '{sales_channel}'"

    if use_estimated:
        time_field = "COALESCE(NULLIF(ot.preparation_time, 0), ot.estimated_prep_time)"
        denom_cond = "(ot.preparation_time > 0 OR ot.estimated_prep_time > 0)"
    else:
        time_field = "ot.preparation_time"
        denom_cond = "ot.preparation_time > 0"

    fechamentos = read_fechamentos()
    fechamentos_clause = _build_fechamentos_clause(fechamentos)

    # ── QUERY PRINCIPAL (exclui dias de fechamento) ──────────────────────────
    query_principal = f"""
    SELECT
        CASE
            WHEN DATE(ot.CREATED_AT, "America/Sao_Paulo") BETWEEN '{BONUS_START_DATE}' AND '2026-04-30'
                THEN DATE '{BONUS_START_DATE}'
            ELSE DATE_TRUNC(DATE(ot.CREATED_AT, "America/Sao_Paulo"), MONTH)
        END AS periodo,
        COUNT(1) AS total_bruto_pedidos,
        COUNTIF({denom_cond}) AS pedidos_validos,
        COUNTIF({time_field} <= 6 AND {denom_cond}) AS ate_6min,
        COUNTIF({time_field} > 6 AND {time_field} <= 7 AND {denom_cond}) AS entre_6_7min,
        COUNTIF({time_field} > 7 AND {denom_cond}) AS acima_7min,
        COUNTIF({time_field} <= 7 AND {denom_cond}) AS ate_7min
    FROM `ORDERS_TABLE` ot
    WHERE ot.current_status IN ('CONCLUDED', 'PARTIALLY_CANCELLED')
        AND DATE(ot.CREATED_AT, "America/Sao_Paulo") >= '{BONUS_START_DATE}'
        {fechamentos_clause}
        {where_channel_clause}
    GROUP BY 1
    ORDER BY 1 DESC
    """

    # ── QUERY VALOR PERDIDO (somente dias de fechamento) ─────────────────────
    query_perdido = None
    if fechamentos:
        datas_in = ", ".join(f"DATE '{d}'" for d in fechamentos)
        query_perdido = f"""
        SELECT
            CASE
                WHEN DATE(ot.CREATED_AT, "America/Sao_Paulo") BETWEEN '{BONUS_START_DATE}' AND '2026-04-30'
                    THEN DATE '{BONUS_START_DATE}'
                ELSE DATE_TRUNC(DATE(ot.CREATED_AT, "America/Sao_Paulo"), MONTH)
            END AS periodo,
            COUNTIF({time_field} <= 6 AND {denom_cond}) AS perdido_ate_6min,
            COUNTIF({time_field} > 6 AND {time_field} <= 7 AND {denom_cond}) AS perdido_6_7min
        FROM `ORDERS_TABLE` ot
        WHERE ot.current_status IN ('CONCLUDED', 'PARTIALLY_CANCELLED')
            AND DATE(ot.CREATED_AT, "America/Sao_Paulo") IN ({datas_in})
            {where_channel_clause}
        GROUP BY 1
        """

    try:
        df = client.query(query_principal).to_dataframe()
        if df.empty:
            return pd.DataFrame()

        # Cálculos do bônus
        denom = df["pedidos_validos"].replace(0, pd.NA)
        df["pct_ate_7min"] = (df["ate_7min"] / denom * 100).round(2)
        df["multiplicador"] = df["pct_ate_7min"].apply(_multiplicador)
        df["bonus_bruto"] = (df["ate_6min"] * 1.00 + df["entre_6_7min"] * 0.80).round(2)
        df["bonus_apos_consistencia"] = (df["bonus_bruto"] * df["multiplicador"]).round(2)

        # Penalidades reais da tabela de ocorrências
        pen_df = read_penalidades_por_periodo(BONUS_START_DATE)
        if not pen_df.empty:
            pen_df["periodo"] = pd.to_datetime(pen_df["periodo"]).dt.date
            df["periodo_date"] = pd.to_datetime(df["periodo"]).dt.date
            df = df.merge(pen_df, left_on="periodo_date", right_on="periodo", how="left", suffixes=("", "_pen"))
            df["total_erros"] = df["total_erros"].fillna(0).astype(int)
            df.drop(columns=["periodo_pen", "periodo_date"], errors="ignore", inplace=True)
        else:
            df["total_erros"] = 0

        df["penalidades"] = (df["total_erros"] * 8.00).round(2)
        df["bonus_final"] = (df["bonus_apos_consistencia"] - df["penalidades"]).clip(lower=0).round(2)

        # Valor perdido por fechamento de loja
        df["valor_perdido_fechamento"] = 0.0
        if query_perdido:
            df_perdido = client.query(query_perdido).to_dataframe()
            if not df_perdido.empty:
                df_perdido["valor_perdido"] = (
                    df_perdido["perdido_ate_6min"] * 1.00 + df_perdido["perdido_6_7min"] * 0.80
                ).round(2)
                df_perdido["periodo"] = pd.to_datetime(df_perdido["periodo"]).dt.date
                df["periodo_date"] = pd.to_datetime(df["periodo"]).dt.date
                df = df.merge(
                    df_perdido[["periodo", "valor_perdido"]],
                    left_on="periodo_date", right_on="periodo",
                    how="left", suffixes=("", "_fech")
                )
                df["valor_perdido_fechamento"] = df["valor_perdido"].fillna(0.0).round(2)
                df.drop(columns=["periodo_fech", "periodo_date", "valor_perdido"], errors="ignore", inplace=True)

        df["Período"] = df["periodo"].apply(_label_periodo)
        return df

    except Exception as e:
        st.error(f"Erro ao calcular bônus: {e}")
        return pd.DataFrame()


def _build_fechamentos_clause(fechamentos: list[str]) -> str:
    if not fechamentos:
        return ""
    datas = ", ".join(f"DATE '{d}'" for d in fechamentos)
    return f"AND DATE(ot.CREATED_AT, \"America/Sao_Paulo\") NOT IN ({datas})"


def _label_periodo(periodo) -> str:
    d = pd.to_datetime(periodo)
    mes = _MESES_PT[d.month]
    if d.strftime("%Y-%m-%d") == BONUS_START_DATE:
        return f"25-30/{mes}/{d.year}"
    return f"{mes}/{d.year}"


def _multiplicador(pct: float) -> float:
    if pd.isna(pct):
        return 0.0
    if pct >= 90:
        return 1.00
    if pct >= 85:
        return 0.90
    if pct >= 80:
        return 0.80
    return 0.00
