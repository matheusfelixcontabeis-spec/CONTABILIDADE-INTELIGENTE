"""
Classificador de documentos: tenta LLM (Groq, gratuito) e sempre tem
um fallback por regras de palavra-chave, para a demo nunca quebrar
mesmo se a API falhar ou a chave não estiver configurada.
"""

import json
import re

KEYWORDS = {
    "Nota Fiscal de Serviço": ["nota fiscal de serviço", "nfs-e", "nfse", "prestador de serviço", "iss retido"],
    "Nota Fiscal de Produto": ["nf-e", "nfe", "danfe", "icms", "produto"],
    "Boleto": ["boleto", "código de barras", "vencimento", "linha digitável"],
    "Extrato Bancário": ["extrato", "saldo anterior", "saldo atual", "lançamentos do período"],
    "Guia de Imposto (DAS/GPS)": ["das", "simples nacional", "gps", "guia da previdência"],
    "Folha de Pagamento": ["holerite", "folha de pagamento", "salário líquido", "fgts", "inss"],
}

FISCAL_MAP = {
    "Nota Fiscal de Serviço": "Prestação de serviços — apuração de ISS / retenções",
    "Nota Fiscal de Produto": "Circulação de mercadoria — apuração de ICMS",
    "Boleto": "Contas a pagar/receber — sem apuração fiscal direta",
    "Extrato Bancário": "Conciliação bancária",
    "Guia de Imposto (DAS/GPS)": "Tributo já apurado — lançar como obrigação a pagar/paga",
    "Folha de Pagamento": "Departamento Pessoal — encargos trabalhistas e previdenciários",
}

LANCAMENTO_MAP = {
    "Nota Fiscal de Serviço": "D: Contas a Receber / C: Receita de Serviços (líquido de ISS retido, se houver)",
    "Nota Fiscal de Produto": "D: Estoque ou CMV / C: Fornecedores, com destaque de ICMS",
    "Boleto": "D: Fornecedores a Pagar / C: Caixa/Banco (na liquidação)",
    "Extrato Bancário": "Conciliar linha a linha com o razão contábil",
    "Guia de Imposto (DAS/GPS)": "D: Impostos a Recolher / C: Caixa/Banco",
    "Folha de Pagamento": "D: Despesa com Pessoal / C: Salários a Pagar, INSS a Recolher, FGTS a Recolher",
}


def _classify_by_keywords(texto: str):
    texto_lower = texto.lower()
    for tipo, palavras in KEYWORDS.items():
        for palavra in palavras:
            if palavra in texto_lower:
                return tipo
    return "Documento não identificado"


def _classify_with_groq(texto: str, api_key: str):
    import requests

    prompt = f"""Você é um classificador de documentos contábeis brasileiros.
Analise o texto abaixo e responda APENAS com um JSON no formato:
{{"tipo_documento": "...", "confianca": "alta/média/baixa"}}

O tipo_documento deve ser um destes: {list(KEYWORDS.keys())} ou "Documento não identificado".

Texto do documento:
{texto[:2000]}
"""
    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": "llama-3.1-8b-instant",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
        },
        timeout=15,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    match = re.search(r"\{.*\}", content, re.DOTALL)
    data = json.loads(match.group(0))
    return data["tipo_documento"], data.get("confianca", "média")


def classify_document(texto: str, groq_api_key: str = None):
    tipo = None
    confianca = "média (regras)"
    fonte = "Motor de regras (palavras-chave)"

    if groq_api_key:
        try:
            tipo, conf_llm = _classify_with_groq(texto, groq_api_key)
            confianca = f"{conf_llm} (IA - Groq/Llama)"
            fonte = "LLM (Groq, Llama 3.1)"
        except Exception:
            tipo = None  # cai no fallback

    if not tipo or tipo not in FISCAL_MAP:
        tipo = _classify_by_keywords(texto)
        if fonte.startswith("LLM"):
            fonte = "LLM falhou — fallback por regras"
            confianca = "média (regras, fallback)"

    classificacao_fiscal = FISCAL_MAP.get(tipo, "Requer análise manual do contador")
    lancamento = LANCAMENTO_MAP.get(tipo, "Requer análise manual do contador")

    return {
        "tipo_documento": tipo,
        "classificacao_fiscal": classificacao_fiscal,
        "lancamento_sugerido": lancamento,
        "confianca": confianca,
        "fonte": fonte,
    }
