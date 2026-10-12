# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

"""Instante T: fotografia de cada crédito tal como estava no fim do dia
`data_referencia` (ex.: 30-09-2026), não como está hoje.

Os campos `*_pago`/`*_perdoado`/`status` gravados no Plano De Amortizacao só
guardam o estado atual, por isso aqui o plano é reconstruído a partir do
histórico datado, ignorando tudo o que aconteceu depois da data:

- Pedidos considerados: os com Desembolso submetido com `data_de_desembolso`
  até à data.
- Pago: soma das Alocacao De Reembolso dos Reembolsos submetidos com
  `data_de_pagamento` até à data (por prestação e componente).
- Perdoado: Prestacao Perdoada dos Perdao De Multa submetidos com
  `data_perdao` até à data; `isento_de_multa` só a partir do primeiro perdão
  com `isentar_multa_futura`.
- Multa e Juros de Mora: recalculados para a data com as mesmas fórmulas de
  `atualizar_encargos_da_linha` - a Multa com `calcular_multa_acumulada`
  (cada dia sobre o capital+juros por pagar nesse dia, só com os pagamentos
  até à data), congelada na data do perdão se a prestação ficou isenta; o
  Juros de Mora (encargo único) sobre o capital+juros em atraso no primeiro
  dia de atraso. Nunca abaixo do que já foi pago/perdoado contra eles.
- Execucao De Garantia submetida com `data` até à data: o pedido conta como
  liquidado nessa data, tal como `marcar_como_liquidado`.

Estado na data: "Liquidado" se todas as prestações estavam pagas (ou houve
execução de garantia); "Incumprimento" se alguma prestação ultrapassou
`dias_para_incumprimento` ainda por pagar em algum dia até à data (é um
estado que a tarefa diária nunca desfaz); senão "Em Curso".

Saldo do Crédito / Dívida / Em Risco seguem `calcular_saldos`, e o estado de
cada prestação `atualizar_estado_da_linha`, aplicados às linhas reconstruídas.
"""

import frappe
from frappe import _
from frappe.utils import add_days, cint, date_diff, flt, getdate, nowdate

from entre_mc.entre_mc.doctype.mc_settings.mc_settings import get_settings
from entre_mc.utils.reembolso import atualizar_estado_da_linha, calcular_multa_acumulada, calcular_saldos

CAMPO_PAGO_POR_COMPONENTE = {
	"Juros de Mora": "juros_mora_pago",
	"Multa": "multa_paga",
	"Juros": "juros_pago",
	"Capital": "capital_pago",
}


def execute(filters=None):
	filters = filters or {}
	data_referencia = getdate(filters.get("data_referencia") or nowdate())
	por_prestacao = filters.get("vista") == "Por Prestação"

	columns = get_columns_por_prestacao() if por_prestacao else get_columns_por_credito()
	situacoes = get_situacoes(filters, data_referencia)

	if por_prestacao:
		data = [linha for situacao in situacoes for linha in _linhas_por_prestacao(situacao)]
	else:
		data = [_linha_por_credito(situacao) for situacao in situacoes]
		data.sort(key=lambda d: d["saldo_do_credito"], reverse=True)
	return columns, data


