# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

"""Motor de cálculo de planos de amortização.

Implementa os três modelos descritos na especificação (Constante, Decrescente
e Misto) e a conversão de Prazo (em meses) + Frequência para o número de
prestações e a taxa de juro por período.

Interpretação assumida para o modelo Misto: o desdobramento capital/juros por
prestação segue o mesmo método de saldo decrescente do modelo Decrescente
(CM = Ki/P, JM = SCR × Tj), mas a prestação apresentada ao cliente é
suavizada para um valor fixo (VTP/P), onde VTP é o total que resultaria do
cálculo decrescente ao longo de todo o prazo. Ajustar aqui se a definição
pretendida for outra.

Arredondamento: o plano é calculado já em cêntimos, linha a linha, e não
arredondado no fim. Assim os valores mostrados batem sempre certo entre si:

- juros de cada prestação = saldo de capital anterior (já arredondado) × taxa;
- capital + juros = prestação, em todas as linhas (exceto no Misto, em que a
  prestação é suavizada por definição);
- a soma do capital é exatamente o capital concedido - a última prestação
  amortiza o que falta, e o saldo fecha em 0,00;
- a soma das prestações é exatamente capital + juros.

Isto importa para além da apresentação: a Multa é calculada sobre o capital +
juros de cada prestação, por isso um cêntimo a menos aqui era um cêntimo a
menos de base da Multa.
"""

import frappe
from frappe.utils import add_days, add_months, flt, getdate

PERIOD_DAYS = {
	"Diário": 1,
	"Semanal": 7,
	"Quinzenal": 15,
	"Mensal": 30,
}

MODELOS = ("Francês", "Decrescente", "Misto", "Constante")


def get_period_days(frequencia):
	if frequencia not in PERIOD_DAYS:
		frappe.throw(f"Frequência inválida: {frequencia}")
	return PERIOD_DAYS[frequencia]


def get_num_periodos(prazo_meses, frequencia):
	"""Número de prestações resultante do prazo (meses) convertido para a frequência."""
	period_days = get_period_days(frequencia)
	total_dias = flt(prazo_meses) * 30
	n = round(total_dias / period_days)
	return max(int(n), 1)


def get_taxa_por_periodo(taxa_juros_percent, frequencia):
	"""Taxa de juro (Tj) prorateada para a duração do período face a uma taxa mensal nominal."""
	period_days = get_period_days(frequencia)
	return flt(taxa_juros_percent) / 100 * (period_days / 30)


def usar_vencimento_calendario(frequencia, vencimento_calendario=None):
	"""Decide se as datas limite de pagamento seguem meses de calendário (mesmo
	dia do mês da data de início) em vez de blocos fixos de 30 dias. Só se aplica
	à frequência Mensal; nas restantes o bloco fixo é o comportamento esperado.

	`vencimento_calendario` a None lê o campo `vencimento_no_dia_do_desembolso`
	de MC Settings; passar True/False força o comportamento (usado nos pré-visuais
	e testes)."""
	if frequencia != "Mensal":
		return False
	if vencimento_calendario is None:
		vencimento_calendario = frappe.db.get_single_value(
			"MC Settings", "vencimento_no_dia_do_desembolso"
		)
	return bool(vencimento_calendario)


def build_plano(
	capital,
	taxa_juros_percent,
	prazo_meses,
	frequencia,
	modelo,
	data_inicio,
	precision=2,
	vencimento_calendario=None,
):
	"""Devolve a lista de linhas do plano de amortização (dicts prontos para um child table)."""
	if modelo not in MODELOS:
		frappe.throw(f"Modelo de cálculo de juros inválido: {modelo}")

	capital = flt(capital)
	period_days = get_period_days(frequencia)
	n = get_num_periodos(prazo_meses, frequencia)
	tj = get_taxa_por_periodo(taxa_juros_percent, frequencia)
	data_inicio = getdate(data_inicio)
	calendario = usar_vencimento_calendario(frequencia, vencimento_calendario)

	linhas = _calcular_linhas(capital, tj, n, modelo, precision)
	for idx, linha in enumerate(linhas, start=1):
		linha["data_limite_pagamento"] = (
			add_months(data_inicio, idx) if calendario else add_days(data_inicio, period_days * idx)
		)

	_preencher_saldos(linhas, capital, precision)
	return linhas


def _calcular_linhas(capital, tj, n, modelo, precision):
	"""Capital, juros e prestação de cada linha, já arredondados - ver as
	regras de arredondamento no topo do módulo."""
	capital = flt(capital, precision)

	# Prestação fixa do Francês (Tabela Price), arredondada uma só vez: todas
	# as prestações são iguais a este valor, exceto a última, que fecha o
	# saldo e pode diferir em cêntimos.
	if tj == 0:
		prestacao_fixa = flt(capital / n, precision)
	else:
		fator = (1 + tj) ** n
		prestacao_fixa = flt(capital * (tj * fator) / (fator - 1), precision)
	capital_fixo = flt(capital / n, precision)
	juros_constantes = flt(capital * tj, precision)

	linhas = []
	restante = capital
	for idx in range(1, n + 1):
		if modelo == "Constante":
			juros = juros_constantes
		else:
			juros = flt(restante * tj, precision)

		if idx == n:
			amortizacao = restante
		elif modelo == "Francês":
			amortizacao = flt(prestacao_fixa - juros, precision)
		else:
			amortizacao = capital_fixo
		amortizacao = min(max(amortizacao, 0), restante)
		restante = flt(restante - amortizacao, precision)

		linhas.append(
			{
				"numero": idx,
				"capital_mensal": amortizacao,
				"juros_mensais": juros,
				"prestacao_total": flt(amortizacao + juros, precision),
			}
		)

	if modelo == "Misto":
		_suavizar_prestacoes(linhas, precision)
	return linhas


def _suavizar_prestacoes(linhas, precision):
	"""Misto: o cliente paga sempre o mesmo valor (o total do plano a dividir
	pelo número de prestações); o desdobramento capital/juros de cada linha
	continua a ser o do Decrescente. Os cêntimos que sobram da divisão vão
	para a última prestação, para o total pago ser exatamente capital + juros."""
	n = len(linhas)
	total = flt(sum(linha["prestacao_total"] for linha in linhas), precision)
	fixa = flt(total / n, precision)
	for linha in linhas[:-1]:
		linha["prestacao_total"] = fixa
	linhas[-1]["prestacao_total"] = flt(total - fixa * (n - 1), precision)


def _preencher_saldos(linhas, capital, precision):
	"""Preenche dois saldos por prestação, ambos sobre os valores já
	arredondados - os mesmos valores que são
	efetivamente cobrados:

	- `saldo` (Saldo Total): tudo o que falta pagar do plano (capital + juros
	  das prestações seguintes). A última linha fecha sempre em 0.00, nunca em
	  resíduos como 0.01 ou -0.02.
	- `saldo_capital`: capital tomado menos o capital já amortizado até essa
	  prestação (inclusive) - a dívida de capital em si, sem os juros ainda
	  por vencer. Também fecha em 0.00 na última linha."""
	if not linhas:
		return
	total = sum(linha["prestacao_total"] for linha in linhas)
	pago_ate_agora = 0.0
	capital_amortizado = 0.0
	for linha in linhas:
		pago_ate_agora += linha["prestacao_total"]
		capital_amortizado += linha["capital_mensal"]
		linha["saldo"] = flt(total - pago_ate_agora, precision)
		linha["saldo_capital"] = flt(capital - capital_amortizado, precision)
	linhas[-1]["saldo"] = 0.0
	linhas[-1]["saldo_capital"] = 0.0
