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
"""

import frappe
from frappe.utils import add_days, flt, getdate

PERIOD_DAYS = {
	"Diário": 1,
	"Semanal": 7,
	"Quinzenal": 15,
	"Mensal": 30,
}

MODELOS = ("Constante", "Decrescente", "Misto")


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


def build_plano(capital, taxa_juros_percent, prazo_meses, frequencia, modelo, data_inicio, precision=2):
	"""Devolve a lista de linhas do plano de amortização (dicts prontos para um child table)."""
	if modelo not in MODELOS:
		frappe.throw(f"Modelo de cálculo de juros inválido: {modelo}")

	capital = flt(capital)
	period_days = get_period_days(frequencia)
	n = get_num_periodos(prazo_meses, frequencia)
	tj = get_taxa_por_periodo(taxa_juros_percent, frequencia)
	data_inicio = getdate(data_inicio)

	if modelo == "Constante":
		prestacoes = _build_constante(capital, tj, n)
	else:
		prestacoes = _build_decrescente_ou_misto(capital, tj, n, suavizar=(modelo == "Misto"))

	valor_total = sum(p["prestacao_total"] for p in prestacoes)

	linhas = []
	saldo_restante = valor_total
	for idx, p in enumerate(prestacoes, start=1):
		saldo_restante = flt(saldo_restante - p["prestacao_total"], precision)
		linhas.append(
			{
				"numero": idx,
				"capital_mensal": flt(p["capital_mensal"], precision),
				"juros_mensais": flt(p["juros_mensais"], precision),
				"prestacao_total": flt(p["prestacao_total"], precision),
				"saldo": saldo_restante,
				"data_limite_pagamento": add_days(data_inicio, period_days * idx),
			}
		)
	return linhas


def _build_constante(capital, tj, n):
	cm = capital / n
	jm = capital * tj
	pt = cm + jm
	return [{"capital_mensal": cm, "juros_mensais": jm, "prestacao_total": pt} for _ in range(n)]


def _build_decrescente_ou_misto(capital, tj, n, suavizar):
	cm = capital / n
	capital_amortizado = 0.0
	prestacoes = []
	for _ in range(n):
		scr = capital - capital_amortizado
		jm = scr * tj
		pt = cm + jm
		prestacoes.append({"capital_mensal": cm, "juros_mensais": jm, "prestacao_total": pt})
		capital_amortizado += cm

	if suavizar:
		vtp = sum(p["prestacao_total"] for p in prestacoes)
		pt_fixo = vtp / n
		for p in prestacoes:
			p["prestacao_total"] = pt_fixo

	return prestacoes