def get_columns_por_credito():
	return [
		{"label": _("Pedido"), "fieldname": "name", "fieldtype": "Link", "options": "Pedido De Credito", "width": 140},
		{"label": _("Cliente"), "fieldname": "cliente", "fieldtype": "Link", "options": "Cliente", "width": 160},
		{"label": _("Promotor"), "fieldname": "promotor_name", "fieldtype": "Data", "width": 140},
		{"label": _("Produto"), "fieldname": "produto", "fieldtype": "Link", "options": "Produto", "width": 130},
		{"label": _("Data de Desembolso"), "fieldname": "data_de_desembolso", "fieldtype": "Date", "width": 110},
		{
			"label": _("Capital Desembolsado"),
			"fieldname": "capital_desembolsado",
			"fieldtype": "Currency",
			"width": 140,
		},
		{"label": _("Estado na Data"), "fieldname": "estado", "fieldtype": "Data", "width": 120},
		{"label": _("Capital em Falta"), "fieldname": "capital_em_falta", "fieldtype": "Currency", "width": 130},
		{"label": _("Juros em Falta"), "fieldname": "juros_em_falta", "fieldtype": "Currency", "width": 120},
		{"label": _("Multa em Falta"), "fieldname": "multa_em_falta", "fieldtype": "Currency", "width": 120},
		{
			"label": _("Juros de Mora em Falta"),
			"fieldname": "juros_mora_em_falta",
			"fieldtype": "Currency",
			"width": 140,
		},
		{"label": _("Saldo do Crédito"), "fieldname": "saldo_do_credito", "fieldtype": "Currency", "width": 130},
		{"label": _("Dívida"), "fieldname": "divida", "fieldtype": "Currency", "width": 120},
		{"label": _("Capital em Dívida"), "fieldname": "capital_em_divida", "fieldtype": "Currency", "width": 130},
		{"label": _("Juros em Dívida"), "fieldname": "juros_em_divida", "fieldtype": "Currency", "width": 120},
		{"label": _("Em Risco"), "fieldname": "em_risco", "fieldtype": "Currency", "width": 120},
		{"label": _("Capital em Risco"), "fieldname": "capital_em_risco", "fieldtype": "Currency", "width": 130},
		{"label": _("Juros em Risco"), "fieldname": "juros_em_risco", "fieldtype": "Currency", "width": 120},
		{"label": _("Dias de Atraso"), "fieldname": "dias_atraso", "fieldtype": "Int", "width": 100},
		{"label": _("Prestações em Atraso"), "fieldname": "prestacoes_em_atraso", "fieldtype": "Int", "width": 120},
		{"label": _("Total Reembolsado"), "fieldname": "total_reembolsado", "fieldtype": "Currency", "width": 130},
		{
			"label": _("Data do Último Reembolso"),
			"fieldname": "data_ultimo_reembolso",
			"fieldtype": "Date",
			"width": 150,
		},
	]


def get_columns_por_prestacao():
	return [
		{"label": _("Pedido"), "fieldname": "pedido", "fieldtype": "Link", "options": "Pedido De Credito", "width": 140},
		{"label": _("Cliente"), "fieldname": "cliente", "fieldtype": "Link", "options": "Cliente", "width": 150},
		{"label": _("Nº"), "fieldname": "numero", "fieldtype": "Int", "width": 60},
		{"label": _("Data Limite"), "fieldname": "data_limite_pagamento", "fieldtype": "Date", "width": 100},
		{"label": _("Estado na Data"), "fieldname": "status", "fieldtype": "Data", "width": 110},
		{"label": _("Capital"), "fieldname": "capital_mensal", "fieldtype": "Currency", "width": 110},
		{"label": _("Capital Pago"), "fieldname": "capital_pago", "fieldtype": "Currency", "width": 110},
		{"label": _("Juros"), "fieldname": "juros_mensais", "fieldtype": "Currency", "width": 100},
		{"label": _("Juros Pago"), "fieldname": "juros_pago", "fieldtype": "Currency", "width": 100},
		{"label": _("Multa Aplicada"), "fieldname": "multa_aplicada", "fieldtype": "Currency", "width": 110},
		{"label": _("Multa Paga"), "fieldname": "multa_paga", "fieldtype": "Currency", "width": 100},
		{"label": _("Multa Perdoada"), "fieldname": "multa_perdoada", "fieldtype": "Currency", "width": 110},
		{"label": _("Juros de Mora"), "fieldname": "juros_mora_aplicado", "fieldtype": "Currency", "width": 110},
		{"label": _("Mora Paga"), "fieldname": "juros_mora_pago", "fieldtype": "Currency", "width": 100},
		{"label": _("Mora Perdoada"), "fieldname": "juros_mora_perdoado", "fieldtype": "Currency", "width": 110},
		{"label": _("Em Falta"), "fieldname": "em_falta", "fieldtype": "Currency", "width": 120},
		{"label": _("Dias de Atraso"), "fieldname": "dias_atraso", "fieldtype": "Int", "width": 100},
	]


