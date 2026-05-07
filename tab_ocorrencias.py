import streamlit as st
import pandas as pd
from datetime import date
from read_ocorrencias import (
    ensure_table_exists, read_ocorrencias, read_responsaveis,
    insert_ocorrencia, delete_ocorrencia, CANAIS, PROBLEMAS
)
from read_problem_events import read_pending_events, translate_problem_type


_EVENT_PROBLEM_MAP = {
    "CANCELAMENTO_TOTAL":   "Cancelamento",
    "CANCELAMENTO":         "Cancelamento",
    "CANCELAMENTO_PARCIAL": "Cancelamento Parcial",
    "REEMBOLSO":            "Ocorrência",
    "REENVIO":              "Ocorrência",
    "RECLAMACAO":           "Ocorrência",
}

_STATUS_LABELS = {
    "CONCLUDED":           "Concluído",
    "CANCELLED":           "Cancelado",
    "PARTIALLY_CANCELLED": "Cancelado Parcial",
}


def _form_ocorrencia(key_prefix: str, defaults: dict = None, locked: set = None):
    d = defaults or {}
    locked = locked or set()
    responsaveis = read_responsaveis()

    problema_idx = PROBLEMAS.index(d.get("PROBLEM_TYPE", "")) if d.get("PROBLEM_TYPE") in PROBLEMAS else 0
    problema = st.selectbox(
        "Problema *", PROBLEMAS, index=problema_idx,
        key=f"{key_prefix}_problema", disabled="PROBLEM_TYPE" in locked
    )
    is_fechamento = problema == "Fechamento de Loja"

    col1, col2 = st.columns(2)
    with col1:
        canal_idx = CANAIS.index(d.get("SALES_CHANNEL", "")) if d.get("SALES_CHANNEL") in CANAIS else 0
        canal = st.selectbox(
            "Canal *", CANAIS, index=canal_idx,
            key=f"{key_prefix}_canal", disabled="SALES_CHANNEL" in locked
        )
        data_oc = st.date_input(
            "Data da ocorrência *",
            value=d.get("OCCURRENCE_DATE", date.today()),
            key=f"{key_prefix}_data",
            disabled="OCCURRENCE_DATE" in locked
        )
    with col2:
        emp = d.get("EMPLOYEE_NAME", "")
        resp_idx = responsaveis.index(emp) if emp in responsaveis else 0
        responsavel = st.selectbox("Responsável *", responsaveis, index=resp_idx, key=f"{key_prefix}_responsavel")
        erro_op = st.radio(
            "Erro operacional *",
            options=[True, False],
            index=0 if d.get("IS_OPERATIONAL_ERROR", True) else 1,
            format_func=lambda x: "Sim" if x else "Não",
            horizontal=True,
            help="'Sim' = conta como penalidade de R$ 8,00 no bônus",
            key=f"{key_prefix}_erro_op"
        )

    short_id = None
    if not is_fechamento:
        short_id = st.text_input(
            "Número do Pedido",
            value=d.get("SHORT_ID", "") or "",
            placeholder="Ex: 123456789",
            max_chars=50,
            key=f"{key_prefix}_num_pedido",
            disabled="SHORT_ID" in locked
        )

    descricao = st.text_area(
        "Descrição",
        value=d.get("DESCRIPTION", "") or "",
        placeholder="Resumo do que ocorreu...",
        max_chars=500,
        key=f"{key_prefix}_descricao"
    )

    return canal, data_oc, problema, erro_op, responsavel, short_id, descricao


def tab_ocorrencias(sales_channel: str = None):
    st.subheader("📋 Registro de Ocorrências — Bônus Delivery")

    ensure_table_exists()

    if "editando_id" not in st.session_state:
        st.session_state.editando_id = None
    if "processando_order_id" not in st.session_state:
        st.session_state.processando_order_id = None

    sub_pendentes, sub_ocorrencias = st.tabs(["⏳ Pendentes", "📝 Ocorrências"])

    with sub_pendentes:
        _tab_pendentes(sales_channel)

    with sub_ocorrencias:
        _tab_crud()


