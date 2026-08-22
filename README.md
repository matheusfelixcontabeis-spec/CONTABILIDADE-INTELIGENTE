# Orquestrador Contadoros AI

Executa o fluxo completo automaticamente: você envia o texto de um documento,
o sistema decide sozinho quais setores acionar, roda os sub-agentes em
paralelo, consolida o resultado — e para em um único ponto: a aprovação
humana antes de qualquer coisa virar contabilização final.

## O que É automático
- Roteamento (Agente Sênior decide os setores, sem você escolher).
- Execução de todos os sub-agentes acionados, em paralelo.
- Consolidação e detecção de conflitos entre setores.
- Priorização automática (score baixo ou conflito → "Prioritaria").

## O único ponto manual (por design)
O resultado final sai com `"status": "pendente_aprovacao_humana"`. Nada é
lançado, contabilizado ou enviado a um órgão sozinho. Isso é proposital: em
fiscal, tributário e DP um erro sem revisão vira multa ou pagamento errado
pro cliente. Se você quiser remover esse freio mais adiante, é uma linha de
código pra tirar (`status` no fim de `processar_documento`) — mas eu
recomendo manter pelo menos até o produto ter mais tração validada.

## Como rodar

1. Instale a dependência (é só uma):
   ```
   pip install -r requirements.txt --break-system-packages
   ```
   (Sem o `--break-system-packages` se você estiver usando um virtualenv.)

2. Configure sua chave da API da Anthropic como variável de ambiente:
   ```
   export ANTHROPIC_API_KEY="sua-chave-aqui"
   ```
   (No Windows/PowerShell: `$env:ANTHROPIC_API_KEY="sua-chave-aqui"`)

   Pegue a chave em https://console.anthropic.com/settings/keys — tem um
   nível gratuito de créditos pra teste, depois é pré-pago por uso (bem
   barato para volume de MVP: um documento típico custa frações de centavo).

3. Rode com um documento de teste:
   ```
   python orquestrador.py exemplo_nota_fiscal.txt "Padaria Bela Vista MEI"
   ```

4. O resultado sai no terminal em JSON, pronto pra você (ou o próximo passo
   de integração) jogar numa fila/banco de dados.

## Estrutura de pastas
```
orquestrador/
  orquestrador.py          <- o motor: roteia, executa, consolida
  requirements.txt
  prompts/
    senior_roteamento.txt      <- decide quais setores acionar
    senior_consolidacao.txt    <- junta as respostas, aponta conflitos
    sub_contabil.txt
    sub_fiscal.txt
    sub_departamento_pessoal.txt
    sub_tributario.txt
    sub_legalizacao.txt
```

## Próximo passo natural
Hoje você roda `python orquestrador.py arquivo.txt` na mão. Pra virar
"documento entra, roda sozinho, sem terminal", falta só uma camada de
entrada (ex: o mesmo Streamlit que já temos, ou uma pasta monitorada, ou um
endpoint de e-mail) chamando a função `processar_documento()` — o motor em
si já está pronto pra isso, não precisa ser reescrito.
