# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

"""Dados agregados para o Painel de Crédito: cartões (Saldo do Crédito, Dívida,
Em Risco, PAR%, contagens, volume/receita do período) mais duas tabelas de
"precisa de atenção agora" (Carteira em Risco, Créditos em Atraso), todos
filtráveis pela mesma barra de filtros (Cliente/Produto/Finalidade/Datas).

Tudo é recalculado na hora a partir das datas (ver `calcular_saldos`), nunca a
partir do `status` gravado em Plano De Amortizacao - esse só é atualizado pela
tarefa diária `atualizar_atrasos` ou por um Reembolso submetido."""

import frappe
from frappe.utils import date_diff, flt, getdate, nowdate

from entre_mc.entre_mc.doctype.mc_settings.mc_settings import get_settings
from entre_mc.utils.reembolso import calcular_saldos

ESTADOS_CONSIDERADOS = ("Em Curso", "Incumprimento")
LIMITE_LINHAS = 15


@frappe.whitelist()
def obter_painel(cliente=None, produto=None, finalidade=None, data_inicio=None, data_fim=None):
	frappe.has_permission("Pedido De Credito", "read", throw=True)

	settings = get_settings()
	hoje = getdate(nowdate())

	pedido_filters = {"status": ["in", ESTADOS_CONSIDERADOS]}
	if cliente:
		pedido_filters["cliente"] = cliente
	if produto:
		pedido_filters["produto"] = produto
	if finalidade:
		pedido_filters["finalidade"] = finalidade

	pedidos = frappe.get_all(
		"Pedido De Credito", filters=pedido_filters, fields=["name", "cliente", "produto", "status"]
	)

	linhas_por_pedido = {}
	if pedidos:
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
		for linha in linhas:
			linhas_por_pedido.setdefault(linha.parent, []).append(linha)

	cards, carteira_em_risco = _cards_e_carteira_em_risco(pedidos, linhas_por_pedido, settings, hoje)
	creditos_em_atraso = _creditos_em_atraso(pedidos, linhas_por_pedido, settings, hoje)
	cards["desembolsado_periodo"], cards["taxas_periodo"] = _totais_do_periodo(
		cliente, produto, finalidade, data_inicio, data_fim
	)

	return {
		"cards": cards,
		"carteira_em_risco": carteira_em_risco[:LIMITE_LINHAS],
		"creditos_em_atraso": creditos_em_atraso[:LIMITE_LINHAS],
	}


def _cards_e_carteira_em_risco(pedidos, linhas_por_pedido, settings, hoje):
	total_saldo = 0
	total_divida = 0
	total_em_risco = 0
	num_ativos = 0
	num_incumprimento = 0
	carteira_em_risco = []

	for pedido in pedidos:
		if pedido.status == "Em Curso":
			num_ativos += 1
		elif pedido.status == "Incumprimento":
			num_incumprimento += 1

		saldo, divida, em_risco = calcular_saldos(linhas_por_pedido.get(pedido.name, []), settings, hoje)
		total_saldo += saldo
		total_divida += divida
		total_em_risco += em_risco

		if divida > 0:
			carteira_em_risco.append(
				{
					"name": pedido.name,
					"cliente": pedido.cliente,
					"saldo_do_credito": saldo,
					"divida": divida,
					"em_risco": em_risco,
				}
			)

	carteira_em_risco.sort(key=lambda d: d["em_risco"], reverse=True)

	cards = {
		"saldo_do_credito": total_saldo,
		"divida": total_divida,
		"em_risco": total_em_risco,
		"par_percent": flt(total_em_risco / total_saldo * 100) if total_saldo else 0,
		"num_ativos": num_ativos,
		"num_incumprimento": num_incumprimento,
	}
	return cards, carteira_em_risco


def _creditos_em_atraso(pedidos, linhas_por_pedido, settings, hoje):
	pedidos_por_nome = {p.name: p for p in pedidos}
	rows = []

	for nome, linhas in linhas_por_pedido.items():
		pedido = pedidos_por_nome.get(nome)
		if not pedido:
			continue
		for linha in linhas:
			dias_atraso = date_diff(hoje, linha.data_limite_pagamento) - flt(settings.dias_de_tolerancia)
			if dias_atraso <= 0:
				continue
			total_em_atraso = flt(
				(linha.capital_mensal - linha.capital_pago)
				+ (linha.juros_mensais - linha.juros_pago)
				+ (linha.multa_aplicada - linha.multa_paga)
				+ (linha.juros_mora_aplicado - linha.juros_mora_pago)
			)
			rows.append(
				{
					"parent": nome,
					"cliente": pedido.cliente,
					"numero": linha.numero,
					"data_limite_pagamento": linha.data_limite_pagamento,
					"dias_atraso": dias_atraso,
					"total_em_atraso": total_em_atraso,
				}
			)

	rows.sort(key=lambda d: d["dias_atraso"], reverse=True)
	return rows


def _totais_do_periodo(cliente, produto, finalidade, data_inicio, data_fim):
	desembolso_filters = {"docstatus": 1}
	if cliente:
		desembolso_filters["cliente"] = cliente
	if data_inicio or data_fim:
		desembolso_filters["data_de_desembolso"] = [
			"between",
			[data_inicio or "1900-01-01", data_fim or "2999-12-31"],
		]

	desembolsos = frappe.get_all(
		"Desembolso",
		filters=desembolso_filters,
		fields=["pedido_de_credito", "valor_desembolsado", "taxa_administrativa"],
	)

	if (produto or finalidade) and desembolsos:
		pedidos_ref = {
			p.name: p
			for p in frappe.get_all(
				"Pedido De Credito",
				filters={"name": ["in", list({d.pedido_de_credito for d in desembolsos})]},
				fields=["name", "produto", "finalidade"],
			)
		}
		if produto:
			desembolsos = [d for d in desembolsos if pedidos_ref.get(d.pedido_de_credito, {}).get("produto") == produto]
		if finalidade:
			desembolsos = [
				d for d in desembolsos if pedidos_ref.get(d.pedido_de_credito, {}).get("finalidade") == finalidade
			]

	total_desembolsado = sum(flt(d.valor_desembolsado) for d in desembolsos)
	total_taxas = sum(flt(d.taxa_administrativa) for d in desembolsos)
	return total_desembolsado, total_taxas
