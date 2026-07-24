# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

"""Extrato de Cliente: ledger cronológico de tudo o que aconteceu com um
cliente - desembolsos (débito), prestações agendadas (referência), reembolsos
recebidos (crédito) e execuções de garantia (crédito não monetário) - com um
Saldo Devedor corrido que só se move nos eventos reais de liquidação
(Desembolso/Reembolso/Execução de Garantia), tal como um extrato real.

Cada linha também mostra a composição Capital / Juros / Multa / Juros de Mora:
para uma Prestação são os valores agendados nessa prestação; para um
Reembolso são os valores efetivamente alocados a cada componente nesse
pagamento (via Alocação de Reembolso, a mesma fonte usada no Relatório de
Cobranças); para um Desembolso, o valor todo é capital; para uma Execução de
Garantia (dação em pagamento), o valor todo aparece como crédito sem
composição por componente - o Pedido De Credito.marcar_como_liquidado() não
preserva essa quebra ao dar as prestações por pagas."""

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate

TIPO_DESEMBOLSO = 0
TIPO_PRESTACAO = 1
TIPO_REEMBOLSO = 2
TIPO_EXECUCAO_GARANTIA = 3


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	if not filters.get("cliente"):
		return columns, []
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": _("Data"), "fieldname": "data", "fieldtype": "Date", "width": 95},
		{"label": _("Tipo"), "fieldname": "tipo", "fieldtype": "Data", "width": 100},
		{"label": _("Pedido"), "fieldname": "pedido", "fieldtype": "Link", "options": "Pedido De Credito", "width": 130},
		{"label": _("Descrição"), "fieldname": "descricao", "fieldtype": "Data", "width": 220},
		{"label": _("Débito"), "fieldname": "debito", "fieldtype": "Currency", "width": 105},
		{"label": _("Crédito"), "fieldname": "credito", "fieldtype": "Currency", "width": 105},
		{"label": _("Capital"), "fieldname": "capital", "fieldtype": "Currency", "width": 100},
		{"label": _("Juros"), "fieldname": "juros", "fieldtype": "Currency", "width": 100},
		{"label": _("Multa"), "fieldname": "multa", "fieldtype": "Currency", "width": 90},
		{"label": _("Juros de Mora"), "fieldname": "juros_mora", "fieldtype": "Currency", "width": 105},
		{"label": _("Estado"), "fieldname": "estado", "fieldtype": "Data", "width": 100},
		{"label": _("Saldo Devedor"), "fieldname": "saldo_devedor", "fieldtype": "Currency", "width": 130},
	]


def get_data(filters):
	cliente = filters["cliente"]

	pedido_filters = {"cliente": cliente}
	if filters.get("pedido_de_credito"):
		pedido_filters["name"] = filters["pedido_de_credito"]

	pedidos = frappe.get_all("Pedido De Credito", filters=pedido_filters, fields=["name", "produto"])
	if not pedidos:
		return []
	pedido_names = [p.name for p in pedidos]
	produto_por_pedido = {p.name: p.produto for p in pedidos}

	eventos = []
	eventos += get_eventos_desembolso(pedido_names, produto_por_pedido)
	if cint(filters.get("incluir_prestacoes", 1)):
		eventos += get_eventos_prestacao(pedido_names)
	eventos += get_eventos_reembolso(pedido_names)
	eventos += get_eventos_execucao_garantia(pedido_names)

	eventos.sort(key=lambda e: (e["data"], e["_ordem"]))

	saldo = 0
	for e in eventos:
		saldo = flt(saldo + e["debito"] - e["credito"])
		e["saldo_devedor"] = saldo
		del e["_ordem"]

	data_inicio = getdate(filters["data_inicio"]) if filters.get("data_inicio") else None
	data_fim = getdate(filters["data_fim"]) if filters.get("data_fim") else None
	if data_inicio:
		eventos = [e for e in eventos if e["data"] >= data_inicio]
	if data_fim:
		eventos = [e for e in eventos if e["data"] <= data_fim]

	return eventos


