# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import date_diff, flt, getdate, nowdate

from entre_mc.entre_mc.doctype.mc_settings.mc_settings import get_settings
from entre_mc.utils.reembolso import calcular_saldos

ESTADOS_CONSIDERADOS = ("Em Curso", "Incumprimento")

# Faixas de PAR (Portfolio at Risk) - classificação por dias de atraso da
# prestação mais atrasada do pedido, distinta das faixas usadas em Aging da
# Carteira (1-30/31-60/61-90/91+), que agrupa prestações, não pedidos. Cada
# faixa é uma coluna própria no relatório (em vez de uma única coluna "PAR"),
# com o valor "Em Risco" do pedido lançado na coluna correspondente à sua
# faixa e 0 nas restantes.
FAIXAS_PAR = (
	(1, 30, "par_1_30", "PAR 1-30"),
	(31, 90, "par_31_90", "PAR 31-90"),
	(91, 365, "par_91_365", "PAR 91-365"),
	(366, None, "par_365_mais", "PAR 365+"),
)


def _fieldname_par(dias_atraso):
	for inicio, fim, fieldname, _label in FAIXAS_PAR:
		if (fim is None or dias_atraso <= fim) and dias_atraso >= inicio:
			return fieldname
	return FAIXAS_PAR[-1][2]


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": _("Pedido"), "fieldname": "name", "fieldtype": "Link", "options": "Pedido De Credito", "width": 140},
		{"label": _("Cliente"), "fieldname": "cliente", "fieldtype": "Link", "options": "Cliente", "width": 160},
		{"label": _("Promotor"), "fieldname": "promotor_name", "fieldtype": "Data", "width": 140},
		{"label": _("Produto"), "fieldname": "produto", "fieldtype": "Link", "options": "Produto", "width": 130},
		{"label": _("Estado"), "fieldname": "status", "fieldtype": "Data", "width": 110},
		{
			"label": _("Capital Desembolsado"),
			"fieldname": "capital_desembolsado",
			"fieldtype": "Currency",
			"width": 150,
		},
		{"label": _("Saldo do Crédito"), "fieldname": "saldo_do_credito", "fieldtype": "Currency", "width": 130},
		{"label": _("Dívida"), "fieldname": "divida", "fieldtype": "Currency", "width": 120},
		{"label": _("Juros a Pagar"), "fieldname": "juros_a_pagar", "fieldtype": "Currency", "width": 120},
	] + [
		{"label": _(label), "fieldname": fieldname, "fieldtype": "Currency", "width": 120}
		for _ini, _fim, fieldname, label in FAIXAS_PAR
	]


def get_data(filters):
	"""Pedidos com pelo menos uma prestação em atraso (Dívida > 0), com o valor
	"Em Risco" = Dívida + a próxima prestação ainda não vencida - ver
	`calcular_saldos` para a definição de cada termo. "Juros a Pagar" é a soma
	dos juros ainda não pagos (vencidos ou não) das prestações em aberto;
	"Capital Desembolsado" vem do(s) Desembolso submetido(s) do pedido, que
	pode divergir do Capital Solicitado (o tesoureiro pode ajustar o valor
	desembolsado). O pedido é classificado pela sua prestação mais atrasada
	nas faixas 1-30/31-90/91-365/365+ dias, e o seu "Em Risco" é lançado na
	coluna PAR correspondente a essa faixa (0 nas restantes).

	Calculado a partir das datas (não do `status` gravado em Plano De
	Amortizacao), pelo mesmo motivo do relatório Creditos em Atraso: esse
	campo só é atualizado pela tarefa diária `atualizar_atrasos` ou por um
	Reembolso submetido, e não pode ser a fonte de verdade aqui."""
	settings = get_settings()
	hoje = getdate(nowdate())

	query_filters = {"status": ["in", ESTADOS_CONSIDERADOS]}
	if filters.get("cliente"):
		query_filters["cliente"] = filters["cliente"]
	if filters.get("produto"):
		query_filters["produto"] = filters["produto"]

	pedidos = frappe.get_all(
		"Pedido De Credito",
		filters=query_filters,
		fields=["name", "cliente", "produto", "status", "promotor_name"],
	)
	if not pedidos:
		return []

	linhas = frappe.get_all(
		"Plano De Amortizacao",
		filters={
			"status": ["!=", "Pago"],
			"parenttype": "Pedido De Credito",
			"parent": ["in", [p.name for p in pedidos]],
		},
		fields=[
			"parent",
			"numero",
			"data_limite_pagamento",
			"capital_mensal",
			"capital_pago",
			"juros_mensais",
			"juros_pago",
			"multa_aplicada",
			"multa_paga",
			"juros_mora_aplicado",
			"juros_mora_pago",
		],
	)
	linhas_por_pedido = {}
	for linha in linhas:
		linhas_por_pedido.setdefault(linha.parent, []).append(linha)

	desembolsado_por_pedido = {}
	for d in frappe.get_all(
		"Desembolso",
		filters={"pedido_de_credito": ["in", [p.name for p in pedidos]], "docstatus": 1},
		fields=["pedido_de_credito", "valor_desembolsado"],
	):
		desembolsado_por_pedido[d.pedido_de_credito] = desembolsado_por_pedido.get(
			d.pedido_de_credito, 0
		) + flt(d.valor_desembolsado)

	data = []
	for pedido in pedidos:
		rows = linhas_por_pedido.get(pedido.name, [])
		saldo, divida, em_risco = calcular_saldos(rows, settings, hoje)
		if divida <= 0:
			continue

		dias_atraso = 0
		juros_a_pagar = 0
		for row in rows:
			juros_a_pagar += flt(row.juros_mensais) - flt(row.juros_pago)
			atraso = date_diff(hoje, row.data_limite_pagamento) - flt(settings.dias_de_tolerancia)
			dias_atraso = max(dias_atraso, atraso)

		linha = {
			"name": pedido.name,
			"cliente": pedido.cliente,
			"promotor_name": pedido.promotor_name,
			"produto": pedido.produto,
			"status": pedido.status,
			"capital_desembolsado": desembolsado_por_pedido.get(pedido.name, 0),
			"saldo_do_credito": saldo,
			"divida": divida,
			"juros_a_pagar": flt(juros_a_pagar),
		}
		for _ini, _fim, fieldname, _label in FAIXAS_PAR:
			linha[fieldname] = 0
		linha[_fieldname_par(dias_atraso)] = em_risco
		data.append(linha)

	data.sort(key=lambda d: sum(d[fieldname] for _ini, _fim, fieldname, _label in FAIXAS_PAR), reverse=True)
	return data
