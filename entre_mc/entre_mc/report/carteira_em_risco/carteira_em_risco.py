# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import getdate, nowdate

from entre_mc.entre_mc.doctype.mc_settings.mc_settings import get_settings
from entre_mc.utils.reembolso import calcular_saldos

ESTADOS_CONSIDERADOS = ("Desembolsado", "Em Pagamento", "Incumprimento")


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
		{"label": _("Estado"), "fieldname": "status", "fieldtype": "Data", "width": 110},
		{"label": _("Saldo do Crédito"), "fieldname": "saldo_do_credito", "fieldtype": "Currency", "width": 130},
		{"label": _("Dívida"), "fieldname": "divida", "fieldtype": "Currency", "width": 120},
		{"label": _("Em Risco"), "fieldname": "em_risco", "fieldtype": "Currency", "width": 120},
	]


def get_data(filters):
	"""Pedidos com pelo menos uma prestação em atraso (Dívida > 0), com o valor
	"Em Risco" = Dívida + a próxima prestação ainda não vencida - ver
	`calcular_saldos` para a definição de cada termo.

	Calculado a partir das datas (não do `status` gravado em Plano De
	Amortizacao), pelo mesmo motivo do relatório Creditos em Atraso: esse
	campo só é atualizado pela tarefa diária `atualizar_atrasos` ou por um
	Reembolso submetido, e não pode ser a fonte de verdade aqui."""
	settings = get_settings()
	hoje = getdate(nowdate())

	query_filters = {"status": ["in", ESTADOS_CONSIDERADOS]}
	if filters.get("cliente"):
		query_filters["cliente"] = filters["cliente"]
	if filters.get("produto"):
		query_filters["produto"] = filters["produto"]

	pedidos = frappe.get_all(
		"Pedido De Credito",
		filters=query_filters,
		fields=["name", "cliente", "produto", "status"],
	)
	if not pedidos:
		return []

	linhas = frappe.get_all(
		"Plano De Amortizacao",
		filters={
			"status": ["!=", "Pago"],
			"parenttype": "Pedido De Credito",
			"parent": ["in", [p.name for p in pedidos]],
		},
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
	linhas_por_pedido = {}
	for linha in linhas:
		linhas_por_pedido.setdefault(linha.parent, []).append(linha)

	data = []
	for pedido in pedidos:
		saldo, divida, em_risco = calcular_saldos(linhas_por_pedido.get(pedido.name, []), settings, hoje)
		if divida <= 0:
			continue
		data.append(
			{
				"name": pedido.name,
				"cliente": pedido.cliente,
				"produto": pedido.produto,
				"status": pedido.status,
				"saldo_do_credito": saldo,
				"divida": divida,
				"em_risco": em_risco,
			}
		)

	data.sort(key=lambda d: d["em_risco"], reverse=True)
	return data
