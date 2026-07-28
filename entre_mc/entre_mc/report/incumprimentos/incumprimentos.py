# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import date_diff, flt, getdate, nowdate

from entre_mc.entre_mc.doctype.mc_settings.mc_settings import get_settings
from entre_mc.utils.reembolso import calcular_saldos


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": _("Pedido"), "fieldname": "name", "fieldtype": "Link", "options": "Pedido De Credito", "width": 140},
		{"label": _("Cliente"), "fieldname": "cliente", "fieldtype": "Link", "options": "Cliente", "width": 160},
		{"label": _("Produto"), "fieldname": "produto", "fieldtype": "Link", "options": "Produto", "width": 130},
		{"label": _("Dias em Atraso"), "fieldname": "dias_atraso", "fieldtype": "Int", "width": 100},
		{"label": _("Saldo do Crédito"), "fieldname": "saldo_do_credito", "fieldtype": "Currency", "width": 130},
		{"label": _("Dívida"), "fieldname": "divida", "fieldtype": "Currency", "width": 120},
		{"label": _("Valor de Garantias"), "fieldname": "valor_garantias", "fieldtype": "Currency", "width": 135},
		{"label": _("Cobertura (%)"), "fieldname": "cobertura", "fieldtype": "Percent", "width": 100},
	]


def get_data(filters):
	"""Pedidos em Incumprimento, com Saldo do Crédito/Dívida recalculados na
	hora (ver `calcular_saldos` - não confiamos no que está gravado pelo mesmo
	motivo de sempre: só é atualizado pela tarefa diária ou por um Reembolso
	submetido) e o valor de mercado das Garantias vinculadas.

	Cobertura = valor das Garantias ÷ Saldo do Crédito - apoia a decisão de
	executar a Garantia (dação em pagamento): abaixo de 100% a garantia não
	cobre sequer o que falta pagar."""
	settings = get_settings()
	hoje = getdate(nowdate())

	query_filters = {"status": "Incumprimento"}
	if filters.get("cliente"):
		query_filters["cliente"] = filters["cliente"]
	if filters.get("produto"):
		query_filters["produto"] = filters["produto"]

	pedidos = frappe.get_all("Pedido De Credito", filters=query_filters, fields=["name", "cliente", "produto"])
	if not pedidos:
		return []

	nomes = [p.name for p in pedidos]

	linhas = frappe.get_all(
		"Plano De Amortizacao",
		filters={"status": ["!=", "Pago"], "parenttype": "Pedido De Credito", "parent": ["in", nomes]},
		fields=[
			"parent",
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

	pedido_garantia_rows = frappe.get_all(
		"Pedido Garantia",
		filters={"parent": ["in", nomes], "parenttype": "Pedido De Credito"},
		fields=["parent", "garantia"],
	)
	garantia_nomes = list({r.garantia for r in pedido_garantia_rows})

	valor_por_garantia = {}
	if garantia_nomes:
		itens = frappe.get_all(
			"Item De Garantia", filters={"parent": ["in", garantia_nomes]}, fields=["parent", "valor_de_mercado"]
		)
		for item in itens:
			valor_por_garantia[item.parent] = valor_por_garantia.get(item.parent, 0) + flt(item.valor_de_mercado)

	garantias_por_pedido = {}
	for r in pedido_garantia_rows:
		garantias_por_pedido[r.parent] = garantias_por_pedido.get(r.parent, 0) + valor_por_garantia.get(
			r.garantia, 0
		)

	data = []
	for pedido in pedidos:
		rows = linhas_por_pedido.get(pedido.name, [])
		saldo, divida, _em_risco = calcular_saldos(rows, settings, hoje)

		dias_atraso = 0
		for row in rows:
			atraso = date_diff(hoje, row.data_limite_pagamento) - flt(settings.dias_de_tolerancia)
			dias_atraso = max(dias_atraso, atraso)

		valor_garantias = flt(garantias_por_pedido.get(pedido.name, 0))
		cobertura = flt(valor_garantias / saldo * 100) if saldo else 0

		data.append(
			{
				"name": pedido.name,
				"cliente": pedido.cliente,
				"produto": pedido.produto,
				"dias_atraso": dias_atraso,
				"saldo_do_credito": saldo,
				"divida": divida,
				"valor_garantias": valor_garantias,
				"cobertura": cobertura,
			}
		)

	data.sort(key=lambda d: d["dias_atraso"], reverse=True)
	return data
