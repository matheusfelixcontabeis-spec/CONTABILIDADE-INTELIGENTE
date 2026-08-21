import streamlit as st
from datetime import datetime
import csv
import io
import re

from supabase import create_client

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
except Exception as e:
    supabase_ok = False
    supabase_error = str(e)

# =========================================================
# MÓDULO: CLASSIFICADOR DE DOCUMENTOS (IA)
# =========================================================
def classify_document(texto: str, groq_api_key: str = None) -> dict:
    """
    Classifica um documento contábil (nota fiscal, boleto, extrato, etc.)
    Usa a API da Groq se a chave estiver disponível; senão, usa regras simples (fallback).
    """
    texto_lower = texto.lower()

    # Tenta usar IA via Groq, se a chave existir
    if groq_api_key:
        try:
            from groq import Groq
            client = Groq(api_key=groq_api_key)

            prompt = f"""Você é um assistente contábil. Analise o documento abaixo e responda em formato JSON com as chaves:
tipo_documento, classificacao_fiscal, confianca (Alta/Média/Baixa), lancamento_sugerido.

Documento:
{texto[:3000]}

Responda APENAS o JSON, sem explicações."""

            resposta = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            conteudo = resposta.choices[0].message.content

            import json
            match = re.search(r"\{.*\}", conteudo, re.DOTALL)
            if match:
                dados = json.loads(match.group())
                dados["fonte"] = "IA (Groq/Llama 3.3)"
                return dados
        except Exception as e:
            st.warning(f"Falha ao usar IA ({e}). Usando classificação por regras.")

    # -------- Fallback: classificação simples por palavras-chave --------
    if "nota fiscal" in texto_lower or "nfe" in texto_lower or "nfs-e" in texto_lower:
        tipo = "Nota Fiscal"
        classificacao = "Receita de Serviço" if "serviço" in texto_lower else "Receita de Venda"
        lancamento = "Débito: Clientes a Receber / Crédito: Receita de Vendas ou Serviços"
    elif "boleto" in texto_lower or "fatura" in texto_lower:
        tipo = "Boleto/Fatura"
        classificacao = "Despesa Operacional"
        lancamento = "Débito: Despesas Operacionais / Crédito: Fornecedores a Pagar"
    elif "extrato" in texto_lower or "saldo" in texto_lower:
        tipo = "Extrato Bancário"
        classificacao = "Movimentação Financeira"
        lancamento = "Conforme lançamentos detalhados do extrato"
    else:
        tipo = "Documento não identificado"
        classificacao = "Revisão manual necessária"
        lancamento = "A definir pelo contador"

    valor_match = re.search(r"r\$\s*([\d.,]+)", texto_lower)
    valor_texto = f" (valor identificado: R$ {valor_match.group(1)})" if valor_match else ""

    return {
        "tipo_documento": tipo,
        "classificacao_fiscal": classificacao,
        "confianca": "Média" if valor_match else "Baixa",
        "lancamento_sugerido": lancamento + valor_texto,
        "fonte": "Regras (fallback, sem IA configurada)",
    }


# =========================================================
# MÓDULO: CONTABILIDADE (lançamentos, conciliação, balancete)
# =========================================================
def gerar_lancamento(valor, historico, conta_debito, conta_credito, data):
    return {
        "data": data,
        "historico": historico,
        "conta_debito": conta_debito,
        "conta_credito": conta_credito,
        "valor": float(valor) if valor else 0.0,
    }


def conciliar_extrato(extrato: list, lancamentos: list):
    """
    Compara movimentos do extrato bancário com os lançamentos contábeis.
    Considera 'conciliado' quando existe um lançamento com o mesmo valor (tolerância de centavos).
    """
    conciliados = []
    pendentes = []

    valores_lancamentos = [l["valor"] for l in lancamentos]

    for mov in extrato:
        valor_mov = mov["valor"]
        encontrado = any(abs(valor_mov - v) < 0.01 for v in valores_lancamentos)
        if encontrado:
            conciliados.append(mov)
        else:
            pendentes.append(mov)

    return conciliados, pendentes


def calcular_balancete(lancamentos: list):
    """
    Agrupa os lançamentos por conta, somando débitos e créditos.
    """
    contas = {}

    for l in lancamentos:
        debito = l["conta_debito"]
        credito = l["conta_credito"]
        valor = l["valor"]

        if debito not in contas:
            contas[debito] = {"conta": debito, "debito": 0.0, "credito": 0.0}
        if credito not in contas:
            contas[credito] = {"conta": credito, "debito": 0.0, "credito": 0.0}

        contas[debito]["debito"] += valor
        contas[credito]["credito"] += valor

    balancete = []
    for conta, valores in contas.items():
        saldo = valores["debito"] - valores["credito"]
        balancete.append({
            "conta": conta,
            "debito": round(valores["debito"], 2),
            "credito": round(valores["credito"], 2),
            "saldo": round(saldo, 2),
        })

    return balancete