def get_situacoes(filters, data_referencia):
	"""Um dict por pedido com o plano reconstruído para `data_referencia` e o
	estado nessa data, já filtrado por estado/liquidados."""
	settings = get_settings()

	desembolsos = {}
	for d in frappe.get_all(
		"Desembolso",
		filters={"docstatus": 1, "data_de_desembolso": ["<=", data_referencia]},
		fields=["pedido_de_credito", "data_de_desembolso", "valor_desembolsado"],
	):
		atual = desembolsos.setdefault(
			d.pedido_de_credito, frappe._dict(data_de_desembolso=d.data_de_desembolso, valor=0)
		)
		atual.data_de_desembolso = min(atual.data_de_desembolso, d.data_de_desembolso)
		atual.valor += flt(d.valor_desembolsado)
	if not desembolsos:
		return []

	query_filters = {"name": ["in", list(desembolsos)]}
	for campo in ("cliente", "produto", "promotor"):
		if filters.get(campo):
			query_filters[campo] = filters[campo]
	if filters.get("pedido_de_credito"):
		query_filters["name"] = filters["pedido_de_credito"]

	pedidos = frappe.get_all(
		"Pedido De Credito",
		filters=query_filters,
		fields=["name", "cliente", "promotor_name", "produto", "taxa_diaria_de_multa", "juros_de_mora"],
	)
	pedidos = [p for p in pedidos if p.name in desembolsos]
	if not pedidos:
		return []
	nomes = tuple(p.name for p in pedidos)

	linhas_por_pedido = {}
	for linha in frappe.get_all(
		"Plano De Amortizacao",
		filters={"parenttype": "Pedido De Credito", "parent": ["in", nomes]},
		fields=["parent", "numero", "data_limite_pagamento", "capital_mensal", "juros_mensais"],
		order_by="numero asc",
	):
		linhas_por_pedido.setdefault(linha.parent, []).append(linha)

	alocacoes = frappe.db.sql(
		"""
		select r.pedido_de_credito, r.data_de_pagamento, r.montante_pago, r.name as reembolso,
			a.prestacao, a.componente, a.valor
		from `tabAlocacao De Reembolso` a
		inner join `tabReembolso` r on r.name = a.parent and a.parenttype = 'Reembolso'
		where r.docstatus = 1 and r.data_de_pagamento <= %(data)s and r.pedido_de_credito in %(nomes)s
		""",
		{"data": data_referencia, "nomes": nomes},
		as_dict=True,
	)
	alocacoes_por_pedido = {}
	for a in alocacoes:
		alocacoes_por_pedido.setdefault(a.pedido_de_credito, []).append(a)

	perdoes = frappe.db.sql(
		"""
		select p.pedido_de_credito, p.data_perdao, p.isentar_multa_futura,
			i.numero, i.valor_perdoado_multa, i.valor_perdoado_mora
		from `tabPrestacao Perdoada` i
		inner join `tabPerdao De Multa` p on p.name = i.parent and i.parenttype = 'Perdao De Multa'
		where p.docstatus = 1 and p.data_perdao <= %(data)s and p.pedido_de_credito in %(nomes)s
		""",
		{"data": data_referencia, "nomes": nomes},
		as_dict=True,
	)
	perdoes_por_pedido = {}
	for p in perdoes:
		perdoes_por_pedido.setdefault(p.pedido_de_credito, []).append(p)

	execucoes = {}
	for e in frappe.get_all(
		"Execucao De Garantia",
		filters={"docstatus": 1, "data": ["<=", data_referencia], "pedido_de_credito": ["in", nomes]},
		fields=["pedido_de_credito", "data"],
	):
		atual = execucoes.get(e.pedido_de_credito)
		execucoes[e.pedido_de_credito] = min(atual, e.data) if atual else e.data

	situacoes = []
	for pedido in pedidos:
		situacao = _reconstruir_pedido(
			pedido,
			linhas_por_pedido.get(pedido.name, []),
			alocacoes_por_pedido.get(pedido.name, []),
			perdoes_por_pedido.get(pedido.name, []),
			execucoes.get(pedido.name),
			desembolsos[pedido.name],
			settings,
			data_referencia,
		)
		if filters.get("estado"):
			if situacao.estado != filters["estado"]:
				continue
		elif situacao.estado == "Liquidado" and not cint(filters.get("incluir_liquidados")):
			continue
		situacoes.append(situacao)
	return situacoes


