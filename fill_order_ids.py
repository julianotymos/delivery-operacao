"""
Preenche ORDER_ID em BONUS_OCCURRENCES via join com ORDERS_TABLE
usando SHORT_ID + SALES_CHANNEL. Usa o pedido com data mais proxima
da OCCURRENCE_DATE quando houver mais de um match.

Executar: python fill_order_ids.py
"""
from get_bigquery_client import get_bigquery_client

DATASET = "DELIVERY"


def run():
    client = get_bigquery_client()
    p = client.project

    print("Verificando registros sem ORDER_ID...")
    stats_before = client.query(f"""
        SELECT
            COUNT(*) AS total,
            COUNTIF(ORDER_ID IS NOT NULL) AS com_order_id,
            COUNTIF(ORDER_ID IS NULL)     AS sem_order_id
        FROM `{p}.{DATASET}.BONUS_OCCURRENCES`
    """).to_dataframe()
    print(f"  Total         : {stats_before['total'].iloc[0]}")
    print(f"  Com ORDER_ID  : {stats_before['com_order_id'].iloc[0]}")
    print(f"  Sem ORDER_ID  : {stats_before['sem_order_id'].iloc[0]}")

    print("\nPreenchendo ORDER_ID via SHORT_ID + SALES_CHANNEL...")
    client.query(f"""
        CREATE OR REPLACE TABLE `{p}.{DATASET}.BONUS_OCCURRENCES` AS
        WITH matches AS (
            -- Para cada ocorrencia sem ORDER_ID, ranqueia os pedidos candidatos
            -- pelo menor intervalo de dias entre OCCURRENCE_DATE e a data do pedido
            SELECT
                bo.ID              AS bo_id,
                ot.id              AS matched_order_id,
                ROW_NUMBER() OVER (
                    PARTITION BY bo.ID
                    ORDER BY ABS(DATE_DIFF(
                        DATE(ot.CREATED_AT, 'America/Sao_Paulo'),
                        bo.OCCURRENCE_DATE,
                        DAY
                    ))
                ) AS rn
            FROM `{p}.{DATASET}.BONUS_OCCURRENCES` bo
            INNER JOIN `{p}.{DATASET}.ORDERS_TABLE` ot
                ON  ot.SHORT_ID      = bo.SHORT_ID
                AND ot.SALES_CHANNEL = bo.SALES_CHANNEL
            INNER JOIN `{p}.{DATASET}.ORDER_PROBLEM_EVENTS` pe
                ON pe.ORDER_ID = ot.id
            WHERE bo.ORDER_ID IS NULL
              AND ot.CURRENT_STATUS IN ('CONCLUDED', 'CANCELLED', 'PARTIALLY_CANCELLED')
        )
        SELECT
            bo.ID,
            bo.SALES_CHANNEL,
            bo.OCCURRENCE_DATE,
            bo.PROBLEM_TYPE,
            bo.IS_OPERATIONAL_ERROR,
            bo.EMPLOYEE_NAME,
            bo.SHORT_ID,
            COALESCE(bo.ORDER_ID, m.matched_order_id) AS ORDER_ID,
            bo.DESCRIPTION,
            bo.CREATED_AT,
            bo.UPDATED_AT
        FROM `{p}.{DATASET}.BONUS_OCCURRENCES` bo
        LEFT JOIN matches m ON m.bo_id = bo.ID AND m.rn = 1
    """).result()
    print("[OK] Tabela recriada com ORDER_ID preenchido.")

    print("\nResultado apos preenchimento:")
    stats_after = client.query(f"""
        SELECT
            COUNT(*) AS total,
            COUNTIF(ORDER_ID IS NOT NULL) AS com_order_id,
            COUNTIF(ORDER_ID IS NULL)     AS sem_order_id
        FROM `{p}.{DATASET}.BONUS_OCCURRENCES`
    """).to_dataframe()
    print(f"  Total         : {stats_after['total'].iloc[0]}")
    print(f"  Com ORDER_ID  : {stats_after['com_order_id'].iloc[0]}")
    print(f"  Sem ORDER_ID  : {stats_after['sem_order_id'].iloc[0]}")


if __name__ == "__main__":
    run()