def gerar_pdf_balancete(balancete: list, caminho: str = "/tmp/balancete.pdf"):
    """
    Gera um PDF simples do balancete usando fpdf2.
    """
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Balancete de Verificação", ln=True, align="C")
    pdf.ln(5)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(80, 8, "Conta", border=1)
    pdf.cell(35, 8, "Débito (R$)", border=1, align="R")
    pdf.cell(35, 8, "Crédito (R$)", border=1, align="R")
    pdf.cell(35, 8, "Saldo (R$)", border=1, align="R")
    pdf.ln()

    pdf.set_font("Helvetica", "", 10)
    total_debito = 0
    total_credito = 0
    for linha in balancete:
        pdf.cell(80, 8, str(linha["conta"]), border=1)
        pdf.cell(35, 8, f"{linha['debito']:.2f}", border=1, align="R")
        pdf.cell(35, 8, f"{linha['credito']:.2f}", border=1, align="R")
        pdf.cell(35, 8, f"{linha['saldo']:.2f}", border=1, align="R")
        pdf.ln()
        total_debito += linha["debito"]
        total_credito += linha["credito"]

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(80, 8, "TOTAL", border=1)
    pdf.cell(35, 8, f"{total_debito:.2f}", border=1, align="R")
    pdf.cell(35, 8, f"{total_credito:.2f}", border=1, align="R")
    pdf.cell(35, 8, f"{(total_debito - total_credito):.2f}", border=1, align="R")

    pdf.output(caminho)
    return caminho


# =========================================================
# CABEÇALHO DO APP
# =========================================================
st.title("📊 Contadoros AI")
st.caption("Triagem inteligente de documentos contábeis, com aprovação humana obrigatória")

if not supabase_ok:
    st.warning(
        "Supabase não conectado ainda (configure SUPABASE_URL e SUPABASE_KEY em Settings → Secrets). "
        "O app funciona em modo demo mesmo assim."
    )

tab1, tab2, tab3 = st.tabs(["📥 Novo Documento", "✅ Fila de Conferência", "📑 Contabilidade"])

# =========================================================
# TAB 1: UPLOAD / CLASSIFICAÇÃO
# =========================================================
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
                st.error(f"Não consegui extrair texto deste PDF: {e}")

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
                        st.success("Enviado para fila de conferência!")
                    except Exception as e:
                        st.error(f"Erro ao salvar: {e}")
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
            st.info("Nenhum documento pendente. Classifique na aba anterior.")

        for doc in docs:
            with st.container():
                c1, c2, c3 = st.columns([2, 2, 1])
                with c1:
                    st.write(f"**Cliente:** {doc['cliente_nome']}")
                    st.write(f"**Tipo:** {doc['tipo_documento']}")
                with c2:
                    st.write(f"**Classificação:** {doc['classificacao_fiscal']}")
                    st.write(f"**Lançamento:** {doc['lancamento_sugerido']}")
                with c3:
                    if st.button("✅ Aprovar", key=f"apr_{doc['id']}"):
                        supabase.table("documentos").update({"status": "aprovado"}).eq("id", doc["id"]).execute()
                        st.rerun()
                    if st.button("❌ Rejeitar", key=f"rej_{doc['id']}"):
                        supabase.table("documentos").update({"status": "rejeitado"}).eq("id", doc["id"]).execute()
                        st.rerun()

        st.divider()
        st.caption("Todo lançamento passa por aprovação antes de ser contabilizado.")

# =========================================================
# TAB 3: CONTABILIDADE (LANÇAMENTOS, BALANCETE E PDF)
# =========================================================
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

        st.subheader("Conciliação de extrato bancário")
        st.caption("Envie um CSV com colunas: data,valor (ex: 2025-01-10,1500.00)")
        extrato_file = st.file_uploader("Extrato bancário (CSV)", type=["csv"], key="extrato")

        extrato = []
        if extrato_file is not None:
            content = extrato_file.read().decode("utf-8")
            reader = csv.DictReader(io.StringIO(content))
            for row in reader:
                extrato.append({"data": row["data"], "valor": float(row["valor"])})

            conciliados, pendentes_extrato = conciliar_extrato(extrato, lancamentos)
            st.success(f"{len(conciliados)} movimento(s) conciliado(s)")
            if pendentes_extrato:
                st.warning(f"{len(pendentes_extrato)} movimento(s) do extrato sem lançamento correspondente")
                st.dataframe(pendentes_extrato, use_container_width=True)

        st.divider()

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
