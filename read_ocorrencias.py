import uuid
import streamlit as st
import pandas as pd
from datetime import datetime, timezone
from google.cloud import bigquery
from get_bigquery_client import get_bigquery_client

DATASET = "DELIVERY"
TABLE = "bonus_ocorrencias"
TABLE_TOMBSTONE = "bonus_ocorrencias_tombstone"
TABLE_RESPONSAVEIS = "bonus_responsaveis"

CANAIS = ["iFood", "99food", "keeta"]
PROBLEMAS = ["Cancelamento", "Cancelamento Parcial", "Ocorrência", "Fechamento de Loja"]

_RESPONSAVEIS_PADRAO = [
    "Taina", "Keila", "Stefanie", "Eduarda",
    "Juliana", "Freelance", "Desconhecido"
]


def _full_table(client: bigquery.Client) -> str:
    return f"`{client.project}.{DATASET}.{TABLE}`"


def _full_tombstone(client: bigquery.Client) -> str:
    return f"`{client.project}.{DATASET}.{TABLE_TOMBSTONE}`"


def _full_responsaveis(client: bigquery.Client) -> str:
    return f"`{client.project}.{DATASET}.{TABLE_RESPONSAVEIS}`"


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
        bigquery.SchemaField("responsavel",      "STRING",    mode="NULLABLE"),
        bigquery.SchemaField("numero_pedido",    "STRING",    mode="NULLABLE"),
        bigquery.SchemaField("descricao",        "STRING",    mode="NULLABLE"),
        bigquery.SchemaField("created_at",       "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("updated_at",       "TIMESTAMP", mode="NULLABLE"),
    ]
    client.create_table(bigquery.Table(table_ref, schema=schema), exists_ok=True)

    for col_def in ["numero_pedido STRING", "responsavel STRING", "updated_at TIMESTAMP"]:
        client.query(f"""
            ALTER TABLE `{table_ref}`
            ADD COLUMN IF NOT EXISTS {col_def}
        """).result()

    # Tabela tombstone
    tombstone_ref = f"{client.project}.{DATASET}.{TABLE_TOMBSTONE}"
    client.create_table(bigquery.Table(tombstone_ref, [
        bigquery.SchemaField("id",         "STRING",    mode="REQUIRED"),
        bigquery.SchemaField("deleted_at", "TIMESTAMP", mode="REQUIRED"),
    ]), exists_ok=True)

    # Tabela de responsáveis
    resp_ref = f"{client.project}.{DATASET}.{TABLE_RESPONSAVEIS}"
    client.create_table(bigquery.Table(resp_ref, [
        bigquery.SchemaField("id",     "STRING", mode="REQUIRED"),
        bigquery.SchemaField("nome",   "STRING", mode="REQUIRED"),
        bigquery.SchemaField("ativo",  "BOOL",   mode="REQUIRED"),
    ]), exists_ok=True)

    _seed_responsaveis(client, resp_ref)


def _seed_responsaveis(client: bigquery.Client, resp_ref: str):
    """Insere os responsáveis padrão se a tabela estiver vazia."""
    result = client.query(
        f"SELECT COUNT(*) AS total FROM `{resp_ref}`"
    ).to_dataframe()
    if result["total"].iloc[0] > 0:
        return
    rows = [
        {"id": str(uuid.uuid4()), "nome": nome, "ativo": True}
        for nome in _RESPONSAVEIS_PADRAO
    ]
    client.insert_rows_json(resp_ref, rows)


@st.cache_data(ttl=300, show_spinner=False)
def read_responsaveis() -> list[str]:
    client = get_bigquery_client()
    query = f"""
    SELECT nome FROM {_full_responsaveis(client)}
    WHERE ativo = TRUE
    ORDER BY nome
    """
    try:
        df = client.query(query).to_dataframe()
        return df["nome"].tolist() if not df.empty else _RESPONSAVEIS_PADRAO
    except Exception:
        return _RESPONSAVEIS_PADRAO


def _active_filter(client: bigquery.Client) -> str:
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
           o.erro_operacional, o.responsavel, o.numero_pedido, o.descricao, o.created_at, o.updated_at
    FROM {_full_table(client)} o
    WHERE TRUE
      {_active_filter(client)}
    ORDER BY o.data_ocorrencia DESC, o.created_at DESC
    """
    try:
        df = client.query(query).to_dataframe()
        if not df.empty:
            df["data_ocorrencia"] = pd.to_datetime(df["data_ocorrencia"]).dt.date
            for ts_col in ["created_at", "updated_at"]:
                df[ts_col] = (
                    pd.to_datetime(df[ts_col])
                    .dt.tz_convert("America/Sao_Paulo")
                    .dt.tz_localize(None)
                )
        return df
    except Exception as e:
        st.error(f"Erro ao buscar ocorrências: {e}")
        return pd.DataFrame()


def insert_ocorrencia(canal: str, data_ocorrencia, problema: str,
                      erro_operacional: bool, descricao: str,
                      numero_pedido: str = None, responsavel: str = None,
                      original_created_at=None):
    client = get_bigquery_client()
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "id": str(uuid.uuid4()),
        "canal": canal,
        "data_ocorrencia": str(data_ocorrencia),
        "problema": problema,
        "erro_operacional": erro_operacional,
        "responsavel": responsavel or None,
        "numero_pedido": numero_pedido.strip() if numero_pedido else None,
        "descricao": descricao.strip() if descricao else None,
        "created_at": original_created_at.isoformat() if original_created_at else now,
        "updated_at": now if original_created_at else None,
    }
    errors = client.insert_rows_json(f"{client.project}.{DATASET}.{TABLE}", [row])
    if errors:
        raise RuntimeError(f"Erro ao inserir: {errors}")
    st.cache_data.clear()


def delete_ocorrencia(record_id: str):
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
