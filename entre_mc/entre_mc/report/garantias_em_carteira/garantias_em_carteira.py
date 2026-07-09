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
		{"label": _("Garantia"), "fieldname": "name", "fieldtype": "Link", "options": "Garantia", "width": 130},
		{"label": _("Cliente"), "fieldname": "cliente", "fieldtype": "Link", "options": "Cliente", "width": 160},
		{"label": _("Estado"), "fieldname": "status", "fieldtype": "Data", "width": 110},
		{"label": _("Data"), "fieldname": "data", "fieldtype": "Date", "width": 100},
		{"label": _("Nº de Itens"), "fieldname": "num_itens", "fieldtype": "Int", "width": 90},
		{"label": _("Valor de Mercado Total"), "fieldname": "valor_total", "fieldtype": "Currency", "width": 150},
	]


def get_data(filters):
	query_filters = {}
	if filters.get("cliente"):
		query_filters["cliente"] = filters["cliente"]
	if filters.get("status"):
		query_filters["status"] = filters["status"]

	garantias = frappe.get_all(
		"Garantia", filters=query_filters, fields=["name", "cliente", "status", "data"], order_by="data desc"
	)
	if not garantias:
		return []

	itens = frappe.get_all(
		"Item De Garantia",
		filters={"parent": ["in", [g.name for g in garantias]]},
		fields=["parent", "valor_de_mercado"],
	)
	por_garantia = {}
	for i in itens:
		bucket = por_garantia.setdefault(i.parent, {"num_itens": 0, "valor_total": 0})
		bucket["num_itens"] += 1
		bucket["valor_total"] += flt(i.valor_de_mercado)

	data = []
	for g in garantias:
		agg = por_garantia.get(g.name, {"num_itens": 0, "valor_total": 0})
		data.append({**g, **agg})
	return data
