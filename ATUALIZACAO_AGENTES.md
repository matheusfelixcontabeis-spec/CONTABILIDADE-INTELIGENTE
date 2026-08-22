# Contadoros AI — Atualização: Agentes integrados ao Streamlit

Esta versão troca a classificação simples pelo orquestrador completo: Agente
Sênior roteia automaticamente, os sub-agentes de setor rodam em paralelo, e
você só aprova o resultado final — tudo pelo navegador, sem terminal.

## 1. Suba TODOS estes arquivos para o GitHub

- `app.py` (substitui o antigo)
- `orquestrador.py` (novo)
- `requirements.txt` (substitui o antigo)
- A pasta `prompts/` inteira, com os 7 arquivos dentro dela:
  - `senior_roteamento.txt`
  - `senior_consolidacao.txt`
  - `sub_contabil.txt`
  - `sub_fiscal.txt`
  - `sub_departamento_pessoal.txt`
  - `sub_tributario.txt`
  - `sub_legalizacao.txt`

No GitHub, pra criar a pasta `prompts/` você pode arrastar os 7 arquivos
juntos na tela de upload — ele cria a pasta sozinho se você digitar
`prompts/nome_do_arquivo.txt` no campo de nome antes de cada upload, ou
simplesmente arraste todos de uma vez que o GitHub identifica pela estrutura
se você tiver mantido a pasta ao arrastar do Explorer/Finder.

## 2. Adicione sua chave da Anthropic nos Secrets do Streamlit

Manage app → Settings → Secrets → adicione (mantendo o que já existe):

```toml
SUPABASE_URL = "https://SEU-PROJETO.supabase.co"
SUPABASE_KEY = "sua-anon-key-aqui"
ANTHROPIC_API_KEY = "sua-chave-anthropic-aqui"
```

Pegue a chave em https://console.anthropic.com/settings/keys (tem crédito
gratuito pra testar).

## 3. Atualize a tabela no Supabase

Rode este SQL (só adiciona colunas novas, não apaga nada):

```sql
alter table documentos
  add column if not exists setores_acionados jsonb,
  add column if not exists resultado_consolidado text,
  add column if not exists conflitos_detectados text,
  add column if not exists confianca_geral text,
  add column if not exists prioridade_revisao text,
  add column if not exists justificativa_resumida text;
```

## 4. Teste

1. Aba "Processar Documento" → cole o texto de uma nota fiscal com valor
2. Clique "🚀 Processar com os Agentes" — vai aparecer o status ao vivo
   (Agente Sênior roteando → sub-agentes rodando → consolidando)
3. Confira o resultado por setor (cada um em um card expansível)
4. "Enviar para conferência humana"
5. Aba "Fila de Conferência" → aprovar
6. Aba "Contabilidade" → o lançamento (se o setor Contábil foi acionado)
   aparece no balancete

## Nota sobre custo e tempo de resposta

Cada documento processado faz de 3 a 6 chamadas de API (1 roteamento + 1 a 5
sub-agentes em paralelo + 1 consolidação). Com a Claude Sonnet, isso custa
frações de centavo por documento — mas para uma demo ao vivo, cada
processamento leva de alguns segundos a ~20-30 segundos, dependendo de
quantos setores forem acionados. Vale rodar um teste ANTES da reunião com o
investidor pra já saber o tempo de resposta na prática e não ser pego de
surpresa.
