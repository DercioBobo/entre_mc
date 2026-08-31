# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

"""Previsto vs. Realizado dos recebimentos de um período (por defeito o mês corrente).

Uma linha por crédito com:

- **Previsto**: Capital + Juros (+ Multa + Juros de Mora) das prestações do Plano
  De Amortizacao cuja `data_limite_pagamento` cai no período - o que se espera
  cobrar. Multa/Mora são recalculadas em memória para hoje (ou para o fim do
  período, o que for mais cedo), como em Prestacoes a Receber e Contas a Receber,
  porque os encargos gravados na linha só são atualizados pela tarefa diária
  `atualizar_atrasos` ou por um Reembolso submetido.
- **Realizado**: o que foi efetivamente alocado a Capital/Juros/Multa/Mora pelos
  Reembolsos com `data_de_pagamento` no período - a mesma fonte do Relatorio de
  Cobrancas, atribuído pela data do pagamento (não pela prestação a que foi
  aplicado).
- **Desvio**: Total Realizado - Total Previsto.

Com `add_total_row`, a última linha dá o previsto e o realizado de toda a carteira
para o período - o número para responder a "cobrei o que esperava este mês?".
"""

import frappe
from frappe import _
from frappe.utils import flt, get_first_day, get_last_day, getdate, nowdate

from entre_mc.entre_mc.doctype.mc_settings.mc_settings import get_settings
from entre_mc.utils.reembolso import atualizar_encargos_da_linha

ESTADOS_CONSIDERADOS = ("Em Curso", "Incumprimento", "Liquidado")


def execute(filters=None):
	filters = filters or {}
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": _("Pedido"), "fieldname": "pedido", "fieldtype": "Link", "options": "Pedido De Credito", "width": 140},
		{"label": _("Cliente"), "fieldname": "cliente", "fieldtype": "Link", "options": "Cliente", "width": 160},
		{"label": _("Promotor"), "fieldname": "promotor_name", "fieldtype": "Data", "width": 130},
		{"label": _("Produto"), "fieldname": "produto", "fieldtype": "Link", "options": "Produto", "width": 120},
		{"label": _("Capital Previsto"), "fieldname": "capital_previsto", "fieldtype": "Currency", "width": 130},
		{"label": _("Juros Previsto"), "fieldname": "juros_previsto", "fieldtype": "Currency", "width": 125},
		{"label": _("Encargos Previstos"), "fieldname": "encargos_previstos", "fieldtype": "Currency", "width": 140},
		{"label": _("Total Previsto"), "fieldname": "total_previsto", "fieldtype": "Currency", "width": 130},
		{"label": _("Capital Recebido"), "fieldname": "capital_recebido", "fieldtype": "Currency", "width": 135},
		{"label": _("Juros Recebido"), "fieldname": "juros_recebido", "fieldtype": "Currency", "width": 130},
		{"label": _("Encargos Recebidos"), "fieldname": "encargos_recebidos", "fieldtype": "Currency", "width": 145},
		{"label": _("Total Recebido"), "fieldname": "total_recebido", "fieldtype": "Currency", "width": 130},
		{"label": _("Desvio"), "fieldname": "desvio", "fieldtype": "Currency", "width": 120},
	]


def get_data(filters):
	settings = get_settings()
	hoje = getdate(nowdate())

	data_inicio = getdate(filters.get("data_inicio")) if filters.get("data_inicio") else get_first_day(hoje)
	data_fim = getdate(filters.get("data_fim")) if filters.get("data_fim") else get_last_day(hoje)
	data_ref_encargos = min(hoje, data_fim)

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
		fields=["name", "cliente", "produto", "promotor_name", "taxa_diaria_de_multa", "juros_de_mora"],
	)
	if not pedidos:
		return []

	pedidos_por_nome = {p.name: p for p in pedidos}

	previsto = _previsto_por_pedido(pedidos_por_nome, data_inicio, data_fim, data_ref_encargos, settings)
	recebido = _recebido_por_pedido(list(pedidos_por_nome), data_inicio, data_fim)

	data = []
	for nome, pedido in pedidos_por_nome.items():
		prev = previsto.get(nome, {})
		rec = recebido.get(nome, {})

		capital_previsto = flt(prev.get("capital"))
		juros_previsto = flt(prev.get("juros"))
		encargos_previstos = flt(prev.get("multa")) + flt(prev.get("mora"))
		total_previsto = capital_previsto + juros_previsto + encargos_previstos

		capital_recebido = flt(rec.get("Capital"))
		juros_recebido = flt(rec.get("Juros"))
		encargos_recebidos = flt(rec.get("Multa")) + flt(rec.get("Juros de Mora"))
		total_recebido = capital_recebido + juros_recebido + encargos_recebidos

		if total_previsto == 0 and total_recebido == 0:
			continue

		data.append(
			{
				"pedido": nome,
				"cliente": pedido.cliente,
				"promotor_name": pedido.promotor_name,
				"produto": pedido.produto,
				"capital_previsto": capital_previsto,
				"juros_previsto": juros_previsto,
				"encargos_previstos": encargos_previstos,
				"total_previsto": total_previsto,
				"capital_recebido": capital_recebido,
				"juros_recebido": juros_recebido,
				"encargos_recebidos": encargos_recebidos,
				"total_recebido": total_recebido,
				"desvio": flt(total_recebido - total_previsto),
			}
		)

	data.sort(key=lambda d: d["total_previsto"], reverse=True)
	return data


def _previsto_por_pedido(pedidos_por_nome, data_inicio, data_fim, data_ref_encargos, settings):
	linhas = frappe.get_all(
		"Plano De Amortizacao",
		filters={
			"parenttype": "Pedido De Credito",
			"parent": ["in", list(pedidos_por_nome)],
			"status": ["!=", "Pago"],
			"data_limite_pagamento": ["between", [data_inicio, data_fim]],
		},
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

	previsto = {}
	for row in linhas:
		pedido = pedidos_por_nome[row.parent]
		atualizar_encargos_da_linha(
			row, pedido.taxa_diaria_de_multa, pedido.juros_de_mora, settings, data_ref_encargos, 2
		)
		bucket = previsto.setdefault(row.parent, {"capital": 0, "juros": 0, "multa": 0, "mora": 0})
		bucket["capital"] += flt(row.capital_mensal) - flt(row.capital_pago)
		bucket["juros"] += flt(row.juros_mensais) - flt(row.juros_pago)
		bucket["multa"] += flt(row.multa_aplicada) - flt(row.multa_paga)
		bucket["mora"] += flt(row.juros_mora_aplicado) - flt(row.juros_mora_pago)

	return previsto


def _recebido_por_pedido(nomes_pedidos, data_inicio, data_fim):
	reembolsos = frappe.get_all(
		"Reembolso",
		filters={
			"docstatus": 1,
			"pedido_de_credito": ["in", nomes_pedidos],
			"data_de_pagamento": ["between", [data_inicio, data_fim]],
		},
		fields=["name", "pedido_de_credito"],
	)
	if not reembolsos:
		return {}

	reembolso_para_pedido = {r.name: r.pedido_de_credito for r in reembolsos}
	alocacoes = frappe.get_all(
		"Alocacao De Reembolso",
		filters={"parent": ["in", list(reembolso_para_pedido)]},
		fields=["parent", "componente", "valor"],
	)

	recebido = {}
	for a in alocacoes:
		pedido = reembolso_para_pedido[a.parent]
		bucket = recebido.setdefault(pedido, {})
		bucket[a.componente] = bucket.get(a.componente, 0) + flt(a.valor)

	return recebido
