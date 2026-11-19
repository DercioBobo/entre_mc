# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

"""Ficha do Crédito: tudo sobre um Pedido De Credito numa só página - as
condições, quanto falta pagar e de quê, o plano prestação a prestação e a
cronologia de tudo o que lhe aconteceu.

A situação é a de uma data à escolha (por omissão, hoje), reconstruída pelo
relatório Instante T a partir dos documentos datados (Desembolso, Reembolsos,
Perdões, Congelamentos, Execução de Garantia) - não a que está gravada no
Pedido. Assim pode ver-se como o crédito estava em qualquer dia do passado e,
com uma data futura, como ficará se o cliente não pagar mais nada.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

from entre_mc.entre_mc.report.instante_t.instante_t import get_situacoes
from entre_mc.utils.reembolso import ESTADOS_FECHADOS

COMPONENTES = (
	("Capital", "capital"),
	("Juros", "juros"),
	("Multa", "multa"),
	("Juros de Mora", "mora"),
)


@frappe.whitelist()
def obter_ficha(pedido_de_credito, data=None):
	frappe.has_permission("Pedido De Credito", "read", doc=pedido_de_credito, throw=True)

	hoje = getdate(nowdate())
	data = getdate(data) if data else hoje
	pedido = frappe.get_doc("Pedido De Credito", pedido_de_credito)

	ficha = {
		"data": data,
		"hoje": hoje,
		"projecao": data > hoje,
		"pedido": _condicoes(pedido),
		"situacao": None,
		"plano": [],
		"cronologia": [],
	}

	situacoes = get_situacoes({"pedido_de_credito": pedido.name, "incluir_liquidados": 1}, data)
	if not situacoes:
		# Ainda não desembolsado nesta data.
		return ficha

	situacao = situacoes[0]
	ficha["situacao"] = _resumo(situacao, pedido, data, hoje)
	ficha["plano"] = [_linha_do_plano(row) for row in situacao.rows]
	ficha["cronologia"] = _cronologia(pedido, situacao, data)
	return ficha


@frappe.whitelist()
def obter_historico(pedido_de_credito):
	"""Para o formulário do Pedido De Credito: a mesma cronologia da Ficha (até
	hoje) e os planos que cada Reestruturação submetida substituiu, do mais
	recente para o mais antigo."""
	frappe.has_permission("Pedido De Credito", "read", doc=pedido_de_credito, throw=True)

	hoje = getdate(nowdate())
	pedido = frappe.get_doc("Pedido De Credito", pedido_de_credito)

	cronologia = []
	situacoes = get_situacoes({"pedido_de_credito": pedido.name, "incluir_liquidados": 1}, hoje)
	if situacoes:
		cronologia = _cronologia(pedido, situacoes[0], hoje)

	planos_anteriores = []
	for rest in frappe.get_all(
		"Reestruturacao De Credito",
		filters={"pedido_de_credito": pedido.name, "docstatus": 1},
		fields=["name", "data_da_reestruturacao", "motivo"],
		order_by="data_da_reestruturacao desc, creation desc",
	):
		doc = frappe.get_doc("Reestruturacao De Credito", rest.name)
		planos_anteriores.append(
			{
				"name": rest.name,
				"data": rest.data_da_reestruturacao,
				"motivo": rest.motivo,
				"rows": [row.as_dict() for row in sorted(doc.plano_anterior, key=lambda r: r.numero)],
			}
		)

	return {"cronologia": cronologia, "planos_anteriores": planos_anteriores}


def _condicoes(pedido):
	return {
		"name": pedido.name,
		"cliente": pedido.cliente,
		"produto": pedido.produto,
		"promotor": pedido.promotor_name,
		"finalidade": pedido.finalidade,
		"capital_solicitado": flt(pedido.capital_solicitado),
		"taxa_de_juros": flt(pedido.taxa_de_juros),
		"taxa_diaria_de_multa": flt(pedido.taxa_diaria_de_multa),
		"juros_de_mora": flt(pedido.juros_de_mora),
		"prazo": pedido.prazo,
		"frequencia": pedido.frequencia,
		"status": pedido.status,
		"workflow_state": pedido.workflow_state,
		"garantias": [row.garantia for row in pedido.garantias],
	}


def _resumo(situacao, pedido, data, hoje):
	rows = situacao.rows
	em_falta = {
		"capital": sum(r.capital_mensal - flt(r.capital_pago) for r in rows),
		"juros": sum(r.juros_mensais - flt(r.juros_pago) for r in rows),
		"multa": sum(r.multa_aplicada - flt(r.multa_paga) - flt(r.multa_perdoada) for r in rows),
		"mora": sum(r.juros_mora_aplicado - flt(r.juros_mora_pago) - flt(r.juros_mora_perdoado) for r in rows),
	}
	pago = {
		"capital": sum(flt(r.capital_pago) for r in rows),
		"juros": sum(flt(r.juros_pago) for r in rows),
		"multa": sum(flt(r.multa_paga) for r in rows),
		"mora": sum(flt(r.juros_mora_pago) for r in rows),
	}
	por_pagar = [r for r in rows if r.em_falta > 0]
	proxima = min(por_pagar, key=lambda r: r.numero) if por_pagar else None

	congelado_em = frappe.db.sql(
		"""
		select max(data_do_congelamento) from `tabCongelamento De Divida`
		where docstatus = 1 and pedido_de_credito = %s and data_do_congelamento <= %s
			and (data_do_descongelamento is null or data_do_descongelamento > %s)
		""",
		(pedido.name, data, data),
	)[0][0]

	return {
		"estado": situacao.estado,
		"data_de_desembolso": situacao.desembolso.data_de_desembolso,
		"valor_desembolsado": flt(situacao.desembolso.valor),
		"saldo_do_credito": flt(situacao.saldo_do_credito),
		"divida": flt(situacao.divida),
		"em_risco": flt(situacao.em_risco),
		"em_falta": {k: flt(v, 2) for k, v in em_falta.items()},
		"pago": {k: flt(v, 2) for k, v in pago.items()},
		"total_contratado": flt(sum(r.capital_mensal + r.juros_mensais for r in rows), 2),
		"multa_perdoada": flt(sum(flt(r.multa_perdoada) for r in rows), 2),
		"mora_perdoada": flt(sum(flt(r.juros_mora_perdoado) for r in rows), 2),
		"total_reembolsado": flt(situacao.total_reembolsado),
		"data_ultimo_reembolso": situacao.data_ultimo_reembolso,
		"dias_atraso": max((r.dias_atraso for r in rows), default=0),
		"prestacoes": len(rows),
		"prestacoes_pagas": len([r for r in rows if r.status in ESTADOS_FECHADOS]),
		"prestacoes_em_atraso": len([r for r in rows if r.dias_atraso > 0]),
		"proxima": {
			"numero": proxima.numero,
			"data_limite_pagamento": proxima.data_limite_pagamento,
			"em_falta": proxima.em_falta,
			"dias_atraso": proxima.dias_atraso,
		}
		if proxima
		else None,
		"ultimo_vencimento": max((r.data_limite_pagamento for r in rows), default=None),
		"congelado_em": congelado_em,
		"reestruturado": bool(
			frappe.db.exists(
				"Reestruturacao De Credito",
				{"pedido_de_credito": pedido.name, "docstatus": 1, "data_da_reestruturacao": ["<=", data]},
			)
		),
	}


def _linha_do_plano(row):
	return {
		"numero": row.numero,
		"data_limite_pagamento": row.data_limite_pagamento,
		"status": row.status,
		"capital_mensal": flt(row.capital_mensal),
		"juros_mensais": flt(row.juros_mensais),
		"pago": flt(
			flt(row.capital_pago) + flt(row.juros_pago) + flt(row.multa_paga) + flt(row.juros_mora_pago), 2
		),
		"multa_aplicada": flt(row.multa_aplicada),
		"juros_mora_aplicado": flt(row.juros_mora_aplicado),
		"perdoado": flt(flt(row.multa_perdoada) + flt(row.juros_mora_perdoado), 2),
		"em_falta": flt(row.em_falta),
		"dias_atraso": row.dias_atraso,
	}


def _cronologia(pedido, situacao, data):
	"""Tudo o que aconteceu ao crédito até `data`, do mais recente para o mais
	antigo. `sentido`: "entrada" (dinheiro recebido), "saida" (dinheiro
	entregue), "alivio" (perdão/acordo a favor do cliente), "alerta" ou "info"."""
	eventos = []

	def evento(dia, tipo, titulo, detalhe="", valor=None, sentido="info", doctype=None, name=None):
		eventos.append(
			{
				"data": getdate(dia),
				"tipo": tipo,
				"titulo": titulo,
				"detalhe": detalhe,
				"valor": valor,
				"sentido": sentido,
				"doctype": doctype,
				"name": name,
			}
		)

	filtro = {"pedido_de_credito": pedido.name, "docstatus": 1}

	for d in frappe.get_all(
		"Desembolso",
		filters={**filtro, "data_de_desembolso": ["<=", data]},
		fields=["name", "data_de_desembolso", "valor_desembolsado", "taxa_administrativa", "forma_de_pagamento"],
	):
		detalhe = _("Crédito concedido: {0}. Taxa administrativa: {1}.").format(
			_moeda(pedido.capital_solicitado), _moeda(d.taxa_administrativa)
		)
		if d.forma_de_pagamento:
			detalhe += " " + _("Forma de pagamento: {0}.").format(d.forma_de_pagamento)
		evento(d.data_de_desembolso, "Desembolso", _("Desembolso"), detalhe, d.valor_desembolsado, "saida", "Desembolso", d.name)

	reembolsos = frappe.get_all(
		"Reembolso",
		filters={**filtro, "data_de_pagamento": ["<=", data]},
		fields=["name", "data_de_pagamento", "montante_pago", "referencia_da_transacao"],
	)
	alocacoes = {}
	if reembolsos:
		for a in frappe.get_all(
			"Alocacao De Reembolso",
			filters={"parenttype": "Reembolso", "parent": ["in", [r.name for r in reembolsos]]},
			fields=["parent", "prestacao", "componente", "valor"],
		):
			alocacoes.setdefault(a.parent, []).append(a)
	for r in reembolsos:
		linhas = alocacoes.get(r.name, [])
		partes = []
		for rotulo, _chave in COMPONENTES:
			total = sum(flt(a.valor) for a in linhas if a.componente == rotulo)
			if total:
				partes.append(f"{_(rotulo)} {_moeda(total)}")
		prestacoes = sorted({a.prestacao for a in linhas})
		detalhe = ""
		if prestacoes:
			detalhe = _("Prestação {0}").format(", ".join(str(n) for n in prestacoes)) + ": " + " · ".join(partes)
		if r.referencia_da_transacao:
			detalhe += " " + _("(ref. {0})").format(r.referencia_da_transacao)
		evento(r.data_de_pagamento, "Reembolso", _("Reembolso"), detalhe, r.montante_pago, "entrada", "Reembolso", r.name)

	for p in frappe.get_all(
		"Perdao De Multa",
		filters={**filtro, "data_perdao": ["<=", data]},
		fields=["name", "data_perdao", "total_perdoado", "motivo", "isentar_multa_futura"],
	):
		detalhe = p.motivo or ""
		if p.isentar_multa_futura:
			detalhe += " " + _("Prestações isentas de multa futura.")
		evento(p.data_perdao, "Perdão", _("Perdão de Multa"), detalhe, p.total_perdoado, "alivio", "Perdao De Multa", p.name)

	for c in frappe.get_all(
		"Congelamento De Divida",
		filters={**filtro, "data_do_congelamento": ["<=", data]},
		fields=[
			"name",
			"data_do_congelamento",
			"valor_congelado",
			"motivo",
			"data_do_descongelamento",
			"motivo_do_descongelamento",
		],
	):
		evento(
			c.data_do_congelamento,
			"Congelamento",
			_("Dívida congelada"),
			_("Deixa de gerar Multa e Juros de Mora.") + " " + (c.motivo or ""),
			c.valor_congelado,
			"alivio",
			"Congelamento De Divida",
			c.name,
		)
		if c.data_do_descongelamento and getdate(c.data_do_descongelamento) <= data:
			evento(
				c.data_do_descongelamento,
				"Congelamento",
				_("Dívida descongelada"),
				_("A Multa volta a contar a partir deste dia.") + " " + (c.motivo_do_descongelamento or ""),
				None,
				"alerta",
				"Congelamento De Divida",
				c.name,
			)

	for r in frappe.get_all(
		"Reestruturacao De Credito",
		filters={**filtro, "data_da_reestruturacao": ["<=", data]},
		fields=[
			"name",
			"data_da_reestruturacao",
			"saldo_total",
			"valor_a_reestruturar",
			"novo_prazo",
			"nova_taxa_de_juros",
			"nova_frequencia",
			"motivo",
		],
	):
		evento(
			r.data_da_reestruturacao,
			"Reestruturação",
			_("Crédito reestruturado"),
			_("Saldo em aberto {0} passou a novo plano: {1} meses, {2}% de juros, {3}.").format(
				_moeda(r.saldo_total), r.novo_prazo, flt(r.nova_taxa_de_juros), r.nova_frequencia or ""
			)
			+ " "
			+ (r.motivo or ""),
			r.valor_a_reestruturar,
			"info",
			"Reestruturacao De Credito",
			r.name,
		)

	for s in frappe.get_all(
		"Substituicao De Garantia",
		filters={**filtro, "data_da_substituicao": ["<=", data]},
		fields=["name", "data_da_substituicao", "garantia_atual", "garantia_nova", "destino_da_garantia_antiga", "motivo"],
	):
		evento(
			s.data_da_substituicao,
			"Garantia",
			_("Garantia substituída"),
			_("{0} substituída por {1} ({2}).").format(s.garantia_atual, s.garantia_nova, s.destino_da_garantia_antiga)
			+ " "
			+ (s.motivo or ""),
			None,
			"info",
			"Substituicao De Garantia",
			s.name,
		)

	for e in frappe.get_all(
		"Execucao De Garantia",
		filters={**filtro, "data": ["<=", data]},
		fields=["name", "data", "garantia", "valor_liquidado"],
	):
		evento(
			e.data,
			"Garantia",
			_("Garantia executada"),
			_("Dação em pagamento da garantia {0}: o crédito fica liquidado.").format(e.garantia),
			e.valor_liquidado,
			"alerta",
			"Execucao De Garantia",
			e.name,
		)

	for d in frappe.get_all(
		"Devolucao Da Garantia",
		filters={**filtro, "data_de_devolucao": ["<=", data]},
		fields=["name", "data_de_devolucao", "garantia"],
	):
		evento(
			d.data_de_devolucao,
			"Garantia",
			_("Garantia devolvida"),
			_("Garantia {0} devolvida ao cliente.").format(d.garantia),
			None,
			"info",
			"Devolucao Da Garantia",
			d.name,
		)

	for row in situacao.rows:
		if getdate(row.data_limite_pagamento) > data:
			continue
		valor = flt(row.capital_mensal + row.juros_mensais, 2)
		if row.status == "Pago":
			detalhe, sentido = _("Paga."), "info"
		elif row.status == "Reestruturado":
			detalhe, sentido = _("Fechada pela Reestruturação - o que faltava passou para o novo plano."), "info"
		elif row.dias_atraso > 0:
			detalhe = _("Em atraso há {0} dias - faltam {1}.").format(row.dias_atraso, _moeda(row.em_falta))
			sentido = "alerta"
		else:
			detalhe, sentido = _("Por pagar, ainda dentro da tolerância."), "info"
		evento(
			row.data_limite_pagamento,
			"Vencimento",
			_("Venceu a prestação {0}").format(row.numero),
			detalhe,
			valor,
			sentido,
		)

	# Prestações que uma Reestruturação tirou do plano (sem qualquer pagamento
	# ou perdão - ver reestruturacao_de_credito._fica_no_plano) já não estão em
	# `situacao.rows`; vêm do `plano_anterior` dela. As que ficaram (numero <=
	# ultima_prestacao_mantida) já aparecem acima, por isso não se repetem.
	for rest in frappe.get_all(
		"Reestruturacao De Credito",
		filters={**filtro, "data_da_reestruturacao": ["<=", data]},
		fields=["name", "data_da_reestruturacao", "ultima_prestacao_mantida"],
	):
		limite = int(rest.ultima_prestacao_mantida or 0)
		for row in frappe.get_all(
			"Plano De Amortizacao",
			filters={
				"parenttype": "Reestruturacao De Credito",
				"parent": rest.name,
				"parentfield": "plano_anterior",
				"numero": [">", limite],
				"data_limite_pagamento": ["<=", min(data, getdate(rest.data_da_reestruturacao))],
			},
			fields=["numero", "data_limite_pagamento", "capital_mensal", "juros_mensais"],
		):
			atraso = (getdate(rest.data_da_reestruturacao) - getdate(row.data_limite_pagamento)).days
			evento(
				row.data_limite_pagamento,
				"Vencimento",
				_("Venceu a prestação {0} (plano anterior)").format(row.numero),
				_("Não foi paga - {0} dias depois passou para o novo plano na {1}.").format(atraso, rest.name),
				flt(flt(row.capital_mensal) + flt(row.juros_mensais), 2),
				"alerta",
				"Reestruturacao De Credito",
				rest.name,
			)

	# Mais recente primeiro; no mesmo dia, o vencimento fica antes (abaixo) do
	# que aconteceu nesse dia.
	eventos.sort(key=lambda e: (e["data"], e["tipo"] != "Vencimento"), reverse=True)
	return eventos


def _moeda(valor):
	return frappe.format(flt(valor), {"fieldtype": "Currency"})