def _tab_pendentes(sales_channel: str):
    st.markdown("Eventos com problemas que ainda não possuem ocorrência registrada.")

    col_d1, col_d2 = st.columns(2)
    with col_d1:
        start = st.date_input("De", value=date(2026, 4, 25), key="pend_start")
    with col_d2:
        end = st.date_input("Até", value=date.today(), key="pend_end")

    df = read_pending_events(start, end, sales_channel)

    if df.empty:
        st.success("Nenhum evento pendente no período. ✅")
        return

    st.markdown(f"**{len(df)} evento(s) pendente(s)**")

    df_display = df.copy()
    df_display["Data"] = pd.to_datetime(df_display["data_pedido"]).apply(lambda d: d.strftime("%d/%m/%Y"))
    df_display["Valor"] = df_display["valor_liquido"].apply(lambda v: f"R$ {v:,.2f}" if pd.notna(v) else "—")
    df_display["Problema"] = df_display["problem_type"].apply(translate_problem_type)
    df_display["status"] = df_display["status"].map(_STATUS_LABELS).fillna(df_display["status"])
    df_display["Selecionar"] = False

    edited = st.data_editor(
        df_display[["Selecionar", "Data", "canal", "short_id", "status", "Problema", "cancel_descricao", "cancel_motivo", "Valor", "order_id"]],
        column_config={
            "Selecionar":       st.column_config.CheckboxColumn("☑️"),
            "Data":             st.column_config.TextColumn("Data", disabled=True),
            "canal":            st.column_config.TextColumn("Canal", disabled=True),
            "short_id":         st.column_config.TextColumn("Pedido", disabled=True),
            "status":           st.column_config.TextColumn("Status", disabled=True),
            "Problema":         st.column_config.TextColumn("Problema", disabled=True),
            "cancel_descricao": st.column_config.TextColumn("Descrição do Código", disabled=True),
            "cancel_motivo":    st.column_config.TextColumn("Motivo", disabled=True),
            "Valor":            st.column_config.TextColumn("Valor", disabled=True),
            "order_id":         None,
        },
        use_container_width=True,
        hide_index=True,
        key="tabela_pendentes",
    )

    ids_sel = edited.loc[edited["Selecionar"] == True, "order_id"].tolist()
    if st.button("📝 Criar Ocorrência", disabled=len(ids_sel) != 1, key="btn_criar_oc"):
        st.session_state.processando_order_id = ids_sel[0]

    if st.session_state.processando_order_id:
        row_data = df[df["order_id"] == st.session_state.processando_order_id]
        if not row_data.empty:
            row = row_data.iloc[0]
            st.markdown("---")
            st.markdown(f"### 📝 Nova ocorrência — Pedido `{row['short_id']}`")

            with st.form("form_pendente_ocorrencia"):
                mapped_problem = _EVENT_PROBLEM_MAP.get(row["problem_type"], "Ocorrência")
                defaults = {
                    "SALES_CHANNEL":        row["canal"],
                    "OCCURRENCE_DATE":      row["data_pedido"],
                    "PROBLEM_TYPE":         mapped_problem,
                    "IS_OPERATIONAL_ERROR": True,
                    "SHORT_ID":             str(row["short_id"]),
                }
                canal, data_oc, problema, erro_op, responsavel, short_id, descricao = _form_ocorrencia(
                    "pend", defaults,
                    locked={"PROBLEM_TYPE", "SALES_CHANNEL", "OCCURRENCE_DATE", "SHORT_ID"}
                )
                col_b1, col_b2 = st.columns(2)
                with col_b1:
                    salvar = st.form_submit_button("💾 Salvar e marcar como processado", type="primary")
                with col_b2:
                    cancelar = st.form_submit_button("✖ Cancelar")

            if salvar:
                try:
                    insert_ocorrencia(
                        canal, data_oc, problema, erro_op, descricao,
                        short_id, responsavel,
                        order_id=st.session_state.processando_order_id
                    )
                    st.session_state.processando_order_id = None
                    st.success("Ocorrência registrada! Evento marcado como processado.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")

            if cancelar:
                st.session_state.processando_order_id = None
                st.rerun()


