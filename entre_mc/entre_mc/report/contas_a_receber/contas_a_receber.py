# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

"""Um crédito ativo por linha, com tudo o que falta receber dele repartido nas
suas quatro parcelas - Capital, Juros, Multa e Juros de Mora - e o total.

É a visão que os outros relatórios dão em pedaços: Carteira de Crédito Ativa
mostra só o saldo, Creditos em Atraso / Aging só a parte já vencida. Aqui a
linha "Total a Receber" (com `add_total_row`) dá o valor a receber de toda a
carteira num só número, e por cliente/promotor com os filtros.

Multa e Juros de Mora são recalculados em memória para hoje (como em Creditos
em Atraso e Reembolso.obter_contexto) - o `status`/encargos gravados em Plano
De Amortizacao só são atualizados pela tarefa diária `atualizar_atrasos` ou
por um Reembolso submetido, por isso não podem ser a fonte de verdade aqui.
"""

import frappe
from frappe import _
from frappe.utils import cint, date_diff, flt, getdate, nowdate

from entre_mc.entre_mc.doctype.mc_settings.mc_settings import get_settings
from entre_mc.utils.reembolso import atualizar_encargos_da_linha, calcular_saldos

ESTADOS_CONSIDERADOS = ("Em Curso", "Incumprimento")


def execute(filters=None):
	filters = filters or {}
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": _("Pedido"), "fieldname": "pedido", "fieldtype": "Link", "options": "Pedido De Credito", "width": 140},
		{"label": _("Cliente"), "fieldname": "cliente", "fieldtype": "Link", "options": "Cliente", "width": 160},
		{"label": _("Promotor"), "fieldname": "promotor_name", "fieldtype": "Data", "width": 130},
		{"label": _("Produto"), "fieldname": "produto", "fieldtype": "Link", "options": "Produto", "width": 120},
		{"label": _("Estado"), "fieldname": "status", "fieldtype": "Data", "width": 110},
		{"label": _("Próximo Vencimento"), "fieldname": "proximo_vencimento", "fieldtype": "Date", "width": 130},
		{"label": _("Dias em Atraso"), "fieldname": "dias_atraso", "fieldtype": "Int", "width": 110},
		{"label": _("Capital a Receber"), "fieldname": "capital", "fieldtype": "Currency", "width": 130},
		{"label": _("Juros a Receber"), "fieldname": "juros", "fieldtype": "Currency", "width": 130},
		{"label": _("Multa"), "fieldname": "multa", "fieldtype": "Currency", "width": 110},
		{"label": _("Juros de Mora"), "fieldname": "juros_mora", "fieldtype": "Currency", "width": 120},
		{"label": _("Total a Receber"), "fieldname": "total_a_receber", "fieldtype": "Currency", "width": 140},
		{"label": _("Dos Quais Vencidos"), "fieldname": "vencido", "fieldtype": "Currency", "width": 140},
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

	pedidos = frappe.get_all(
		"Pedido De Credito",
		filters=query_filters,
		fields=[
			"name",
			"cliente",
			"produto",
			"status",
			"promotor_name",
			"taxa_diaria_de_multa",
			"juros_de_mora",
		],
	)
	if not pedidos:
		return []

	pedidos_por_nome = {p.name: p for p in pedidos}

	linhas_por_pedido = {}
	for linha in frappe.get_all(
		"Plano De Amortizacao",
		filters={
			"status": ["!=", "Pago"],
			"parenttype": "Pedido De Credito",
			"parent": ["in", list(pedidos_por_nome)],
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
			"multa_perdoada",
			"isento_de_multa",
			"juros_mora_aplicado",
			"juros_mora_pago",
			"juros_mora_perdoado",
		],
	):
		linhas_por_pedido.setdefault(linha.parent, []).append(linha)

	data = []
	for nome, pedido in pedidos_por_nome.items():
		rows = linhas_por_pedido.get(nome, [])
		if not rows:
			continue

		for row in rows:
			atualizar_encargos_da_linha(
				row, pedido.taxa_diaria_de_multa, pedido.juros_de_mora, settings, hoje, 2
			)

		capital = juros = multa = mora = 0
		proximo_vencimento = None
		dias_atraso = 0
		for row in rows:
			capital += flt(row.capital_mensal) - flt(row.capital_pago)
			juros += flt(row.juros_mensais) - flt(row.juros_pago)
			multa += flt(row.multa_aplicada) - flt(row.multa_paga) - flt(row.multa_perdoada)
			mora += flt(row.juros_mora_aplicado) - flt(row.juros_mora_pago) - flt(row.juros_mora_perdoado)

			if proximo_vencimento is None or getdate(row.data_limite_pagamento) < proximo_vencimento:
				proximo_vencimento = getdate(row.data_limite_pagamento)
			atraso = date_diff(hoje, row.data_limite_pagamento) - flt(settings.dias_de_tolerancia)
			dias_atraso = max(dias_atraso, atraso)

		_saldo, divida, _em_risco = calcular_saldos(rows, settings, hoje)
		total = flt(capital + juros + multa + mora)

		if cint(filters.get("apenas_em_atraso")) and divida <= 0:
			continue

		data.append(
			{
				"pedido": nome,
				"cliente": pedido.cliente,
				"promotor_name": pedido.promotor_name,
				"produto": pedido.produto,
				"status": pedido.status,
				"proximo_vencimento": proximo_vencimento,
				"dias_atraso": max(dias_atraso, 0),
				"capital": flt(capital),
				"juros": flt(juros),
				"multa": flt(multa),
				"juros_mora": flt(mora),
				"total_a_receber": total,
				"vencido": flt(divida),
			}
		)

	data.sort(key=lambda d: (d["vencido"], d["total_a_receber"]), reverse=True)
	return data
