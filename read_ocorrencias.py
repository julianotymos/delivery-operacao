import uuid
import streamlit as st
import pandas as pd
from datetime import datetime, timezone
from google.cloud import bigquery
from get_bigquery_client import get_bigquery_client

DATASET = "DELIVERY"
TABLE            = "BONUS_OCCURRENCES"
TABLE_TOMBSTONE  = "BONUS_OCCURRENCES_TOMBSTONE"
TABLE_EMPLOYEES  = "BONUS_EMPLOYEES"

CANAIS   = ["iFood", "99food", "keeta"]
PROBLEMAS = ["Cancelamento", "Cancelamento Parcial", "Ocorrência", "Fechamento de Loja"]

_EMPLOYEES_DEFAULT = [
    "Taina", "Keila", "Stefanie", "Eduarda",
    "Juliana", "Freelance", "Desconhecido"
]


def _t(client):   return f"`{client.project}.{DATASET}.{TABLE}`"
def _ts(client):  return f"`{client.project}.{DATASET}.{TABLE_TOMBSTONE}`"
def _emp(client): return f"`{client.project}.{DATASET}.{TABLE_EMPLOYEES}`"


def ensure_table_exists():
    client = get_bigquery_client()
    p = client.project

    # BONUS_OCCURRENCES
    table_ref = f"{p}.{DATASET}.{TABLE}"
    client.create_table(bigquery.Table(table_ref, [
        bigquery.SchemaField("ID",                   "STRING",    mode="REQUIRED"),
        bigquery.SchemaField("SALES_CHANNEL",        "STRING",    mode="REQUIRED"),
        bigquery.SchemaField("OCCURRENCE_DATE",      "DATE",      mode="REQUIRED"),
        bigquery.SchemaField("PROBLEM_TYPE",         "STRING",    mode="REQUIRED"),
        bigquery.SchemaField("IS_OPERATIONAL_ERROR", "BOOL",      mode="REQUIRED"),
        bigquery.SchemaField("EMPLOYEE_NAME",        "STRING",    mode="NULLABLE"),
        bigquery.SchemaField("SHORT_ID",             "STRING",    mode="NULLABLE"),
        bigquery.SchemaField("ORDER_ID",             "STRING",    mode="NULLABLE"),
        bigquery.SchemaField("DESCRIPTION",          "STRING",    mode="NULLABLE"),
        bigquery.SchemaField("CREATED_AT",           "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("UPDATED_AT",           "TIMESTAMP", mode="NULLABLE"),
    ]), exists_ok=True)

    # BONUS_OCCURRENCES_TOMBSTONE
    client.create_table(bigquery.Table(f"{p}.{DATASET}.{TABLE_TOMBSTONE}", [
        bigquery.SchemaField("ID",         "STRING",    mode="REQUIRED"),
        bigquery.SchemaField("DELETED_AT", "TIMESTAMP", mode="REQUIRED"),
    ]), exists_ok=True)

    # BONUS_EMPLOYEES
    emp_ref = f"{p}.{DATASET}.{TABLE_EMPLOYEES}"
    client.create_table(bigquery.Table(emp_ref, [
        bigquery.SchemaField("ID",        "STRING", mode="REQUIRED"),
        bigquery.SchemaField("NAME",      "STRING", mode="REQUIRED"),
        bigquery.SchemaField("IS_ACTIVE", "BOOL",   mode="REQUIRED"),
    ]), exists_ok=True)

    _seed_employees(client, emp_ref)


def _seed_employees(client, emp_ref: str):
    result = client.query(f"SELECT COUNT(*) AS total FROM `{emp_ref}`").to_dataframe()
    if result["total"].iloc[0] > 0:
        return
    rows = [{"ID": str(uuid.uuid4()), "NAME": n, "IS_ACTIVE": True} for n in _EMPLOYEES_DEFAULT]
    client.insert_rows_json(emp_ref, rows)


def _active_filter(client) -> str:
    return f"AND o.ID NOT IN (SELECT ID FROM {_ts(client)})"


@st.cache_data(ttl=300, show_spinner=False)
def read_responsaveis() -> list[str]:
    client = get_bigquery_client()
    try:
        df = client.query(f"""
            SELECT NAME FROM {_emp(client)}
            WHERE IS_ACTIVE = TRUE ORDER BY NAME
        """).to_dataframe()
        return df["NAME"].tolist() if not df.empty else _EMPLOYEES_DEFAULT
    except Exception:
        return _EMPLOYEES_DEFAULT


@st.cache_data(ttl=60, show_spinner=False)
def read_ocorrencias() -> pd.DataFrame:
    client = get_bigquery_client()
    query = f"""
    SELECT o.ID, o.SALES_CHANNEL, o.OCCURRENCE_DATE, o.PROBLEM_TYPE,
           o.IS_OPERATIONAL_ERROR, o.EMPLOYEE_NAME, o.SHORT_ID,
           o.ORDER_ID, o.DESCRIPTION, o.CREATED_AT, o.UPDATED_AT
    FROM {_t(client)} o
    WHERE TRUE {_active_filter(client)}
    ORDER BY o.OCCURRENCE_DATE DESC, o.CREATED_AT DESC
    """
    try:
        df = client.query(query).to_dataframe()
        if not df.empty:
            df["OCCURRENCE_DATE"] = pd.to_datetime(df["OCCURRENCE_DATE"]).dt.date
            for col in ["CREATED_AT", "UPDATED_AT"]:
                df[col] = (
                    pd.to_datetime(df[col])
                    .dt.tz_convert("America/Sao_Paulo")
                    .dt.tz_localize(None)
                )
        return df
    except Exception as e:
        st.error(f"Erro ao buscar ocorrências: {e}")
        return pd.DataFrame()


def insert_ocorrencia(sales_channel: str, occurrence_date, problem_type: str,
                      is_operational_error: bool, description: str,
                      short_id: str = None, employee_name: str = None,
                      original_created_at=None, order_id: str = None):
    client = get_bigquery_client()
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "ID":                   str(uuid.uuid4()),
        "SALES_CHANNEL":        sales_channel,
        "OCCURRENCE_DATE":      str(occurrence_date),
        "PROBLEM_TYPE":         problem_type,
        "IS_OPERATIONAL_ERROR": is_operational_error,
        "EMPLOYEE_NAME":        employee_name or None,
        "SHORT_ID":             short_id.strip() if short_id else None,
        "ORDER_ID":             order_id or None,
        "DESCRIPTION":          description.strip() if description else None,
        "CREATED_AT":           original_created_at.isoformat() if original_created_at else now,
        "UPDATED_AT":           now if original_created_at else None,
    }
    errors = client.insert_rows_json(f"{client.project}.{DATASET}.{TABLE}", [row])
    if errors:
        raise RuntimeError(f"Erro ao inserir: {errors}")
    st.cache_data.clear()


