# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt

ATIVOS = ("Em Curso",)


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
		{"label": _("Capital Solicitado"), "fieldname": "capital_solicitado", "fieldtype": "Currency", "width": 130},
		{"label": _("Valor de Juros"), "fieldname": "valor_de_juros", "fieldtype": "Currency", "width": 120},
		{"label": _("Saldo do Crédito"), "fieldname": "saldo_em_divida", "fieldtype": "Currency", "width": 130},
		{"label": _("Taxa de Juros (%)"), "fieldname": "taxa_de_juros", "fieldtype": "Percent", "width": 100},
		{"label": _("Frequência"), "fieldname": "frequencia", "fieldtype": "Data", "width": 100},
		{"label": _("Prazo"), "fieldname": "prazo", "fieldtype": "Date", "width": 100},
		{
			"label": _("Data do Último Reembolso"),
			"fieldname": "data_ultimo_reembolso",
			"fieldtype": "Date",
			"width": 150,
		},
		{"label": _("Estado"), "fieldname": "status", "fieldtype": "Data", "width": 120},
	]


def get_data(filters):
	""""Prazo" aqui é a data de vencimento da última prestação do Plano De
	Amortizacao (não o Prazo em número de prestações gravado no Pedido);
	"Valor de Juros" é o total de juros contratado (soma de todas as
	prestações do plano, pagas ou não); "Data do Último Reembolso" é a data
	do Reembolso submetido mais recente do pedido."""
	query_filters = {"status": ["in", ATIVOS]}
	if filters.get("cliente"):
		query_filters["cliente"] = filters["cliente"]
	if filters.get("produto"):
		query_filters["produto"] = filters["produto"]

	pedidos = frappe.get_all(
		"Pedido De Credito",
		filters=query_filters,
		fields=[
			"name",
			"cliente",
			"promotor_name",
			"produto",
			"capital_solicitado",
			"saldo_em_divida",
			"taxa_de_juros",
			"frequencia",
			"status",
		],
		order_by="saldo_em_divida desc",
	)
	if not pedidos:
		return []

	nomes = [p.name for p in pedidos]

	prazo_por_pedido = {}
	juros_por_pedido = {}
	for linha in frappe.get_all(
		"Plano De Amortizacao",
		filters={"parent": ["in", nomes], "parenttype": "Pedido De Credito"},
		fields=["parent", "numero", "data_limite_pagamento", "juros_mensais"],
	):
		juros_por_pedido[linha.parent] = juros_por_pedido.get(linha.parent, 0) + flt(linha.juros_mensais)
		atual = prazo_por_pedido.get(linha.parent)
		if atual is None or linha.numero > atual[0]:
			prazo_por_pedido[linha.parent] = (linha.numero, linha.data_limite_pagamento)

	ultimo_reembolso_por_pedido = {}
	for r in frappe.get_all(
		"Reembolso",
		filters={"pedido_de_credito": ["in", nomes], "docstatus": 1},
		fields=["pedido_de_credito", "data_de_pagamento"],
	):
		atual = ultimo_reembolso_por_pedido.get(r.pedido_de_credito)
		if atual is None or r.data_de_pagamento > atual:
			ultimo_reembolso_por_pedido[r.pedido_de_credito] = r.data_de_pagamento

	for pedido in pedidos:
		pedido["valor_de_juros"] = flt(juros_por_pedido.get(pedido.name, 0))
		pedido["prazo"] = (prazo_por_pedido.get(pedido.name) or (None, None))[1]
		pedido["data_ultimo_reembolso"] = ultimo_reembolso_por_pedido.get(pedido.name)

	return pedidos
