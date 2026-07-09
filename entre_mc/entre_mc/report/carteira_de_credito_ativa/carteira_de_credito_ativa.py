# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

import frappe
from frappe import _

ATIVOS = ("Desembolsado", "Em Pagamento")


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
		{"label": _("Capital Solicitado"), "fieldname": "capital_solicitado", "fieldtype": "Currency", "width": 130},
		{"label": _("Saldo em Dívida"), "fieldname": "saldo_em_divida", "fieldtype": "Currency", "width": 130},
		{"label": _("Taxa de Juros"), "fieldname": "taxa_de_juros", "fieldtype": "Percent", "width": 100},
		{"label": _("Frequência"), "fieldname": "frequencia", "fieldtype": "Data", "width": 100},
		{"label": _("Estado"), "fieldname": "status", "fieldtype": "Data", "width": 120},
	]


def get_data(filters):
	query_filters = {"status": ["in", ATIVOS]}
	if filters.get("cliente"):
		query_filters["cliente"] = filters["cliente"]
	if filters.get("produto"):
		query_filters["produto"] = filters["produto"]

	return frappe.get_all(
		"Pedido De Credito",
		filters=query_filters,
		fields=[
			"name",
			"cliente",
			"produto",
			"capital_solicitado",
			"saldo_em_divida",
			"taxa_de_juros",
			"frequencia",
			"status",
		],
		order_by="saldo_em_divida desc",
	)
