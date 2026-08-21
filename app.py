"""
Contadoros AI - MVP de Triagem de Documentos com Aprovação Humana
Rodando 100% na nuvem (Streamlit Community Cloud) - zero instalação local.
"""

import streamlit as st
from datetime import datetime
import json

from supabase import create_client
from classifier import classify_document

st.set_page_config(page_title="Contadoros AI", page_icon="📊", layout="wide")

# ---------- Conexão com Supabase ----------
@st.cache_resource
def get_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase = get_supabase()
    supabase_ok = True
except Exception as e:
    supabase_ok = False
    supabase_error = str(e)

# ---------- Header ----------
st.title("📊 Contadoros AI")
st.caption("Triagem inteligente de documentos contábeis, com aprovação humana obrigatória")

if not supabase_ok:
    st.warning(
        "Supabase não conectado ainda (configure SUPABASE_URL e SUPABASE_KEY em Settings → Secrets). "
        "O app funciona em modo demo local mesmo assim."
    )

tab1, tab2 = st.tabs(["📥 Novo Documento", "✅ Fila de Conferência"])

# ---------- TAB 1: Upload / Classificação ----------
with tab1:
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("1. Envie o documento")
        cliente_nome = st.text_input("Cliente", placeholder="Ex: Padaria Bela Vista MEI")
        uploaded_file = st.file_uploader("PDF com texto (nota fiscal, boleto, extrato...)", type=["pdf"])
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
                st.error(f"Não consegui extrair texto deste PDF (pode ser um PDF escaneado/imagem): {e}")

        texto_final = texto_extraido if texto_extraido else texto_colado

        classificar = st.button("🤖 Classificar com IA", type="primary", use_container_width=True)

    with col2:
        st.subheader("2. Resultado da IA")
        if classificar:
            if not texto_final.strip():
                st.error("Envie um PDF ou cole o texto do documento primeiro.")
            else:
                with st.spinner("Analisando documento..."):
                    resultado = classify_document(texto_final, groq_api_key=st.secrets.get("GROQ_API_KEY"))

                st.session_state["ultimo_resultado"] = resultado
                st.session_state["ultimo_texto"] = texto_final
                st.session_state["ultimo_cliente"] = cliente_nome or "Cliente não identificado"

        if "ultimo_resultado" in st.session_state:
            r = st.session_state["ultimo_resultado"]
            st.metric("Tipo de documento", r["tipo_documento"])
            st.metric("Classificação fiscal sugerida", r["classificacao_fiscal"])
            st.write(f"**Confiança:** {r['confianca']}")
            st.write(f"**Lançamento contábil sugerido:** {r['lancamento_sugerido']}")
            st.write(f"**Fonte da análise:** {r['fonte']}")

            if st.button("📤 Enviar para conferência humana", use_container_width=True):
                if supabase_ok:
                    try:
                        supabase.table("documentos").insert({
                            "cliente_nome": st.session_state["ultimo_cliente"],
                            "texto_original": st.session_state["ultimo_texto"][:5000],
                            "tipo_documento": r["tipo_documento"],
                            "classificacao_fiscal": r["classificacao_fiscal"],
                            "lancamento_sugerido": r["lancamento_sugerido"],
                            "confianca": r["confianca"],
                            "status": "pendente",
                            "criado_em": datetime.utcnow().isoformat(),
                        }).execute()
                        st.success("Enviado para a fila de conferência! Veja na aba ao lado.")
                    except Exception as e:
                        st.error(f"Erro ao salvar no Supabase: {e}")
                else:
                    st.error("Supabase não conectado — configure os secrets para salvar de verdade.")

# ---------- TAB 2: Fila de aprovação humana ----------
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
            st.info("Nenhum documento pendente. Classifique um documento na aba anterior.")

        for doc in docs:
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 2, 1])
                with c1:
                    st.write(f"**Cliente:** {doc['cliente_nome']}")
                    st.write(f"**Tipo:** {doc['tipo_documento']}")
                with c2:
                    st.write(f"**Classificação fiscal:** {doc['classificacao_fiscal']}")
                    st.write(f"**Lançamento sugerido:** {doc['lancamento_sugerido']}")
                with c3:
                    if st.button("✅ Aprovar", key=f"aprovar_{doc['id']}", use_container_width=True):
                        supabase.table("documentos").update({"status": "aprovado"}).eq("id", doc["id"]).execute()
                        st.rerun()
                    if st.button("❌ Rejeitar", key=f"rejeitar_{doc['id']}", use_container_width=True):
                        supabase.table("documentos").update({"status": "rejeitado"}).eq("id", doc["id"]).execute()
                        st.rerun()

    st.divider()
    st.caption("Todo lançamento passa por aprovação humana antes de virar contabilização final — esse é o modelo de confiança do Contadoros AI.")