def _tab_crud():
    st.markdown("Ocorrências registradas (fechamentos de loja e ocorrências vinculadas a pedidos).")

    if "editando_id" not in st.session_state:
        st.session_state.editando_id = None

    # ── FILTROS ──────────────────────────────────────────────────────────────
    col_f1, col_f2, col_f3, col_f4, col_f5 = st.columns([2, 2, 2, 2, 2])
    with col_f1:
        f_data_ini = st.date_input("De", value=date(2026, 4, 25), key="crud_data_ini")
    with col_f2:
        f_data_fim = st.date_input("Até", value=date.today(), key="crud_data_fim")
    with col_f3:
        f_num_pedido = st.text_input("Nº Pedido", placeholder="Ex: 12345", key="crud_num_pedido")
    with col_f4:
        f_canal = st.selectbox("Canal", ["Todos"] + CANAIS, key="f_canal")
    with col_f5:
        f_erro_op = st.selectbox("Erro operacional", ["Todos", "Sim", "Não"], key="f_erro")

    # ── TABELA DE REGISTROS ──────────────────────────────────────────────────
    df = read_ocorrencias()

    if df.empty:
        st.info("Nenhuma ocorrência registrada.")
        _render_form_novo()
        return

    df_filtrado = df.copy()
    df_filtrado["_date"] = pd.to_datetime(df_filtrado["OCCURRENCE_DATE"]).dt.date
    df_filtrado = df_filtrado[
        (df_filtrado["_date"] >= f_data_ini) &
        (df_filtrado["_date"] <= f_data_fim)
    ]
    if f_num_pedido.strip():
        df_filtrado = df_filtrado[
            df_filtrado["SHORT_ID"].fillna("").str.contains(f_num_pedido.strip(), case=False)
        ]
    if f_canal != "Todos":
        df_filtrado = df_filtrado[df_filtrado["SALES_CHANNEL"] == f_canal]
    if f_erro_op == "Sim":
        df_filtrado = df_filtrado[df_filtrado["IS_OPERATIONAL_ERROR"] == True]
    elif f_erro_op == "Não":
        df_filtrado = df_filtrado[df_filtrado["IS_OPERATIONAL_ERROR"] == False]

    df_filtrado = df_filtrado.drop(columns=["_date"])

    if df_filtrado.empty:
        st.info("Nenhuma ocorrência para os filtros selecionados.")
        _render_form_novo()
        return

    st.markdown(f"**{len(df_filtrado)} registro(s) encontrado(s)**")

    df_display = df_filtrado.copy()
    df_display["Selecionar"] = False
    df_display["Erro Operacional"] = df_display["IS_OPERATIONAL_ERROR"].map({True: "Sim", False: "Não"})
    df_display["Data"] = pd.to_datetime(df_display["OCCURRENCE_DATE"]).apply(lambda d: d.strftime("%d/%m/%Y"))
    df_display["Cadastrado em"] = pd.to_datetime(df_display["CREATED_AT"]).dt.strftime("%d/%m/%Y %H:%M")
    df_display["Atualizado em"] = df_display["UPDATED_AT"].apply(
        lambda v: pd.to_datetime(v).strftime("%d/%m/%Y %H:%M") if pd.notna(v) else "—"
    )
    df_display["SHORT_ID"]      = df_display["SHORT_ID"].fillna("—")
    df_display["EMPLOYEE_NAME"] = df_display["EMPLOYEE_NAME"].fillna("—")

    edited = st.data_editor(
        df_display[[
            "Selecionar", "Data", "SALES_CHANNEL", "PROBLEM_TYPE", "EMPLOYEE_NAME",
            "Erro Operacional", "SHORT_ID", "DESCRIPTION",
            "Cadastrado em", "Atualizado em", "ID"
        ]],
        column_config={
            "Selecionar":       st.column_config.CheckboxColumn("☑️"),
            "Data":             st.column_config.TextColumn("Data", disabled=True),
            "SALES_CHANNEL":    st.column_config.TextColumn("Canal", disabled=True),
            "PROBLEM_TYPE":     st.column_config.TextColumn("Problema", disabled=True),
            "EMPLOYEE_NAME":    st.column_config.TextColumn("Responsável", disabled=True),
            "Erro Operacional": st.column_config.TextColumn("Erro Operacional", disabled=True),
            "SHORT_ID":         st.column_config.TextColumn("Nº Pedido", disabled=True),
            "DESCRIPTION":      st.column_config.TextColumn("Descrição", disabled=True),
            "Cadastrado em":    st.column_config.TextColumn("Cadastrado em", disabled=True),
            "Atualizado em":    st.column_config.TextColumn("Atualizado em", disabled=True),
            "ID":               None,
        },
        use_container_width=True,
        hide_index=True,
        key="tabela_ocorrencias",
    )

    ids_selecionados = edited.loc[edited["Selecionar"] == True, "ID"].tolist()

    col_btn1, col_btn2, _ = st.columns([1, 1, 6])
    btn_editar  = col_btn1.button("✏️ Editar",  disabled=len(ids_selecionados) != 1)
    btn_excluir = col_btn2.button("🗑️ Excluir", disabled=len(ids_selecionados) == 0, type="primary")

    if btn_editar and len(ids_selecionados) == 1:
        st.session_state.editando_id = ids_selecionados[0]

    if btn_excluir and ids_selecionados:
        for rid in ids_selecionados:
            try:
                delete_ocorrencia(rid)
            except Exception as e:
                st.error(f"Erro ao excluir: {e}")
        st.success(f"{len(ids_selecionados)} registro(s) excluído(s) com sucesso!")
        st.rerun()

    # ── EDIÇÃO ───────────────────────────────────────────────────────────────
    if st.session_state.editando_id:
        registro = df[df["ID"] == st.session_state.editando_id]
        if not registro.empty:
            row = registro.iloc[0]
            st.markdown("---")
            st.markdown("### ✏️ Editar ocorrência")

            with st.form("form_editar_ocorrencia"):
                defaults = {
                    "SALES_CHANNEL":        row["SALES_CHANNEL"],
                    "OCCURRENCE_DATE":      row["OCCURRENCE_DATE"],
                    "PROBLEM_TYPE":         row["PROBLEM_TYPE"],
                    "IS_OPERATIONAL_ERROR": bool(row["IS_OPERATIONAL_ERROR"]),
                    "EMPLOYEE_NAME":        row.get("EMPLOYEE_NAME", ""),
                    "SHORT_ID":             row["SHORT_ID"] if row["SHORT_ID"] != "—" else "",
                    "DESCRIPTION":          row["DESCRIPTION"],
                }
                canal, data_oc, problema, erro_op, responsavel, short_id, descricao = _form_ocorrencia("edit", defaults)

                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    salvar = st.form_submit_button("💾 Salvar alterações", type="primary")
                with col_btn2:
                    cancelar = st.form_submit_button("✖ Cancelar")

            if salvar:
                try:
                    delete_ocorrencia(st.session_state.editando_id)
                    insert_ocorrencia(canal, data_oc, problema, erro_op, descricao, short_id, responsavel,
                                      original_created_at=row["CREATED_AT"])
                    st.session_state.editando_id = None
                    st.success("Ocorrência atualizada com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao atualizar: {e}")

            if cancelar:
                st.session_state.editando_id = None
                st.rerun()

    # ── RESUMO ───────────────────────────────────────────────────────────────
    st.markdown("---")
    col_r1, col_r2, col_r3 = st.columns(3)
    col_r1.metric("Total de ocorrências", len(df))
    col_r2.metric(
        "Penalidades (Erro operacional Sim)",
        int(df["IS_OPERATIONAL_ERROR"].sum()),
        help="Cada uma desconta R$ 8,00 do bônus"
    )
    col_r3.metric(
        "Dias de fechamento de loja",
        int(df[df["PROBLEM_TYPE"] == "Fechamento de Loja"]["OCCURRENCE_DATE"].nunique()),
        help="Dias cujos pedidos são excluídos do bônus"
    )

    # ── CADASTRO (ao final da página) ────────────────────────────────────────
    st.markdown("---")
    _render_form_novo()


def _render_form_novo():
    with st.expander("➕ Nova ocorrência (Fechamento de Loja)", expanded=False):
        with st.form("form_nova_ocorrencia", clear_on_submit=True):
            canal, data_oc, problema, erro_op, responsavel, _, descricao = _form_ocorrencia(
                "novo",
                defaults={"PROBLEM_TYPE": "Fechamento de Loja"},
                locked={"PROBLEM_TYPE", "SHORT_ID"},
            )
            submitted = st.form_submit_button("💾 Salvar ocorrência", type="primary")

        if submitted:
            try:
                insert_ocorrencia(canal, data_oc, problema, erro_op, descricao, None, responsavel)
                st.success("Ocorrência registrada com sucesso!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar: {e}")
