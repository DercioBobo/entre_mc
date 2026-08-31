# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

"""O Plano De Amortizacao de cada crédito, prestação a prestação, com uma coluna
"Total a Receber" por linha - Capital + Juros ainda por pagar dessa prestação,
mais Multa e Juros de Mora acumulados nela.

É a mesma tabela que aparece no formulário do Pedido De Credito, mas
consolidável em toda a carteira (ou filtrada por cliente/produto/pedido) e com
`add_total_row`, para ter o total a receber somado ao fundo. Para o total por
crédito (uma linha por pedido em vez de por prestação) usar Contas a Receber.

Multa e Juros de Mora são recalculados em memória para hoje - como em Creditos
em Atraso e Reembolso.obter_contexto - porque os valores/estado gravados em
Plano De Amortizacao só são atualizados pela tarefa diária `atualizar_atrasos`
ou por um Reembolso submetido.
"""

import frappe
from frappe import _
from frappe.utils import cint, date_diff, flt, getdate, nowdate

from entre_mc.entre_mc.doctype.mc_settings.mc_settings import get_settings
from entre_mc.utils.reembolso import atualizar_encargos_da_linha, atualizar_estado_da_linha

ESTADOS_CONSIDERADOS = ("Em Curso", "Incumprimento")


def execute(filters=None):
	filters = filters or {}
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": _("Pedido"), "fieldname": "pedido", "fieldtype": "Link", "options": "Pedido De Credito", "width": 140},
		{"label": _("Cliente"), "fieldname": "cliente", "fieldtype": "Link", "options": "Cliente", "width": 150},
		{"label": _("Nº"), "fieldname": "numero", "fieldtype": "Int", "width": 55},
		{"label": _("Data Limite"), "fieldname": "data_limite_pagamento", "fieldtype": "Date", "width": 100},
		{"label": _("Estado"), "fieldname": "status", "fieldtype": "Data", "width": 100},
		{"label": _("Dias em Atraso"), "fieldname": "dias_atraso", "fieldtype": "Int", "width": 100},
		{"label": _("Prestação"), "fieldname": "prestacao_total", "fieldtype": "Currency", "width": 110},
		{"label": _("Capital a Receber"), "fieldname": "capital", "fieldtype": "Currency", "width": 130},
		{"label": _("Juros a Receber"), "fieldname": "juros", "fieldtype": "Currency", "width": 130},
		{"label": _("Multa"), "fieldname": "multa", "fieldtype": "Currency", "width": 100},
		{"label": _("Juros de Mora"), "fieldname": "juros_mora", "fieldtype": "Currency", "width": 115},
		{"label": _("Total a Receber"), "fieldname": "total_a_receber", "fieldtype": "Currency", "width": 135},
	]


def get_data(filters):
	settings = get_settings()
	hoje = getdate(nowdate())

	query_filters = {"status": ["in", ESTADOS_CONSIDERADOS]}
	if filters.get("cliente"):
		query_filters["cliente"] = filters["cliente"]
	if filters.get("produto"):
		query_filters["produto"] = filters["produto"]
	if filters.get("promotor"):
		query_filters["promotor"] = filters["promotor"]
	if filters.get("pedido_de_credito"):
		query_filters["name"] = filters["pedido_de_credito"]

	pedidos = frappe.get_all(
		"Pedido De Credito",
		filters=query_filters,
		fields=["name", "cliente", "taxa_diaria_de_multa", "juros_de_mora"],
	)
	if not pedidos:
		return []

	pedidos_por_nome = {p.name: p for p in pedidos}
	incluir_pagas = cint(filters.get("incluir_pagas"))
	apenas_em_atraso = cint(filters.get("apenas_em_atraso"))

	plano_filtros = {
		"parenttype": "Pedido De Credito",
		"parent": ["in", list(pedidos_por_nome)],
	}
	if not incluir_pagas:
		plano_filtros["status"] = ["!=", "Pago"]

	linhas = frappe.get_all(
		"Plano De Amortizacao",
		filters=plano_filtros,
		fields=[
			"parent",
			"numero",
			"data_limite_pagamento",
			"status",
			"prestacao_total",
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
	if not linhas:
		return []

	data = []
	for row in linhas:
		pedido = pedidos_por_nome[row.parent]
		if row.status != "Pago":
			atualizar_encargos_da_linha(
				row, pedido.taxa_diaria_de_multa, pedido.juros_de_mora, settings, hoje, 2
			)
			atualizar_estado_da_linha(row, hoje, settings)

		capital = flt(row.capital_mensal) - flt(row.capital_pago)
		juros = flt(row.juros_mensais) - flt(row.juros_pago)
		multa = flt(row.multa_aplicada) - flt(row.multa_paga)
		mora = flt(row.juros_mora_aplicado) - flt(row.juros_mora_pago)
		total = flt(capital + juros + multa + mora)

		dias_atraso = date_diff(hoje, row.data_limite_pagamento) - flt(settings.dias_de_tolerancia)
		if apenas_em_atraso and dias_atraso <= 0:
			continue

		data.append(
			{
				"pedido": row.parent,
				"cliente": pedido.cliente,
				"numero": row.numero,
				"data_limite_pagamento": row.data_limite_pagamento,
				"status": row.status,
				"dias_atraso": max(dias_atraso, 0),
				"prestacao_total": flt(row.prestacao_total),
				"capital": capital,
				"juros": juros,
				"multa": multa,
				"juros_mora": mora,
				"total_a_receber": total,
			}
		)

	data.sort(key=lambda d: (d["pedido"], d["numero"]))
	return data
