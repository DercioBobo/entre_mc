# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import date_diff, flt, getdate, nowdate

from entre_mc.entre_mc.doctype.mc_settings.mc_settings import get_settings

FAIXAS = (
	(1, 30, "1-30 dias"),
	(31, 60, "31-60 dias"),
	(61, 90, "61-90 dias"),
	(91, None, "91+ dias"),
)


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": _("Cliente"), "fieldname": "cliente", "fieldtype": "Link", "options": "Cliente", "width": 160},
		{"label": _("Faixa de Atraso"), "fieldname": "faixa", "fieldtype": "Data", "width": 130},
		{"label": _("Nº de Prestações"), "fieldname": "num_prestacoes", "fieldtype": "Int", "width": 120},
		{"label": _("Capital em Falta"), "fieldname": "capital_em_falta", "fieldtype": "Currency", "width": 130},
		{"label": _("Juros em Falta"), "fieldname": "juros_em_falta", "fieldtype": "Currency", "width": 130},
		{"label": _("Multa"), "fieldname": "multa", "fieldtype": "Currency", "width": 110},
		{"label": _("Juros de Mora"), "fieldname": "juros_mora", "fieldtype": "Currency", "width": 120},
		{"label": _("Total em Atraso"), "fieldname": "total_em_atraso", "fieldtype": "Currency", "width": 135},
	]


def get_data(filters):
	"""Agrupa as prestações em atraso por Cliente e por faixa de dias de atraso
	(1-30/31-60/61-90/91+), a partir das datas - não do `status` gravado -
	pelo mesmo motivo do relatório Creditos em Atraso: esse campo só é
	atualizado pela tarefa diária `atualizar_atrasos` ou por um Reembolso
	submetido."""
	settings = get_settings()
	hoje = getdate(nowdate())

	rows = frappe.get_all(
		"Plano De Amortizacao",
		filters={"status": ["!=", "Pago"], "parenttype": "Pedido De Credito"},
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
	if not rows:
		return []

	pedidos = {
		p.name: p
		for p in frappe.get_all(
			"Pedido De Credito",
			filters={"name": ["in", list({r.parent for r in rows})]},
			fields=["name", "cliente", "produto"],
		)
	}
	if filters.get("cliente"):
		rows = [r for r in rows if pedidos.get(r.parent, {}).get("cliente") == filters["cliente"]]
	if filters.get("produto"):
		rows = [r for r in rows if pedidos.get(r.parent, {}).get("produto") == filters["produto"]]

	buckets = {}
	for row in rows:
		dias_atraso = date_diff(hoje, row.data_limite_pagamento) - flt(settings.dias_de_tolerancia)
		if dias_atraso <= 0:
			continue
		cliente = pedidos.get(row.parent, {}).get("cliente")
		bucket = buckets.setdefault(
			(cliente, _faixa(dias_atraso)),
			{"num_prestacoes": 0, "capital": 0, "juros": 0, "multa": 0, "mora": 0},
		)
		bucket["num_prestacoes"] += 1
		bucket["capital"] += flt(row.capital_mensal) - flt(row.capital_pago)
		bucket["juros"] += flt(row.juros_mensais) - flt(row.juros_pago)
		bucket["multa"] += flt(row.multa_aplicada) - flt(row.multa_paga)
		bucket["mora"] += flt(row.juros_mora_aplicado) - flt(row.juros_mora_pago)

	data = []
	clientes = sorted({cliente for cliente, _faixa_label in buckets}, key=lambda c: c or "")
	for cliente in clientes:
		for _ini, _fim, label in FAIXAS:
			bucket = buckets.get((cliente, label))
			if not bucket:
				continue
			total = bucket["capital"] + bucket["juros"] + bucket["multa"] + bucket["mora"]
			data.append(
				{
					"cliente": cliente,
					"faixa": label,
					"num_prestacoes": bucket["num_prestacoes"],
					"capital_em_falta": bucket["capital"],
					"juros_em_falta": bucket["juros"],
					"multa": bucket["multa"],
					"juros_mora": bucket["mora"],
					"total_em_atraso": total,
				}
			)
	return data


def _faixa(dias_atraso):
	for inicio, fim, label in FAIXAS:
		if (fim is None or dias_atraso <= fim) and dias_atraso >= inicio:
			return label
	return FAIXAS[-1][2]
