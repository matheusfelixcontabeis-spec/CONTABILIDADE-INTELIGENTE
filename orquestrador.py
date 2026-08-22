"""
Orquestrador Contadoros AI — versão módulo (usada pelo app.py Streamlit).

Recebe o texto de um documento e executa o fluxo completo:
  1. Agente Sênior decide quais setores acionar.
  2. Sub-agentes dos setores acionados rodam em paralelo.
  3. Agente Sênior consolida as respostas e aponta conflitos.

Nada é finalizado automaticamente — o resultado sempre volta marcado como
pendente de aprovação humana.
"""

import json
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import anthropic

MODELO = "claude-sonnet-4-5"
PASTA_PROMPTS = Path(__file__).parent / "prompts"

SETORES_DISPONIVEIS = {
    "Contabil": "sub_contabil.txt",
    "Fiscal": "sub_fiscal.txt",
    "DepartamentoPessoal": "sub_departamento_pessoal.txt",
    "Tributario": "sub_tributario.txt",
    "Legalizacao": "sub_legalizacao.txt",
}


def _carregar_prompt(nome_arquivo: str) -> str:
    return (PASTA_PROMPTS / nome_arquivo).read_text(encoding="utf-8")


def _chamar_claude(client: "anthropic.Anthropic", system_prompt: str, mensagem_usuario: str, tentativas: int = 3) -> dict:
    """Chama a API do Claude e faz parse do JSON de resposta, com retry simples."""
    ultimo_erro = None
    for tentativa in range(1, tentativas + 1):
        try:
            resposta = client.messages.create(
                model=MODELO,
                max_tokens=2000,
                system=system_prompt,
                messages=[{"role": "user", "content": mensagem_usuario}],
            )
            texto = resposta.content[0].text.strip()
            texto = texto.replace("```json", "").replace("```", "").strip()
            return json.loads(texto)
        except (json.JSONDecodeError, IndexError) as e:
            ultimo_erro = e
            time.sleep(1.5 * tentativa)
        except anthropic.APIError as e:
            ultimo_erro = e
            time.sleep(2 * tentativa)
    raise RuntimeError(f"Falha ao chamar o agente após {tentativas} tentativas: {ultimo_erro}")


def rotear(client, texto_documento: str) -> dict:
    system_prompt = _carregar_prompt("senior_roteamento.txt")
    return _chamar_claude(client, system_prompt, texto_documento)


def _executar_sub_agente(client, setor: str, texto_documento: str) -> tuple[str, dict]:
    arquivo_prompt = SETORES_DISPONIVEIS[setor]
    system_prompt = _carregar_prompt(arquivo_prompt)
    resultado = _chamar_claude(client, system_prompt, texto_documento)
    return setor, resultado


def executar_setores_em_paralelo(client, setores: list[str], texto_documento: str) -> dict:
    resultados = {}
    erros = {}
    with ThreadPoolExecutor(max_workers=len(setores) or 1) as executor:
        futuros = {
            executor.submit(_executar_sub_agente, client, setor, texto_documento): setor
            for setor in setores
        }
        for futuro in as_completed(futuros):
            setor = futuros[futuro]
            try:
                _, resultado = futuro.result()
                resultados[setor] = resultado
            except Exception as e:
                erros[setor] = str(e)
    if erros:
        for setor, erro in erros.items():
            resultados[setor] = {
                "erro": True,
                "mensagem": f"Sub-agente {setor} falhou: {erro}",
                "score_confianca": 0,
            }
    return resultados


def consolidar(client, resultados_setores: dict) -> dict:
    system_prompt = _carregar_prompt("senior_consolidacao.txt")
    mensagem = json.dumps(resultados_setores, ensure_ascii=False, indent=2)
    return _chamar_claude(client, system_prompt, mensagem)


def processar_documento(api_key: str, texto_documento: str, cliente: str = "Cliente não identificado", progresso_callback=None) -> dict:
    """
    Executa o fluxo completo, do documento bruto até o pacote pronto para a
    fila de conferência humana.

    progresso_callback (opcional): função chamada com uma string de status a
    cada etapa, para atualizar a interface (ex: st.status).
    """
    client = anthropic.Anthropic(api_key=api_key)

    def avisar(msg):
        if progresso_callback:
            progresso_callback(msg)

    avisar("Agente Sênior decidindo roteamento...")
    roteamento = rotear(client, texto_documento)
    setores = [s for s in roteamento.get("setores_acionar", []) if s in SETORES_DISPONIVEIS]

    if not setores:
        return {
            "cliente": cliente,
            "status": "sem_setor_identificado",
            "justificativa_roteamento": roteamento.get("justificativa", ""),
            "setores_acionados": [],
            "resultado_consolidado": {},
            "conflitos_detectados": [],
            "confianca_geral": "Baixa",
            "prioridade_revisao": "Prioritaria",
            "justificativa_resumida": "Nenhum setor identificado automaticamente — revisão manual necessária.",
        }

    avisar(f"Setores acionados: {', '.join(setores)}. Executando em paralelo...")
    resultados_setores = executar_setores_em_paralelo(client, setores, texto_documento)

    avisar("Agente Sênior consolidando o resultado...")
    consolidado = consolidar(client, resultados_setores)

    pacote_final = {
        "cliente": cliente,
        "setores_acionados": setores,
        "justificativa_roteamento": roteamento.get("justificativa", ""),
        **consolidado,
        "status": "pendente_aprovacao_humana",
    }
    avisar("Concluído.")
    return pacote_final
