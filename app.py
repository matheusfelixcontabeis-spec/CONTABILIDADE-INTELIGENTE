import streamlit as st
from datetime import datetime
import json

from supabase import create_client
from orquestrador import processar_documento

# =========================================================
# CONFIGURAÇÃO DA PÁGINA
# =========================================================
st.set_page_config(page_title="Contadoros AI", page_icon="📊", layout="wide")

# =========================================================
# CONEXÃO COM SUPABASE
# =========================================================
@st.cache_resource
def get_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase = get_supabase()
    supabase_ok = True
except Exception:
    supabase_ok = False

anthropic_key_ok = bool(st.secrets.get("ANTHROPIC_API_KEY"))

# =========================================================
# CABEÇALHO
# =========================================================
st.title("📊 Contadoros AI")
st.caption("Agentes de IA especializados por setor — Sênior roteia, sub-agentes executam em paralelo, humano aprova")

if not supabase_ok:
    st.warning("Supabase não conectado — configure SUPABASE_URL e SUPABASE_KEY em Settings → Secrets.")
if not anthropic_key_ok:
    st.error("ANTHROPIC_API_KEY não configurada em Settings → Secrets. Os agentes não vão funcionar sem ela.")

tab1, tab2, tab3 = st.tabs(["🤖 Processar Documento", "✅ Fila de Conferência", "📑 Contabilidade"])

# =========================================================
# TAB 1: PROCESSAMENTO AUTOMÁTICO PELOS AGENTES
# =========================================================
with tab1:
    st.subheader("1. Envie o documento")
    cliente_nome = st.text_input("Cliente", placeholder="Ex: Padaria Bela Vista MEI")

    uploaded_file = st.file_uploader("PDF com texto (nota fiscal, boleto, holerite, contrato...)", type=["pdf"])
    texto_colado = st.text_area(
        "Ou cole o texto do documento aqui",
        height=200,
        placeholder="Ex: NOTA FISCAL DE SERVIÇO Nº 1234 - Prestador: ... - Valor: R$ 1.500,00 - ISS retido...",
    )

    texto_extraido = ""
    if uploaded_file is not None:
        try:
            import pypdf
            reader = pypdf.PdfReader(uploaded_file)
            texto_extraido = "\n".join(page.extract_text() or "" for page in reader.pages)
            st.success(f"Texto extraído do PDF ({len(texto_extraido)} caracteres)")
            with st.expander("Ver texto extraído"):
                st.text(texto_extraido[:3000])
        except Exception as e:
            st.error(f"Não consegui extrair texto deste PDF: {e}")

    texto_final = texto_extraido if texto_extraido else texto_colado

    processar = st.button(
        "🚀 Processar com os Agentes", type="primary", use_container_width=True,
        disabled=not anthropic_key_ok,
    )

    if processar:
        if not texto_final.strip():
            st.error("Envie um PDF ou cole o texto do documento primeiro.")
        else:
            status_box = st.status("Iniciando agentes...", expanded=True)

            def atualizar_status(msg):
                status_box.write(msg)

            try:
                resultado = processar_documento(
                    api_key=st.secrets["ANTHROPIC_API_KEY"],
                    texto_documento=texto_final,
                    cliente=cliente_nome or "Cliente não identificado",
                    progresso_callback=atualizar_status,
                )
                status_box.update(label="Processamento concluído", state="complete")
                st.session_state["ultimo_resultado_agentes"] = resultado
                st.session_state["ultimo_texto"] = texto_final
            except Exception as e:
                status_box.update(label="Falhou", state="error")
                st.error(f"Erro ao processar com os agentes: {e}")

    if "ultimo_resultado_agentes" in st.session_state:
        r = st.session_state["ultimo_resultado_agentes"]
        st.divider()
        st.subheader("2. Resultado dos Agentes")

        c1, c2, c3 = st.columns(3)
        c1.metric("Setores acionados", ", ".join(r.get("setores_acionados", [])) or "Nenhum")
        c2.metric("Confiança geral", r.get("confianca_geral", "—"))
        c3.metric("Prioridade de revisão", r.get("prioridade_revisao", "—"))

        if r.get("conflitos_detectados"):
            st.error("⚠️ Conflitos detectados entre setores:")
            for conflito in r["conflitos_detectados"]:
                st.write(f"- {conflito}")

        st.write(f"**Justificativa:** {r.get('justificativa_resumida') or r.get('justificativa_roteamento', '')}")

        resultado_por_setor = r.get("resultado_consolidado", {})
        for setor, dados in resultado_por_setor.items():
            with st.expander(f"📋 {setor}", expanded=True):
                st.json(dados)

        st.divider()
        if st.button("📤 Enviar para conferência humana", type="primary", use_container_width=True):
            if supabase_ok:
                try:
                    supabase.table("documentos").insert({
                        "cliente_nome": r.get("cliente"),
                        "texto_original": st.session_state.get("ultimo_texto", "")[:5000],
                        "setores_acionados": r.get("setores_acionados", []),
                        "resultado_consolidado": json.dumps(r.get("resultado_consolidado", {}), ensure_ascii=False),
                        "conflitos_detectados": json.dumps(r.get("conflitos_detectados", []), ensure_ascii=False),
                        "confianca_geral": r.get("confianca_geral"),
                        "prioridade_revisao": r.get("prioridade_revisao"),
                        "justificativa_resumida": r.get("justificativa_resumida") or r.get("justificativa_roteamento", ""),
                        "status": "pendente",
                        "criado_em": datetime.utcnow().isoformat(),
                    }).execute()
                    st.success("Enviado para a fila de conferência!")
                    del st.session_state["ultimo_resultado_agentes"]
                except Exception as e:
                    st.error(f"Erro ao salvar no Supabase: {e}")
            else:
                st.error("Supabase não conectado — configure os secrets.")

