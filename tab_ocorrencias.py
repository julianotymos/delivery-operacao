import streamlit as st
import pandas as pd
from datetime import date
from read_ocorrencias import (
    ensure_table_exists, read_ocorrencias, insert_ocorrencia,
    delete_ocorrencia, CANAIS, PROBLEMAS
)


def _form_ocorrencia(key_prefix: str, defaults: dict = None):
    """Renderiza os campos do formulário. Retorna (canal, data, problema, erro_op, numero_pedido, descricao)."""
    d = defaults or {}

    problema_idx = PROBLEMAS.index(d["problema"]) if d.get("problema") in PROBLEMAS else 0
    problema = st.selectbox("Problema *", PROBLEMAS, index=problema_idx, key=f"{key_prefix}_problema")
    is_fechamento = problema == "Fechamento de Loja"

    col1, col2 = st.columns(2)
    with col1:
        canal_idx = CANAIS.index(d["canal"]) if d.get("canal") in CANAIS else 0
        canal = st.selectbox("Canal *", CANAIS, index=canal_idx, key=f"{key_prefix}_canal")
        data_oc = st.date_input(
            "Data da ocorrência *",
            value=d.get("data_ocorrencia", date.today()),
            key=f"{key_prefix}_data"
        )
    with col2:
        erro_op = st.radio(
            "Erro operacional *",
            options=[True, False],
            index=0 if d.get("erro_operacional", True) else 1,
            format_func=lambda x: "Sim" if x else "Não",
            horizontal=True,
            help="'Sim' = conta como penalidade de R$ 8,00 no bônus",
            key=f"{key_prefix}_erro_op"
        )
        numero_pedido = None
        if not is_fechamento:
            numero_pedido = st.text_input(
                "Número do Pedido",
                value=d.get("numero_pedido", "") or "",
                placeholder="Ex: 123456789",
                max_chars=50,
                key=f"{key_prefix}_num_pedido"
            )

    descricao = st.text_area(
        "Descrição",
        value=d.get("descricao", "") or "",
        placeholder="Resumo do que ocorreu...",
        max_chars=500,
        key=f"{key_prefix}_descricao"
    )

    return canal, data_oc, problema, erro_op, numero_pedido, descricao


def tab_ocorrencias():
    st.subheader("📋 Registro de Ocorrências — Bônus Delivery")
    st.markdown("Registre cancelamentos, reenvios e fechamentos de loja para o cálculo do bônus.")

    ensure_table_exists()

    if "editando_id" not in st.session_state:
        st.session_state.editando_id = None

    # ── FORMULÁRIO DE CADASTRO ──────────────────────────────────────────────
    with st.expander("➕ Nova ocorrência", expanded=False):
        with st.form("form_nova_ocorrencia", clear_on_submit=True):
            canal, data_oc, problema, erro_op, numero_pedido, descricao = _form_ocorrencia("novo")
            submitted = st.form_submit_button("💾 Salvar ocorrência", type="primary")

        if submitted:
            try:
                insert_ocorrencia(canal, data_oc, problema, erro_op, descricao, numero_pedido)
                st.success("Ocorrência registrada com sucesso!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar: {e}")

    st.markdown("---")

    # ── FILTROS ─────────────────────────────────────────────────────────────
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        f_canal = st.selectbox("Filtrar canal", ["Todos"] + CANAIS, key="f_canal")
    with col_f2:
        f_problema = st.selectbox("Filtrar problema", ["Todos"] + PROBLEMAS, key="f_prob")
    with col_f3:
        f_erro_op = st.selectbox("Erro operacional", ["Todos", "Sim", "Não"], key="f_erro")

    # ── TABELA DE REGISTROS ─────────────────────────────────────────────────
    df = read_ocorrencias()

    if df.empty:
        st.info("Nenhuma ocorrência registrada.")
        return

    df_filtrado = df.copy()
    if f_canal != "Todos":
        df_filtrado = df_filtrado[df_filtrado["canal"] == f_canal]
    if f_problema != "Todos":
        df_filtrado = df_filtrado[df_filtrado["problema"] == f_problema]
    if f_erro_op == "Sim":
        df_filtrado = df_filtrado[df_filtrado["erro_operacional"] == True]
    elif f_erro_op == "Não":
        df_filtrado = df_filtrado[df_filtrado["erro_operacional"] == False]

    if df_filtrado.empty:
        st.info("Nenhuma ocorrência para os filtros selecionados.")
        return

    st.markdown(f"**{len(df_filtrado)} registro(s) encontrado(s)**")

    df_display = df_filtrado.copy()
    df_display["Selecionar"] = False
    df_display["Erro Operacional"] = df_display["erro_operacional"].map({True: "Sim", False: "Não"})
    df_display["Data"] = pd.to_datetime(df_display["data_ocorrencia"]).apply(
        lambda d: d.strftime("%d/%m/%Y")
    )
    df_display["Cadastrado em"] = pd.to_datetime(df_display["created_at"]).dt.strftime("%d/%m/%Y %H:%M")
    df_display["numero_pedido"] = df_display["numero_pedido"].fillna("—")

    edited = st.data_editor(
        df_display[[
            "Selecionar", "Data", "canal", "problema",
            "Erro Operacional", "numero_pedido", "descricao", "Cadastrado em", "id"
        ]],
        column_config={
            "Selecionar":       st.column_config.CheckboxColumn("☑️"),
            "Data":             st.column_config.TextColumn("Data", disabled=True),
            "canal":            st.column_config.TextColumn("Canal", disabled=True),
            "problema":         st.column_config.TextColumn("Problema", disabled=True),
            "Erro Operacional": st.column_config.TextColumn("Erro Operacional", disabled=True),
            "numero_pedido":    st.column_config.TextColumn("Nº Pedido", disabled=True),
            "descricao":        st.column_config.TextColumn("Descrição", disabled=True),
            "Cadastrado em":    st.column_config.TextColumn("Cadastrado em", disabled=True),
            "id":               None,
        },
        width='stretch',
        hide_index=True,
        key="tabela_ocorrencias",
    )

    ids_selecionados = edited.loc[edited["Selecionar"] == True, "id"].tolist()

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
        registro = df[df["id"] == st.session_state.editando_id]
        if not registro.empty:
            row = registro.iloc[0]
            st.markdown("---")
            st.markdown("### ✏️ Editar ocorrência")

            with st.form("form_editar_ocorrencia"):
                defaults = {
                    "canal":           row["canal"],
                    "data_ocorrencia": row["data_ocorrencia"],
                    "problema":        row["problema"],
                    "erro_operacional": bool(row["erro_operacional"]),
                    "numero_pedido":   row["numero_pedido"] if row["numero_pedido"] != "—" else "",
                    "descricao":       row["descricao"],
                }
                canal, data_oc, problema, erro_op, numero_pedido, descricao = _form_ocorrencia("edit", defaults)

                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    salvar = st.form_submit_button("💾 Salvar alterações", type="primary")
                with col_btn2:
                    cancelar = st.form_submit_button("✖ Cancelar")

            if salvar:
                try:
                    delete_ocorrencia(st.session_state.editando_id)
                    insert_ocorrencia(canal, data_oc, problema, erro_op, descricao, numero_pedido)
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
        int(df["erro_operacional"].sum()),
        help="Cada uma desconta R$ 8,00 do bônus"
    )
    col_r3.metric(
        "Dias de fechamento de loja",
        int(df[df["problema"] == "Fechamento de Loja"]["data_ocorrencia"].nunique()),
        help="Dias cujos pedidos são excluídos do bônus"
    )
