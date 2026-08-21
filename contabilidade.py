from fpdf import FPDF

# 1. Conciliação de extrato bancário
def conciliar_extrato(extrato, lancamentos):
    """Compara extrato bancário com lançamentos internos."""
    conciliados = []
    pendentes = []
    for mov in extrato:
        match = next(
            (l for l in lancamentos if l["valor"] == mov["valor"] and l["data"] == mov["data"]),
            None
        )
        if match:
            conciliados.append({"extrato": mov, "lancamento": match})
        else:
            pendentes.append(mov)
    return conciliados, pendentes


# 2. Gerar lançamento contábil (partida dobrada)
def gerar_lancamento(valor, historico, conta_debito, conta_credito, data):
    return {
        "data": data,
        "historico": historico,
        "valor": valor,
        "debito": conta_debito,
        "credito": conta_credito,
    }


# 3. Calcular balancete (saldo por conta)
def calcular_balancete(lancamentos):
    contas = {}
    for lanc in lancamentos:
        deb = lanc["debito"]
        cred = lanc["credito"]
        valor = lanc["valor"]

        contas.setdefault(deb, {"nome": deb, "debito": 0, "credito": 0})
        contas.setdefault(cred, {"nome": cred, "debito": 0, "credito": 0})

        contas[deb]["debito"] += valor
        contas[cred]["credito"] += valor

    balancete = []
    for conta in contas.values():
        conta["saldo"] = conta["debito"] - conta["credito"]
        balancete.append(conta)

    return balancete


# 4. Exportar PDF do balancete
def gerar_pdf_balancete(balancete, caminho="balancete.pdf"):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, "Balancete de Verificacao", ln=True, align="C")
    pdf.ln(5)

    for conta in balancete:
        linha = f"{conta['nome']} | Debito: {conta['debito']:.2f} | Credito: {conta['credito']:.2f} | Saldo: {conta['saldo']:.2f}"
        pdf.cell(0, 10, linha, ln=True)

    pdf.output(caminho)
    return caminho
