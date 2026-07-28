# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import date_diff, flt, getdate, nowdate

from entre_mc.entre_mc.doctype.mc_settings.mc_settings import get_settings
from entre_mc.utils.reembolso import atualizar_encargos_da_linha


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
	"""Prestações em atraso, calculado a partir das datas - não do campo `status`
	gravado em Plano De Amortizacao.

	`status` só passa a "Atrasado" quando a tarefa diária `atualizar_atrasos`
	corre (ou quando um Reembolso é submetido) - se o scheduler não tiver
	corrido ainda hoje, ou estiver desligado no site, prestações realmente em
	atraso continuam gravadas como "Pendente" e este relatório ficava vazio
	mesmo havendo atrasos reais. Recalculamos aqui em memória (sem gravar),
	tal como `Reembolso.obter_contexto` e `Pedido De Credito.plano_com_encargos_atuais`
	fazem pelo mesmo motivo."""
	settings = get_settings()
	hoje = getdate(nowdate())

	rows = frappe.get_all(
		"Plano De Amortizacao",
		filters={"status": ["!=", "Pago"], "parenttype": "Pedido De Credito"},
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
	if not rows:
		return []

	pedidos = {
		p.name: p
		for p in frappe.get_all(
			"Pedido De Credito",
			filters={"name": ["in", list({r.parent for r in rows})]},
			fields=["name", "cliente", "taxa_diaria_de_multa", "juros_de_mora"],
		)
	}
	if filters.get("cliente"):
		rows = [r for r in rows if pedidos.get(r.parent, {}).get("cliente") == filters["cliente"]]

	data = []
	for r in rows:
		dias_atraso = date_diff(hoje, r.data_limite_pagamento) - flt(settings.dias_de_tolerancia)
		if dias_atraso <= 0:
			continue

		pedido = pedidos.get(r.parent) or {}
		atualizar_encargos_da_linha(
			r, pedido.get("taxa_diaria_de_multa"), pedido.get("juros_de_mora"), settings, hoje, 2
		)

		capital_em_falta = flt(r.capital_mensal) - flt(r.capital_pago)
		juros_em_falta = flt(r.juros_mensais) - flt(r.juros_pago)
		multa = flt(r.multa_aplicada) - flt(r.multa_paga)
		mora = flt(r.juros_mora_aplicado) - flt(r.juros_mora_pago)
		data.append(
			{
				"parent": r.parent,
				"cliente": pedido.get("cliente"),
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