def _reconstruir_pedido(pedido, linhas, alocacoes, perdoes, data_execucao, desembolso, settings, data_referencia):
	tolerancia = flt(settings.dias_de_tolerancia)

	# Pagamentos de capital+juros datados, por prestação - para saber o que
	# estava em atraso num dia anterior (base da Multa e do Juros de Mora).
	pagamentos_cj = {}
	pago = {}
	reembolsos = {}
	for a in alocacoes:
		campo = CAMPO_PAGO_POR_COMPONENTE.get(a.componente)
		if not campo:
			continue
		pago.setdefault(a.prestacao, {}).setdefault(campo, 0)
		pago[a.prestacao][campo] += flt(a.valor)
		if campo in ("capital_pago", "juros_pago"):
			pagamentos_cj.setdefault(a.prestacao, []).append((getdate(a.data_de_pagamento), flt(a.valor)))
		reembolsos[a.reembolso] = (getdate(a.data_de_pagamento), flt(a.montante_pago))

	perdoado = {}
	isento_desde = {}
	for p in perdoes:
		valores = perdoado.setdefault(p.numero, {"multa_perdoada": 0, "juros_mora_perdoado": 0})
		valores["multa_perdoada"] += flt(p.valor_perdoado_multa)
		valores["juros_mora_perdoado"] += flt(p.valor_perdoado_mora)
		if p.isentar_multa_futura and flt(p.valor_perdoado_multa) > 0:
			data_perdao = getdate(p.data_perdao)
			atual = isento_desde.get(p.numero)
			isento_desde[p.numero] = min(atual, data_perdao) if atual else data_perdao

	def cj_em_atraso_antes(linha, dia):
		"""Capital+juros da prestação ainda por pagar no início de `dia`."""
		pago_antes = sum(v for d, v in pagamentos_cj.get(linha.numero, []) if d < dia)
		return flt(flt(linha.capital_mensal) + flt(linha.juros_mensais) - pago_antes, 2)

	rows = []
	incumprimento = False
	for linha in linhas:
		row = frappe._dict(
			numero=linha.numero,
			data_limite_pagamento=linha.data_limite_pagamento,
			capital_mensal=flt(linha.capital_mensal),
			juros_mensais=flt(linha.juros_mensais),
			capital_pago=0,
			juros_pago=0,
			multa_paga=0,
			juros_mora_pago=0,
			multa_perdoada=0,
			juros_mora_perdoado=0,
			isento_de_multa=1 if linha.numero in isento_desde else 0,
		)
		row.update(pago.get(linha.numero, {}))
		row.update(perdoado.get(linha.numero, {}))

		dias_atraso = date_diff(data_referencia, linha.data_limite_pagamento) - tolerancia
		base_multa = flt(row.multa_paga) + flt(row.multa_perdoada)
		base_mora = flt(row.juros_mora_pago) + flt(row.juros_mora_perdoado)
		multa = mora = 0

		if dias_atraso > 0:
			_dias, multa = calcular_multa_acumulada(
				linha,
				pedido.taxa_diaria_de_multa,
				settings,
				min(data_referencia, isento_desde.get(linha.numero) or data_referencia),
				pagamentos=pagamentos_cj.get(linha.numero, []),
			)
		if dias_atraso > 0 and flt(pedido.juros_de_mora):
			inicio_atraso = getdate(add_days(linha.data_limite_pagamento, int(tolerancia) + 1))
			mora = flt(pedido.juros_de_mora) / 100 * cj_em_atraso_antes(linha, inicio_atraso)

		row.multa_aplicada = flt(max(multa, base_multa), 2)
		row.juros_mora_aplicado = flt(max(mora, base_mora), 2)

		if data_execucao:
			# Dação em pagamento - mesma baixa que Pedido De Credito.marcar_como_liquidado.
			row.capital_pago = row.capital_mensal
			row.juros_pago = row.juros_mensais
			row.multa_paga = row.multa_aplicada
			row.juros_mora_pago = row.juros_mora_aplicado

		atualizar_estado_da_linha(row, data_referencia, settings)
		row.em_falta = _em_falta(row)
		row.dias_atraso = max(dias_atraso, 0) if row.em_falta > 0 else 0

		# Incumprimento é pegajoso: basta a prestação ter estado por pagar no dia
		# em que ultrapassou `dias_para_incumprimento`, mesmo que paga depois.
		if cint(settings.dias_para_incumprimento):
			dia_incumprimento = getdate(
				add_days(linha.data_limite_pagamento, int(tolerancia) + cint(settings.dias_para_incumprimento) + 1)
			)
			if dia_incumprimento <= data_referencia and cj_em_atraso_antes(linha, dia_incumprimento) > 0:
				incumprimento = True

		rows.append(row)

	saldo, divida, em_risco = calcular_saldos(rows, settings, data_referencia)
	if data_execucao or (rows and all(row.status == "Pago" for row in rows)):
		estado = "Liquidado"
	elif incumprimento:
		estado = "Incumprimento"
	else:
		estado = "Em Curso"

	return frappe._dict(
		pedido=pedido,
		desembolso=desembolso,
		rows=rows,
		estado=estado,
		saldo_do_credito=saldo,
		divida=divida,
		em_risco=em_risco,
		total_reembolsado=flt(sum(v for _d, v in reembolsos.values())),
		data_ultimo_reembolso=max((d for d, _v in reembolsos.values()), default=None),
	)