def get_eventos_desembolso(pedido_names, produto_por_pedido):
	desembolsos = frappe.get_all(
		"Desembolso",
		filters={"pedido_de_credito": ["in", pedido_names], "docstatus": 1},
		fields=["pedido_de_credito", "data_de_desembolso", "valor_desembolsado"],
	)
	return [
		{
			"data": getdate(d.data_de_desembolso),
			"tipo": _("Desembolso"),
			"pedido": d.pedido_de_credito,
			"descricao": _("Desembolso - {0}").format(produto_por_pedido.get(d.pedido_de_credito) or ""),
			"debito": flt(d.valor_desembolsado),
			"credito": 0,
			"capital": flt(d.valor_desembolsado),
			"juros": 0,
			"multa": 0,
			"juros_mora": 0,
			"estado": "",
			"_ordem": TIPO_DESEMBOLSO,
		}
		for d in desembolsos
	]


def get_eventos_prestacao(pedido_names):
	prestacoes = frappe.get_all(
		"Plano De Amortizacao",
		filters={"parent": ["in", pedido_names], "parenttype": "Pedido De Credito"},
		fields=[
			"parent",
			"numero",
			"data_limite_pagamento",
			"capital_mensal",
			"juros_mensais",
			"multa_aplicada",
			"juros_mora_aplicado",
			"status",
		],
	)
	return [
		{
			"data": getdate(p.data_limite_pagamento),
			"tipo": _("Prestação"),
			"pedido": p.parent,
			"descricao": _("Prestação Nº {0}").format(p.numero),
			"debito": 0,
			"credito": 0,
			"capital": flt(p.capital_mensal),
			"juros": flt(p.juros_mensais),
			"multa": flt(p.multa_aplicada),
			"juros_mora": flt(p.juros_mora_aplicado),
			"estado": _(p.status),
			"_ordem": TIPO_PRESTACAO,
		}
		for p in prestacoes
	]


def get_eventos_reembolso(pedido_names):
	reembolsos = frappe.get_all(
		"Reembolso",
		filters={"pedido_de_credito": ["in", pedido_names], "docstatus": 1},
		fields=["name", "pedido_de_credito", "data_de_pagamento", "montante_pago"],
	)
	if not reembolsos:
		return []

	alocacoes = frappe.get_all(
		"Alocacao De Reembolso",
		filters={"parent": ["in", [r.name for r in reembolsos]]},
		fields=["parent", "componente", "valor"],
	)
	por_reembolso = {}
	for a in alocacoes:
		bucket = por_reembolso.setdefault(a.parent, {})
		bucket[a.componente] = bucket.get(a.componente, 0) + flt(a.valor)

	eventos = []
	for r in reembolsos:
		comp = por_reembolso.get(r.name, {})
		eventos.append(
			{
				"data": getdate(r.data_de_pagamento),
				"tipo": _("Reembolso"),
				"pedido": r.pedido_de_credito,
				"descricao": _("Reembolso recebido ({0})").format(r.name),
				"debito": 0,
				"credito": flt(r.montante_pago),
				"capital": comp.get("Capital", 0),
				"juros": comp.get("Juros", 0),
				"multa": comp.get("Multa", 0),
				"juros_mora": comp.get("Juros de Mora", 0),
				"estado": "",
				"_ordem": TIPO_REEMBOLSO,
			}
		)
	return eventos


def get_eventos_execucao_garantia(pedido_names):
	execucoes = frappe.get_all(
		"Execucao De Garantia",
		filters={"pedido_de_credito": ["in", pedido_names], "docstatus": 1},
		fields=["name", "pedido_de_credito", "garantia", "data", "valor_liquidado"],
	)
	return [
		{
			"data": getdate(e.data),
			"tipo": _("Garantia Executada"),
			"pedido": e.pedido_de_credito,
			"descricao": _("Garantia executada ({0}) - dação em pagamento ({1})").format(e.garantia, e.name),
			"debito": 0,
			"credito": flt(e.valor_liquidado),
			"capital": 0,
			"juros": 0,
			"multa": 0,
			"juros_mora": 0,
			"estado": _("Dação em Pagamento"),
			"_ordem": TIPO_EXECUCAO_GARANTIA,
		}
		for e in execucoes
	]
