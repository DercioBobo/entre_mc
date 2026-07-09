# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": _("Reembolso"), "fieldname": "name", "fieldtype": "Link", "options": "Reembolso", "width": 140},
		{"label": _("Cliente"), "fieldname": "cliente", "fieldtype": "Link", "options": "Cliente", "width": 160},
		{
			"label": _("Pedido"),
			"fieldname": "pedido_de_credito",
			"fieldtype": "Link",
			"options": "Pedido De Credito",
			"width": 140,
		},
		{"label": _("Data de Pagamento"), "fieldname": "data_de_pagamento", "fieldtype": "Date", "width": 110},
		{"label": _("Montante Pago"), "fieldname": "montante_pago", "fieldtype": "Currency", "width": 120},
		{"label": _("Juros de Mora"), "fieldname": "juros_de_mora", "fieldtype": "Currency", "width": 110},
		{"label": _("Multa"), "fieldname": "multa", "fieldtype": "Currency", "width": 100},
		{"label": _("Juros"), "fieldname": "juros", "fieldtype": "Currency", "width": 100},
		{"label": _("Capital"), "fieldname": "capital", "fieldtype": "Currency", "width": 100},
	]


def get_data(filters):
	query_filters = {"docstatus": 1}
	if filters.get("cliente"):
		query_filters["cliente"] = filters["cliente"]
	if filters.get("pedido_de_credito"):
		query_filters["pedido_de_credito"] = filters["pedido_de_credito"]
	if filters.get("data_inicio") or filters.get("data_fim"):
		query_filters["data_de_pagamento"] = [
			"between",
			[filters.get("data_inicio") or "1900-01-01", filters.get("data_fim") or "2999-12-31"],
		]

	reembolsos = frappe.get_all(
		"Reembolso",
		filters=query_filters,
		fields=["name", "cliente", "pedido_de_credito", "data_de_pagamento", "montante_pago"],
		order_by="data_de_pagamento desc",
	)
	if not reembolsos:
		return []

	alocacoes = frappe.get_all(
		"Alocacao De Reembolso",
		filters={"parent": ["in", [r.name for r in reembolsos]]},
		fields=["parent", "componente", "valor"],
	)
	por_reembolso = {}
	for a in alocacoes:
		bucket = por_reembolso.setdefault(a.parent, {})
		bucket[a.componente] = bucket.get(a.componente, 0) + flt(a.valor)

	data = []
	for r in reembolsos:
		comp = por_reembolso.get(r.name, {})
		data.append(
			{
				**r,
				"juros_de_mora": comp.get("Juros de Mora", 0),
				"multa": comp.get("Multa", 0),
				"juros": comp.get("Juros", 0),
				"capital": comp.get("Capital", 0),
			}
		)
	return data
