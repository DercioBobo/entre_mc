# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": _("Desembolso"), "fieldname": "name", "fieldtype": "Link", "options": "Desembolso", "width": 140},
		{"label": _("Cliente"), "fieldname": "cliente", "fieldtype": "Link", "options": "Cliente", "width": 160},
		{"label": _("Promotor"), "fieldname": "promotor_name", "fieldtype": "Data", "width": 140},
		{
			"label": _("Pedido"),
			"fieldname": "pedido_de_credito",
			"fieldtype": "Link",
			"options": "Pedido De Credito",
			"width": 140,
		},
		{"label": _("Produto"), "fieldname": "produto", "fieldtype": "Link", "options": "Produto", "width": 130},
		{"label": _("Data de Desembolso"), "fieldname": "data_de_desembolso", "fieldtype": "Date", "width": 120},
		{"label": _("Capital Solicitado"), "fieldname": "capital_solicitado", "fieldtype": "Currency", "width": 130},
		{"label": _("Taxa Administrativa"), "fieldname": "taxa_administrativa", "fieldtype": "Currency", "width": 135},
		{"label": _("Valor Desembolsado"), "fieldname": "valor_desembolsado", "fieldtype": "Currency", "width": 130},
	]


def get_data(filters):
	"""Um Desembolso.taxa_administrativa é herdado do Pedido De Credito (fetch_from)
	no momento em que o Pedido é escolhido, por isso o valor aqui já reflete a
	configuração de MC Settings vigente nessa altura - alterar a taxa depois não
	reescreve desembolsos já submetidos."""
	query_filters = {"docstatus": 1}
	if filters.get("cliente"):
		query_filters["cliente"] = filters["cliente"]
	if filters.get("data_inicio") or filters.get("data_fim"):
		query_filters["data_de_desembolso"] = [
			"between",
			[filters.get("data_inicio") or "1900-01-01", filters.get("data_fim") or "2999-12-31"],
		]

	desembolsos = frappe.get_all(
		"Desembolso",
		filters=query_filters,
		fields=[
			"name",
			"cliente",
			"pedido_de_credito",
			"data_de_desembolso",
			"taxa_administrativa",
			"valor_desembolsado",
		],
		order_by="data_de_desembolso desc",
	)
	if not desembolsos:
		return []

	pedidos = {
		p.name: p
		for p in frappe.get_all(
			"Pedido De Credito",
			filters={"name": ["in", list({d.pedido_de_credito for d in desembolsos})]},
			fields=["name", "produto", "capital_solicitado", "promotor_name"],
		)
	}
	if filters.get("produto"):
		desembolsos = [
			d for d in desembolsos if pedidos.get(d.pedido_de_credito, {}).get("produto") == filters["produto"]
		]

	data = []
	for d in desembolsos:
		pedido = pedidos.get(d.pedido_de_credito) or {}
		data.append(
			{
				**d,
				"produto": pedido.get("produto"),
				"capital_solicitado": pedido.get("capital_solicitado"),
				"promotor_name": pedido.get("promotor_name"),
			}
		)
	return data
