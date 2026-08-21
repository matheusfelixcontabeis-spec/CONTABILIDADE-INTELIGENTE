# Contadoros AI — MVP (deploy 100% pelo navegador, sem instalar nada)

Tempo estimado: 20–30 minutos. Tudo é feito em sites, pelo navegador do seu PC de 4GB.

## 1. Crie uma conta no GitHub (se não tiver) — grátis
https://github.com/signup

## 2. Suba estes arquivos para um repositório novo
- No github.com, clique em "New repository" → nome: `contadoros-ai-mvp` → Create.
- Clique em "uploading an existing file" e arraste os 4 arquivos: `app.py`, `classifier.py`, `requirements.txt`, `README.md`.
- Commit.

## 3. Ajuste a tabela `documentos` no Supabase
Vá no seu projeto Supabase → SQL Editor → cole e rode:

```sql
alter table documentos
  add column if not exists cliente_nome text,
  add column if not exists texto_original text,
  add column if not exists tipo_documento text,
  add column if not exists classificacao_fiscal text,
  add column if not exists lancamento_sugerido text,
  add column if not exists confianca text,
  add column if not exists status text default 'pendente',
  add column if not exists criado_em timestamptz default now();
```

Isso só adiciona colunas que faltarem — não apaga nada que já existe.

Depois, vá em Project Settings → API e copie:
- `Project URL` → isso é o `SUPABASE_URL`
- `anon public key` → isso é o `SUPABASE_KEY`

## 4. Pegue uma chave grátis da Groq (opcional, mas dá o efeito "IA de verdade")
- https://console.groq.com → crie conta grátis (sem cartão) → API Keys → Create Key.
- Sem essa chave o app ainda funciona, só que classifica por regras em vez de LLM — funciona bem pra demo também.

## 5. Deploy no Streamlit Community Cloud — grátis
- https://share.streamlit.io → login com GitHub.
- "New app" → escolha o repositório `contadoros-ai-mvp` → main file: `app.py` → Deploy.
- Antes ou depois do deploy, vá em "Settings" → "Secrets" do app e cole:

```toml
SUPABASE_URL = "https://SEU-PROJETO.supabase.co"
SUPABASE_KEY = "sua-anon-key-aqui"
GROQ_API_KEY = "sua-groq-key-aqui"
```

- Salve. O app reinicia sozinho e já fica no ar, com uma URL pública tipo
  `https://contadoros-ai-mvp.streamlit.app` — essa é a URL que você mostra pro investidor.

## O que mostrar na demo (roteiro sugerido)
1. Aba "Novo Documento": cole o texto de uma nota fiscal de verdade (ou um extrato).
2. Clique "Classificar com IA" → mostra tipo de documento, classificação fiscal e o lançamento contábil sugerido.
3. Clique "Enviar para conferência humana".
4. Vá na aba "Fila de Conferência" → mostre o botão Aprovar → isso é o pitch: **IA acelera, contador sempre valida antes de virar contabilização oficial**. É o seu diferencial de confiança frente a automações "caixa-preta".

## Depois do investidor (não faça isso hoje)
- Trocar upload de texto por OCR de imagem/PDF escaneado (tesseract).
- Multiagentes por setor (Fiscal, DP, Tributário) — já desenhado, é a v2.
- Autenticação multi-cliente (hoje o MVP é single-tenant, propositalmente).
