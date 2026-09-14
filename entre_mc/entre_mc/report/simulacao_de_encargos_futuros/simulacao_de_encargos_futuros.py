# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

"""Um crédito ativo por linha, projetando quanto ficaria a dever numa
"Data de Referência" futura escolhida pelo utilizador - Capital, Juros, Multa
e Juros de Mora, tal como em Contas a Receber, mas assumindo que o cliente não
faz nenhum pagamento entre hoje e essa data.

Útil para responder, numa conversa com o cliente, "quanto vou dever se só
pagar daqui a X dias?" - sem ter de esperar chegar lá para ver o valor real.

Capital e Juros não mudam com a data (não há capitalização de juros neste
produto - ver `MC Settings.ativar_capitalizacao`, ainda reservado). Só Multa e
Juros de Mora dependem da Data de Referência: são recalculados em memória
(nunca gravados) com essa data em vez de hoje, usando a mesma
`atualizar_encargos_da_linha` da tarefa diária `atualizar_atrasos` - a fórmula
da Multa (taxa × dias de atraso × valor em atraso) e o disparo único do Juros
de Mora funcionam para qualquer data de referência, não só para hoje.

Só aceita datas de hoje em diante: para uma data passada, o valor persistido
em `multa_aplicada`/`juros_mora_aplicado` pode já ter sido recalculado para
hoje pela tarefa diária, e `atualizar_encargos_da_linha` não retrocede um
encargo já lançado - o resultado seria incorreto. Para a situação real de
hoje, usar Contas a Receber."""

import frappe
from frappe import _
from frappe.utils import date_diff, flt, getdate, nowdate

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
		{"label": _("Dias em Atraso na Data"), "fieldname": "dias_atraso", "fieldtype": "Int", "width": 130},
		{"label": _("Capital a Receber"), "fieldname": "capital", "fieldtype": "Currency", "width": 130},
		{"label": _("Juros a Receber"), "fieldname": "juros", "fieldtype": "Currency", "width": 130},
		{"label": _("Multa Projetada"), "fieldname": "multa", "fieldtype": "Currency", "width": 130},
		{"label": _("Juros de Mora Projetado"), "fieldname": "juros_mora", "fieldtype": "Currency", "width": 150},
		{"label": _("Total Projetado"), "fieldname": "total_a_receber", "fieldtype": "Currency", "width": 140},
		{"label": _("Dos Quais Vencidos na Data"), "fieldname": "vencido", "fieldtype": "Currency", "width": 160},
	]


def get_data(filters):
	settings = get_settings()
	hoje = getdate(nowdate())
	data_referencia = getdate(filters.get("data_referencia")) if filters.get("data_referencia") else hoje
	if data_referencia < hoje:
		frappe.throw(
			_(
				"A Data de Referência tem de ser hoje ou uma data futura - para a situação real de hoje, "
				"use o relatório Contas a Receber."
			)
		)

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
				row, pedido.taxa_diaria_de_multa, pedido.juros_de_mora, settings, data_referencia, 2
			)

		capital = juros = multa = mora = 0
		dias_atraso = 0
		for row in rows:
			capital += flt(row.capital_mensal) - flt(row.capital_pago)
			juros += flt(row.juros_mensais) - flt(row.juros_pago)
			multa += flt(row.multa_aplicada) - flt(row.multa_paga) - flt(row.multa_perdoada)
			mora += flt(row.juros_mora_aplicado) - flt(row.juros_mora_pago) - flt(row.juros_mora_perdoado)

			atraso = date_diff(data_referencia, row.data_limite_pagamento) - flt(settings.dias_de_tolerancia)
			dias_atraso = max(dias_atraso, atraso)

		_saldo, divida, _em_risco = calcular_saldos(rows, settings, data_referencia)
		total = flt(capital + juros + multa + mora)

		data.append(
			{
				"pedido": nome,
				"cliente": pedido.cliente,
				"promotor_name": pedido.promotor_name,
				"produto": pedido.produto,
				"status": pedido.status,
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
