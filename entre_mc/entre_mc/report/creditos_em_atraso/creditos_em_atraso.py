# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import date_diff, flt, getdate, nowdate


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": _("Pedido"), "fieldname": "parent", "fieldtype": "Link", "options": "Pedido De Credito", "width": 140},
		{"label": _("Cliente"), "fieldname": "cliente", "fieldtype": "Link", "options": "Cliente", "width": 160},
		{"label": _("Nº Prestação"), "fieldname": "numero", "fieldtype": "Int", "width": 90},
		{"label": _("Data Limite"), "fieldname": "data_limite_pagamento", "fieldtype": "Date", "width": 100},
		{"label": _("Dias de Atraso"), "fieldname": "dias_atraso", "fieldtype": "Int", "width": 100},
		{"label": _("Capital em Falta"), "fieldname": "capital_em_falta", "fieldtype": "Currency", "width": 120},
		{"label": _("Juros em Falta"), "fieldname": "juros_em_falta", "fieldtype": "Currency", "width": 120},
		{"label": _("Multa"), "fieldname": "multa_aplicada", "fieldtype": "Currency", "width": 100},
		{"label": _("Juros de Mora"), "fieldname": "juros_mora_aplicado", "fieldtype": "Currency", "width": 110},
		{"label": _("Total em Atraso"), "fieldname": "total_em_atraso", "fieldtype": "Currency", "width": 120},
	]


def get_data(filters):
	rows = frappe.get_all(
		"Plano De Amortizacao",
		filters={"status": "Atrasado", "parenttype": "Pedido De Credito"},
		fields=[
			"parent",
			"numero",
			"data_limite_pagamento",
			"capital_mensal",
			"capital_pago",
			"juros_mensais",
			"juros_pago",
			"multa_aplicada",
			"juros_mora_aplicado",
		],
	)
	if not rows:
		return []

	pedidos = {
		p.name: p
		for p in frappe.get_all(
			"Pedido De Credito",
			filters={"name": ["in", list({r.parent for r in rows})]},
			fields=["name", "cliente"],
		)
	}
	if filters.get("cliente"):
		rows = [r for r in rows if pedidos.get(r.parent, {}).get("cliente") == filters["cliente"]]

	hoje = getdate(nowdate())
	data = []
	for r in rows:
		capital_em_falta = flt(r.capital_mensal) - flt(r.capital_pago)
		juros_em_falta = flt(r.juros_mensais) - flt(r.juros_pago)
		multa = flt(r.multa_aplicada)
		mora = flt(r.juros_mora_aplicado)
		data.append(
			{
				"parent": r.parent,
				"cliente": pedidos.get(r.parent, {}).get("cliente"),
				"numero": r.numero,
				"data_limite_pagamento": r.data_limite_pagamento,
				"dias_atraso": date_diff(hoje, r.data_limite_pagamento),
				"capital_em_falta": capital_em_falta,
				"juros_em_falta": juros_em_falta,
				"multa_aplicada": multa,
				"juros_mora_aplicado": mora,
				"total_em_atraso": capital_em_falta + juros_em_falta + multa + mora,
			}
		)
	data.sort(key=lambda d: d["dias_atraso"], reverse=True)
	return data
