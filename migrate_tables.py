"""
Migracao das tabelas de bonus para nomenclatura EN/UPPERCASE.
Mantem as tabelas originais intactas.

Executar: python migrate_tables.py
"""
from get_bigquery_client import get_bigquery_client

DATASET = "DELIVERY"

def column_exists(client, table_ref: str, column: str) -> bool:
    result = client.query(f"""
        SELECT COUNT(*) AS cnt
        FROM `{client.project}.{DATASET}.INFORMATION_SCHEMA.COLUMNS`
        WHERE TABLE_NAME = '{table_ref.split('.')[-1]}'
          AND COLUMN_NAME = '{column}'
    """).to_dataframe()
    return result["cnt"].iloc[0] > 0


def run():
    client = get_bigquery_client()
    p = client.project

    # -- BONUS_OCCURRENCES ---------------------------------------------------
    print("Migrando bonus_ocorrencias -> BONUS_OCCURRENCES...")

    has_order_id  = column_exists(client, f"{p}.{DATASET}.bonus_ocorrencias", "order_id")
    has_updated   = column_exists(client, f"{p}.{DATASET}.bonus_ocorrencias", "updated_at")
    has_responsavel = column_exists(client, f"{p}.{DATASET}.bonus_ocorrencias", "responsavel")
    has_numero    = column_exists(client, f"{p}.{DATASET}.bonus_ocorrencias", "numero_pedido")

    order_id_sel  = "order_id"      if has_order_id  else "CAST(NULL AS STRING)"
    updated_sel   = "updated_at"    if has_updated   else "CAST(NULL AS TIMESTAMP)"
    resp_sel      = "responsavel"   if has_responsavel else "CAST(NULL AS STRING)"
    numero_sel    = "numero_pedido" if has_numero    else "CAST(NULL AS STRING)"

    client.query(f"""
        CREATE OR REPLACE TABLE `{p}.{DATASET}.BONUS_OCCURRENCES` AS
        SELECT
            id                  AS ID,
            canal               AS SALES_CHANNEL,
            data_ocorrencia     AS OCCURRENCE_DATE,
            problema            AS PROBLEM_TYPE,
            erro_operacional    AS IS_OPERATIONAL_ERROR,
            {resp_sel}          AS EMPLOYEE_NAME,
            {numero_sel}        AS SHORT_ID,
            {order_id_sel}      AS ORDER_ID,
            descricao           AS DESCRIPTION,
            created_at          AS CREATED_AT,
            {updated_sel}       AS UPDATED_AT
        FROM `{p}.{DATASET}.bonus_ocorrencias`
    """).result()
    print("  [OK] BONUS_OCCURRENCES criada.")

    # -- BONUS_OCCURRENCES_TOMBSTONE -----------------------------------------
    print("Migrando bonus_ocorrencias_tombstone -> BONUS_OCCURRENCES_TOMBSTONE...")
    client.query(f"""
        CREATE OR REPLACE TABLE `{p}.{DATASET}.BONUS_OCCURRENCES_TOMBSTONE` AS
        SELECT
            id          AS ID,
            deleted_at  AS DELETED_AT
        FROM `{p}.{DATASET}.bonus_ocorrencias_tombstone`
    """).result()
    print("  [OK] BONUS_OCCURRENCES_TOMBSTONE criada.")

    # -- BONUS_EMPLOYEES -----------------------------------------------------
    print("Migrando bonus_responsaveis -> BONUS_EMPLOYEES...")
    client.query(f"""
        CREATE OR REPLACE TABLE `{p}.{DATASET}.BONUS_EMPLOYEES` AS
        SELECT
            id      AS ID,
            nome    AS NAME,
            ativo   AS IS_ACTIVE
        FROM `{p}.{DATASET}.bonus_responsaveis`
    """).result()
    print("  [OK] BONUS_EMPLOYEES criada.")

    print("\nMigracao concluida. Tabelas originais mantidas.")


if __name__ == "__main__":
    run()