# =========================================================
# TAB 2: FILA DE APROVAÇÃO HUMANA
# =========================================================
with tab2:
    st.subheader("Documentos aguardando aprovação do contador")
    if not supabase_ok:
        st.info("Conecte o Supabase para ver a fila real.")
    else:
        try:
            pendentes = supabase.table("documentos").select("*").eq("status", "pendente").order("criado_em", desc=True).execute()
            docs = pendentes.data
        except Exception as e:
            st.error(f"Erro ao buscar documentos: {e}")
            docs = []

        if not docs:
            st.info("Nenhum documento pendente. Processe um documento na aba anterior.")

        for doc in docs:
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 2, 1])
                with c1:
                    st.write(f"**Cliente:** {doc.get('cliente_nome')}")
                    setores = doc.get("setores_acionados") or []
                    st.write(f"**Setores:** {', '.join(setores) if setores else '—'}")
                    st.write(f"**Prioridade:** {doc.get('prioridade_revisao', '—')}")
                with c2:
                    st.write(f"**Confiança geral:** {doc.get('confianca_geral', '—')}")
                    st.write(f"**Justificativa:** {doc.get('justificativa_resumida', '—')}")
                    try:
                        conflitos = json.loads(doc.get("conflitos_detectados") or "[]")
                    except (json.JSONDecodeError, TypeError):
                        conflitos = []
                    if conflitos:
                        st.error(f"⚠️ {len(conflitos)} conflito(s) detectado(s)")
                with c3:
                    if st.button("✅ Aprovar", key=f"apr_{doc['id']}", use_container_width=True):
                        supabase.table("documentos").update({"status": "aprovado"}).eq("id", doc["id"]).execute()
                        st.rerun()
                    if st.button("❌ Rejeitar", key=f"rej_{doc['id']}", use_container_width=True):
                        supabase.table("documentos").update({"status": "rejeitado"}).eq("id", doc["id"]).execute()
                        st.rerun()

                try:
                    resultado_setores = json.loads(doc.get("resultado_consolidado") or "{}")
                except (json.JSONDecodeError, TypeError):
                    resultado_setores = {}
                if resultado_setores:
                    with st.expander("Ver detalhamento por setor"):
                        for setor, dados in resultado_setores.items():
                            st.write(f"**{setor}**")
                            st.json(dados)

    st.divider()
    st.caption("Todo lançamento passa por aprovação humana antes de virar contabilização final.")

# =========================================================
# TAB 3: CONTABILIDADE (a partir dos documentos aprovados)
# =========================================================
with tab3:
    st.subheader("Lançamentos contábeis a partir dos documentos aprovados")

    if not supabase_ok:
        st.info("Conecte o Supabase para gerar o balancete.")
    else:
        try:
            aprovados = supabase.table("documentos").select("*").eq("status", "aprovado").execute()
            docs_aprovados = aprovados.data
        except Exception as e:
            st.error(f"Erro ao buscar documentos aprovados: {e}")
            docs_aprovados = []

        linhas_balancete = []
        for doc in docs_aprovados:
            try:
                resultado_setores = json.loads(doc.get("resultado_consolidado") or "{}")
            except (json.JSONDecodeError, TypeError):
                resultado_setores = {}
            contabil = resultado_setores.get("Contabil")
            if contabil and not contabil.get("erro"):
                linhas_balancete.append({
                    "cliente": doc.get("cliente_nome"),
                    "conta_debito": contabil.get("conta_debito"),
                    "conta_credito": contabil.get("conta_credito"),
                    "valor": contabil.get("valor", 0) or 0,
                })

        if not linhas_balancete:
            st.info("Nenhum lançamento contábil aprovado ainda (só entram aqui documentos onde o setor Contábil foi acionado e aprovado).")
        else:
            contas = {}
            for l in linhas_balancete:
                d, c, v = l["conta_debito"], l["conta_credito"], l["valor"]
                contas.setdefault(d, {"conta": d, "debito": 0.0, "credito": 0.0})
                contas.setdefault(c, {"conta": c, "debito": 0.0, "credito": 0.0})
                contas[d]["debito"] += v
                contas[c]["credito"] += v

            balancete = []
            for conta, valores in contas.items():
                balancete.append({
                    "conta": conta,
                    "debito": round(valores["debito"], 2),
                    "credito": round(valores["credito"], 2),
                    "saldo": round(valores["debito"] - valores["credito"], 2),
                })

            st.markdown("### 📋 Balancete de Verificação")
            st.dataframe(balancete, use_container_width=True, hide_index=True)

            total_debito = sum(l["debito"] for l in balancete)
            total_credito = sum(l["credito"] for l in balancete)
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Débitos", f"R$ {total_debito:,.2f}")
            c2.metric("Total Créditos", f"R$ {total_credito:,.2f}")
            c3.metric("Diferença", f"R$ {total_debito - total_credito:,.2f}")

            st.markdown("### 📖 Lançamentos individuais")
            st.dataframe(linhas_balancete, use_container_width=True, hide_index=True)
