# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

"""Dados para o Painel de Crédito: cartões agregados da carteira (Saldo do
Crédito, Dívida, Em Risco, PAR%, contagens, volume/receita do período) e a
lista de todos os créditos com a situação de cada um, filtráveis pela mesma
barra de filtros (Cliente/Produto/Finalidade/Datas). Cada linha abre a Ficha
do Crédito (ver page/ficha_do_credito).

Os cartões contam só a carteira viva ("Em Curso" e "Incumprimento"); os
créditos liquidados só entram na lista, e só quando pedidos.

Tudo é recalculado na hora a partir das datas (ver `calcular_saldos`), nunca a
partir do `status` gravado em Plano De Amortizacao - esse só é atualizado pela
tarefa diária `atualizar_atrasos` ou por um Reembolso submetido."""

import frappe
from frappe.utils import cint, date_diff, flt, getdate, nowdate

from entre_mc.entre_mc.doctype.mc_settings.mc_settings import get_settings
from entre_mc.utils.reembolso import calcular_saldos, decompor_saldos

ESTADOS_CONSIDERADOS = ("Em Curso", "Incumprimento")


@frappe.whitelist()
def obter_painel(
	cliente=None, produto=None, finalidade=None, data_inicio=None, data_fim=None, incluir_liquidados=0
):
	frappe.has_permission("Pedido De Credito", "read", throw=True)

	settings = get_settings()
	hoje = getdate(nowdate())

	estados = list(ESTADOS_CONSIDERADOS) + (["Liquidado"] if cint(incluir_liquidados) else [])
	pedido_filters = {"status": ["in", estados]}
	if cliente:
		pedido_filters["cliente"] = cliente
	if produto:
		pedido_filters["produto"] = produto
	if finalidade:
		pedido_filters["finalidade"] = finalidade

	pedidos = frappe.get_all(
		"Pedido De Credito",
		filters=pedido_filters,
		fields=[
			"name",
			"cliente",
			"produto",
			"status",
			"promotor_name",
			"capital_solicitado",
			"congelado",
			"reestruturado",
		],
	)
	nomes = [p.name for p in pedidos]

	linhas_por_pedido = {}
	desembolso_por_pedido = {}
	if pedidos:
		for linha in frappe.get_all(
			"Plano De Amortizacao",
			filters={"status": ["!=", "Pago"], "parenttype": "Pedido De Credito", "parent": ["in", nomes]},
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
				"juros_mora_aplicado",
				"juros_mora_pago",
				"juros_mora_perdoado",
			],
		):
			linhas_por_pedido.setdefault(linha.parent, []).append(linha)

		for d in frappe.get_all(
			"Desembolso",
			filters={"docstatus": 1, "pedido_de_credito": ["in", nomes]},
			fields=["pedido_de_credito", "data_de_desembolso"],
		):
			atual = desembolso_por_pedido.get(d.pedido_de_credito)
			if not atual or d.data_de_desembolso < atual:
				desembolso_por_pedido[d.pedido_de_credito] = d.data_de_desembolso

	creditos = [
		_situacao_do_credito(p, linhas_por_pedido.get(p.name, []), desembolso_por_pedido.get(p.name), settings, hoje)
		for p in pedidos
	]
	creditos.sort(key=lambda c: (-c["dias_atraso"], -c["saldo_do_credito"]))

	cards = _cards([c for c in creditos if c["status"] in ESTADOS_CONSIDERADOS])
	cards["desembolsado_periodo"], cards["taxas_periodo"] = _totais_do_periodo(
		cliente, produto, finalidade, data_inicio, data_fim
	)
	return {"cards": cards, "creditos": creditos}


def _situacao_do_credito(pedido, linhas, data_de_desembolso, settings, hoje):
	saldo, divida, em_risco = calcular_saldos(linhas, settings, hoje)
	partes, _divida_partes = decompor_saldos(linhas, settings, hoje)

	dias_atraso = 0
	proxima = None
	for linha in linhas:
		em_falta = (
			flt(linha.capital_mensal)
			- flt(linha.capital_pago)
			+ flt(linha.juros_mensais)
			- flt(linha.juros_pago)
			+ flt(linha.multa_aplicada)
			- flt(linha.multa_paga)
			- flt(linha.multa_perdoada)
			+ flt(linha.juros_mora_aplicado)
			- flt(linha.juros_mora_pago)
			- flt(linha.juros_mora_perdoado)
		)
		if em_falta <= 0:
			continue
		atraso = date_diff(hoje, linha.data_limite_pagamento) - flt(settings.dias_de_tolerancia)
		dias_atraso = max(dias_atraso, atraso)
		if proxima is None or linha.numero < proxima.numero:
			proxima = linha

	if pedido.status == "Liquidado":
		situacao = "Liquidado"
	elif pedido.status == "Incumprimento":
		situacao = "Incumprimento"
	elif divida > 0:
		situacao = "Em atraso"
	else:
		situacao = "Em dia"

	return {
		"name": pedido.name,
		"cliente": pedido.cliente,
		"produto": pedido.produto,
		"promotor": pedido.promotor_name,
		"status": pedido.status,
		"situacao": situacao,
		"congelado": cint(pedido.congelado),
		"reestruturado": cint(pedido.reestruturado),
		"data_de_desembolso": data_de_desembolso,
		"capital_solicitado": flt(pedido.capital_solicitado),
		"saldo_do_credito": flt(saldo),
		"divida": flt(divida),
		"em_risco": flt(em_risco),
		"multa_e_mora": flt(partes["multa"] + partes["mora"], 2),
		"dias_atraso": int(max(dias_atraso, 0)),
		"proximo_vencimento": proxima.data_limite_pagamento if proxima else None,
	}


def _cards(creditos):
	total_saldo = sum(c["saldo_do_credito"] for c in creditos)
	total_em_risco = sum(c["em_risco"] for c in creditos)
	return {
		"saldo_do_credito": total_saldo,
		"divida": sum(c["divida"] for c in creditos),
		"em_risco": total_em_risco,
		"par_percent": flt(total_em_risco / total_saldo * 100) if total_saldo else 0,
		"num_ativos": len([c for c in creditos if c["status"] == "Em Curso"]),
		"num_incumprimento": len([c for c in creditos if c["status"] == "Incumprimento"]),
		"num_em_atraso": len([c for c in creditos if c["divida"] > 0]),
		"num_congelados": len([c for c in creditos if c["congelado"]]),
	}


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
