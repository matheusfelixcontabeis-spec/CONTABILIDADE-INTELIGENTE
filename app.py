# ---------- TAB 3: Contabilidade (lançamentos, balancete e PDF) ----------
with tab3:
    st.subheader("Lançamentos contábeis a partir dos documentos aprovados")

    if not supabase_ok:
        st.info("Conecte o Supabase para gerar lançamentos reais.")
    else:
        try:
            aprovados = supabase.table("documentos").select("*").eq("status", "aprovado").execute()
            docs_aprovados = aprovados.data
        except Exception as e:
            st.error(f"Erro ao buscar documentos aprovados: {e}")
            docs_aprovados = []

        lancamentos = []
        for doc in docs_aprovados:
            # Ajuste as contas conforme seu plano de contas real
            lancamentos.append(gerar_lancamento(
                valor=doc.get("valor", 0) or 0,
                historico=f"{doc['tipo_documento']} - {doc['cliente_nome']}",
                conta_debito="Despesas",
                conta_credito="Caixa/Bancos",
                data=doc.get("criado_em", "")[:10],
            ))

        if lancamentos:
            st.write(f"**{len(lancamentos)} lançamento(s) gerado(s) a partir de documentos aprovados**")
            st.dataframe(lancamentos, use_container_width=True)
        else:
            st.info("Nenhum documento aprovado ainda. Aprove documentos na aba anterior.")

        st.divider()

        # ---- Conciliação bancária ----
        st.subheader("Conciliação de extrato bancário")
        st.caption("Envie um CSV com colunas: data,valor (ex: 2025-01-10,1500.00)")
        extrato_file = st.file_uploader("Extrato bancário (CSV)", type=["csv"], key="extrato")

        extrato = []
        if extrato_file is not None:
            import csv, io
            content = extrato_file.read().decode("utf-8")
            reader = csv.DictReader(io.StringIO(content))
            for row in reader:
                extrato.append({"data": row["data"], "valor": float(row["valor"])})

            conciliados, pendentes = conciliar_extrato(extrato, lancamentos)
            st.success(f"{len(conciliados)} movimento(s) conciliado(s)")
            if pendentes:
                st.warning(f"{len(pendentes)} movimento(s) do extrato sem lançamento correspondente")
                st.dataframe(pendentes, use_container_width=True)

        st.divider()

        # ---- Balancete e PDF ----
        st.subheader("Balancete de verificação")
        if lancamentos:
            balancete = calcular_balancete(lancamentos)
            st.dataframe(balancete, use_container_width=True)

            if st.button("📄 Gerar PDF do balancete", use_container_width=True):
                caminho = gerar_pdf_balancete(balancete, caminho="/tmp/balancete.pdf")
                with open(caminho, "rb") as f:
                    st.download_button(
                        "⬇️ Baixar PDF",
                        data=f,
                        file_name="balancete.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )
        else:
            st.info("Sem lançamentos para montar o balancete ainda.")
