# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

import frappe
from frappe import _

EM_APROVACAO = ("Pendente Aprovação 1", "Pendente Aprovação 2")


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
		{"label": _("Estado de Aprovação"), "fieldname": "workflow_state", "fieldtype": "Data", "width": 170},
		{"label": _("Criado em"), "fieldname": "creation", "fieldtype": "Datetime", "width": 150},
	]


def get_data(filters):
	query_filters = {"workflow_state": ["in", EM_APROVACAO]}
	if filters.get("workflow_state"):
		query_filters["workflow_state"] = filters["workflow_state"]

	return frappe.get_all(
		"Pedido De Credito",
		filters=query_filters,
		fields=["name", "cliente", "produto", "capital_solicitado", "workflow_state", "creation"],
		order_by="creation asc",
	)
