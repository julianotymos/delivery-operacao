import uuid
import streamlit as st
import pandas as pd
from datetime import datetime, timezone
from google.cloud import bigquery
from get_bigquery_client import get_bigquery_client

DATASET = "DELIVERY"
TABLE = "bonus_ocorrencias"
TABLE_TOMBSTONE = "bonus_ocorrencias_tombstone"

CANAIS = ["iFood", "99food", "keeta"]
PROBLEMAS = ["Cancelamento", "Cancelamento Parcial", "Ocorrência", "Fechamento de Loja"]


def _full_table(client: bigquery.Client) -> str:
    return f"`{client.project}.{DATASET}.{TABLE}`"


def _full_tombstone(client: bigquery.Client) -> str:
    return f"`{client.project}.{DATASET}.{TABLE_TOMBSTONE}`"


def ensure_table_exists():
    client = get_bigquery_client()

    # Tabela principal
    table_ref = f"{client.project}.{DATASET}.{TABLE}"
    schema = [
        bigquery.SchemaField("id",               "STRING",    mode="REQUIRED"),
        bigquery.SchemaField("canal",            "STRING",    mode="REQUIRED"),
        bigquery.SchemaField("data_ocorrencia",  "DATE",      mode="REQUIRED"),
        bigquery.SchemaField("problema",         "STRING",    mode="REQUIRED"),
        bigquery.SchemaField("erro_operacional", "BOOL",      mode="REQUIRED"),
        bigquery.SchemaField("numero_pedido",    "STRING",    mode="NULLABLE"),
        bigquery.SchemaField("descricao",        "STRING",    mode="NULLABLE"),
        bigquery.SchemaField("created_at",       "TIMESTAMP", mode="REQUIRED"),
    ]
    client.create_table(bigquery.Table(table_ref, schema=schema), exists_ok=True)

    # Adiciona numero_pedido se a tabela já existia sem ela
    client.query(f"""
        ALTER TABLE `{table_ref}`
        ADD COLUMN IF NOT EXISTS numero_pedido STRING
    """).result()

    # Tabela de exclusões (tombstone) — evita DML no streaming buffer
    tombstone_ref = f"{client.project}.{DATASET}.{TABLE_TOMBSTONE}"
    tombstone_schema = [
        bigquery.SchemaField("id",         "STRING",    mode="REQUIRED"),
        bigquery.SchemaField("deleted_at", "TIMESTAMP", mode="REQUIRED"),
    ]
    client.create_table(bigquery.Table(tombstone_ref, tombstone_schema), exists_ok=True)


def _active_filter(client: bigquery.Client) -> str:
    """Subquery que exclui IDs marcados como excluídos no tombstone."""
    return f"""
        AND o.id NOT IN (
            SELECT id FROM {_full_tombstone(client)}
        )
    """


@st.cache_data(ttl=60, show_spinner=False)
def read_ocorrencias() -> pd.DataFrame:
    client = get_bigquery_client()
    query = f"""
    SELECT o.id, o.canal, o.data_ocorrencia, o.problema,
           o.erro_operacional, o.numero_pedido, o.descricao, o.created_at
    FROM {_full_table(client)} o
    WHERE TRUE
      {_active_filter(client)}
    ORDER BY o.data_ocorrencia DESC, o.created_at DESC
    """
    try:
        df = client.query(query).to_dataframe()
        if not df.empty:
            df["data_ocorrencia"] = pd.to_datetime(df["data_ocorrencia"]).dt.date
            df["created_at"] = pd.to_datetime(df["created_at"]).dt.tz_localize(None)
        return df
    except Exception as e:
        st.error(f"Erro ao buscar ocorrências: {e}")
        return pd.DataFrame()


def insert_ocorrencia(canal: str, data_ocorrencia, problema: str,
                      erro_operacional: bool, descricao: str, numero_pedido: str = None):
    client = get_bigquery_client()
    row = {
        "id": str(uuid.uuid4()),
        "canal": canal,
        "data_ocorrencia": str(data_ocorrencia),
        "problema": problema,
        "erro_operacional": erro_operacional,
        "numero_pedido": numero_pedido.strip() if numero_pedido else None,
        "descricao": descricao.strip() if descricao else None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    errors = client.insert_rows_json(f"{client.project}.{DATASET}.{TABLE}", [row])
    if errors:
        raise RuntimeError(f"Erro ao inserir: {errors}")
    st.cache_data.clear()


def delete_ocorrencia(record_id: str):
    """Marca o registro como excluído inserindo no tombstone (sem DML)."""
    client = get_bigquery_client()
    row = {
        "id": record_id,
        "deleted_at": datetime.now(timezone.utc).isoformat(),
    }
    errors = client.insert_rows_json(f"{client.project}.{DATASET}.{TABLE_TOMBSTONE}", [row])
    if errors:
        raise RuntimeError(f"Erro ao excluir: {errors}")
    st.cache_data.clear()


@st.cache_data(ttl=60, show_spinner=False)
def read_fechamentos() -> list[str]:
    """Retorna datas (YYYY-MM-DD) com Fechamento de Loja ativos."""
    client = get_bigquery_client()
    query = f"""
    SELECT DISTINCT CAST(o.data_ocorrencia AS STRING) AS dt
    FROM {_full_table(client)} o
    WHERE o.problema = 'Fechamento de Loja'
      {_active_filter(client)}
    """
    try:
        df = client.query(query).to_dataframe()
        return df["dt"].tolist() if not df.empty else []
    except Exception:
        return []


@st.cache_data(ttl=60, show_spinner=False)
def read_penalidades_por_periodo(bonus_start_date: str) -> pd.DataFrame:
    """Retorna total de erros operacionais (erro_operacional=TRUE) por período."""
    client = get_bigquery_client()
    query = f"""
    SELECT
        CASE
            WHEN o.data_ocorrencia BETWEEN '{bonus_start_date}' AND '2026-04-30'
                THEN DATE '{bonus_start_date}'
            ELSE DATE_TRUNC(o.data_ocorrencia, MONTH)
        END AS periodo,
        COUNT(*) AS total_erros
    FROM {_full_table(client)} o
    WHERE o.erro_operacional = TRUE
      AND o.data_ocorrencia >= '{bonus_start_date}'
      {_active_filter(client)}
    GROUP BY 1
    """
    try:
        return client.query(query).to_dataframe()
    except Exception:
        return pd.DataFrame(columns=["periodo", "total_erros"])