def delete_ocorrencia(record_id: str):
    client = get_bigquery_client()
    errors = client.insert_rows_json(
        f"{client.project}.{DATASET}.{TABLE_TOMBSTONE}",
        [{"ID": record_id, "DELETED_AT": datetime.now(timezone.utc).isoformat()}]
    )
    if errors:
        raise RuntimeError(f"Erro ao excluir: {errors}")
    st.cache_data.clear()


@st.cache_data(ttl=60, show_spinner=False)
def read_fechamentos() -> list[str]:
    client = get_bigquery_client()
    try:
        df = client.query(f"""
            SELECT DISTINCT CAST(o.OCCURRENCE_DATE AS STRING) AS dt
            FROM {_t(client)} o
            WHERE o.PROBLEM_TYPE = 'Fechamento de Loja'
              {_active_filter(client)}
        """).to_dataframe()
        return df["dt"].tolist() if not df.empty else []
    except Exception:
        return []


@st.cache_data(ttl=60, show_spinner=False)
def read_penalidades_por_periodo(bonus_start_date: str) -> pd.DataFrame:
    client = get_bigquery_client()
    try:
        return client.query(f"""
            SELECT
                CASE
                    WHEN o.OCCURRENCE_DATE BETWEEN '{bonus_start_date}' AND '2026-04-30'
                        THEN DATE '{bonus_start_date}'
                    ELSE DATE_TRUNC(o.OCCURRENCE_DATE, MONTH)
                END AS periodo,
                COUNT(*) AS total_erros
            FROM {_t(client)} o
            WHERE o.IS_OPERATIONAL_ERROR = TRUE
              AND o.OCCURRENCE_DATE >= '{bonus_start_date}'
              {_active_filter(client)}
            GROUP BY 1
        """).to_dataframe()
    except Exception:
        return pd.DataFrame(columns=["periodo", "total_erros"])