def _em_falta(row):
	return flt(
		(flt(row.capital_mensal) - flt(row.capital_pago))
		+ (flt(row.juros_mensais) - flt(row.juros_pago))
		+ (flt(row.multa_aplicada) - flt(row.multa_paga) - flt(row.multa_perdoada))
		+ (flt(row.juros_mora_aplicado) - flt(row.juros_mora_pago) - flt(row.juros_mora_perdoado)),
		2,
	)


def _linha_por_credito(situacao):
	pedido = situacao.pedido
	rows = situacao.rows

	# Capital/Juros de Dívida e Em Risco com a mesma regra de `calcular_saldos`:
	# Dívida = prestações em atraso; Em Risco = Dívida + a próxima prestação
	# ainda não vencida (só se houver Dívida e essa prestação existir).
	em_atraso = [r for r in rows if r.dias_atraso > 0]
	por_vencer = [r for r in rows if r.em_falta > 0 and r.dias_atraso <= 0]
	proxima = min(por_vencer, key=lambda r: r.numero) if por_vencer else None
	capital_em_divida = flt(sum(r.capital_mensal - flt(r.capital_pago) for r in em_atraso))
	juros_em_divida = flt(sum(r.juros_mensais - flt(r.juros_pago) for r in em_atraso))
	em_risco = situacao.divida and proxima
	capital_em_risco = flt(capital_em_divida + proxima.capital_mensal - flt(proxima.capital_pago)) if em_risco else 0
	juros_em_risco = flt(juros_em_divida + proxima.juros_mensais - flt(proxima.juros_pago)) if em_risco else 0
	return {
		"name": pedido.name,
		"cliente": pedido.cliente,
		"promotor_name": pedido.promotor_name,
		"produto": pedido.produto,
		"data_de_desembolso": situacao.desembolso.data_de_desembolso,
		"capital_desembolsado": situacao.desembolso.valor,
		"estado": _(situacao.estado),
		"capital_em_falta": flt(sum(r.capital_mensal - flt(r.capital_pago) for r in rows)),
		"juros_em_falta": flt(sum(r.juros_mensais - flt(r.juros_pago) for r in rows)),
		"multa_em_falta": flt(sum(r.multa_aplicada - flt(r.multa_paga) - flt(r.multa_perdoada) for r in rows)),
		"juros_mora_em_falta": flt(
			sum(r.juros_mora_aplicado - flt(r.juros_mora_pago) - flt(r.juros_mora_perdoado) for r in rows)
		),
		"saldo_do_credito": situacao.saldo_do_credito,
		"divida": situacao.divida,
		"capital_em_divida": capital_em_divida,
		"juros_em_divida": juros_em_divida,
		"em_risco": situacao.em_risco,
		"capital_em_risco": capital_em_risco,
		"juros_em_risco": juros_em_risco,
		"dias_atraso": max((r.dias_atraso for r in rows), default=0),
		"prestacoes_em_atraso": len(em_atraso),
		"total_reembolsado": situacao.total_reembolsado,
		"data_ultimo_reembolso": situacao.data_ultimo_reembolso,
	}


def _linhas_por_prestacao(situacao):
	return [
		dict(row, pedido=situacao.pedido.name, cliente=situacao.pedido.cliente, status=_(row.status))
		for row in situacao.rows
	]
