# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

"""Motor de alocação de reembolsos.

Aplica um pagamento às prestações em aberto do Plano De Amortizacao, seguindo
obrigatoriamente a ordem de liquidação definida na especificação:

- Sem multa nem juros de mora: Juros -> Capital
- Apenas multa: Multa -> Juros -> Capital
- Multa e juros de mora: Juros de Mora -> Multa -> Juros -> Capital
- Apenas juros de mora: Juros de Mora -> Juros -> Capital

Multa e Juros de Mora são recalculados com base nos dias de atraso até à data em
questão - tanto aqui (no momento de um pagamento) como na tarefa diária
`entre_mc.tasks.atualizar_atrasos`, que mantém o estado "Atrasado" e os
encargos acumulados visíveis mesmo sem nenhum pagamento ser registado.
"""

import frappe
from frappe import _
from frappe.utils import date_diff, flt, getdate

COMPONENTES = ("juros_mora", "multa", "juros", "capital")
COMPONENTE_LABEL = {
	"juros_mora": "Juros de Mora",
	"multa": "Multa",
	"juros": "Juros",
	"capital": "Capital",
}


def aplicar_alocacao(rows, produto_doc, settings, montante_pago, data_pagamento):
	"""Muta `rows` (linhas do Plano De Amortizacao, ordenadas por número) in place.

	Devolve a lista de alocações efetuadas: [{"prestacao": n, "componente": x, "valor": v}, ...]
	Lança frappe.ValidationError se o montante pago exceder o total em dívida.
	"""
	precision = 2
	data_pagamento = getdate(data_pagamento)
	restante = flt(montante_pago, precision)
	alocacoes = []

	for row in sorted(rows, key=lambda r: r.numero):
		if restante <= 0:
			break
		if row.status == "Pago":
			continue

		atualizar_encargos_da_linha(row, produto_doc, settings, data_pagamento, precision)

		devido = {
			"juros_mora": flt(row.juros_mora_aplicado - row.juros_mora_pago, precision),
			"multa": flt(row.multa_aplicada - row.multa_paga, precision),
			"juros": flt(row.juros_mensais - row.juros_pago, precision),
			"capital": flt(row.capital_mensal - row.capital_pago, precision),
		}
		ordem = _ordem_de_liquidacao(devido["multa"] > 0, devido["juros_mora"] > 0)

		for componente in ordem:
			if restante <= 0:
				break
			valor_devido = devido[componente]
			if valor_devido <= 0:
				continue
			valor_a_pagar = flt(min(restante, valor_devido), precision)
			if valor_a_pagar <= 0:
				continue

			_registar_pagamento(row, componente, valor_a_pagar)
			alocacoes.append(
				{
					"prestacao": row.numero,
					"componente": COMPONENTE_LABEL[componente],
					"valor": valor_a_pagar,
				}
			)
			restante = flt(restante - valor_a_pagar, precision)

		atualizar_estado_da_linha(row, data_pagamento, settings)

	if restante > 0:
		frappe.throw(
			_(
				"O montante pago excede o total em dívida em {0}. "
				"Reveja o valor ou registe primeiro as prestações em falta."
			).format(restante)
		)

	return alocacoes


def atualizar_encargos_da_linha(row, produto_doc, settings, data_pagamento, precision):
	dias_atraso = date_diff(data_pagamento, row.data_limite_pagamento) - flt(settings.dias_de_tolerancia)
	if dias_atraso <= 0:
		return

	capital_em_atraso = flt(row.capital_mensal - row.capital_pago, precision)
	prestacao_em_atraso = flt(
		(row.capital_mensal - row.capital_pago) + (row.juros_mensais - row.juros_pago), precision
	)

	if produto_doc.taxa_diaria_de_multa:
		row.multa_aplicada = flt(
			flt(produto_doc.taxa_diaria_de_multa) / 100 * dias_atraso * prestacao_em_atraso, precision
		)
	if produto_doc.juros_de_mora:
		row.juros_mora_aplicado = flt(
			flt(produto_doc.juros_de_mora) / 100 * capital_em_atraso * dias_atraso / 30, precision
		)


def _ordem_de_liquidacao(tem_multa, tem_mora):
	if tem_mora and tem_multa:
		return ("juros_mora", "multa", "juros", "capital")
	if tem_mora:
		return ("juros_mora", "juros", "capital")
	if tem_multa:
		return ("multa", "juros", "capital")
	return ("juros", "capital")


def _registar_pagamento(row, componente, valor):
	campo_pago = {
		"juros_mora": "juros_mora_pago",
		"multa": "multa_paga",
		"juros": "juros_pago",
		"capital": "capital_pago",
	}[componente]
	row.set(campo_pago, flt(row.get(campo_pago)) + valor)


def atualizar_estado_da_linha(row, data_pagamento, settings):
	capital_quitado = flt(row.capital_pago) >= flt(row.capital_mensal)
	juros_quitado = flt(row.juros_pago) >= flt(row.juros_mensais)
	multa_quitada = flt(row.multa_paga) >= flt(row.multa_aplicada)
	mora_quitada = flt(row.juros_mora_pago) >= flt(row.juros_mora_aplicado)

	if capital_quitado and juros_quitado and multa_quitada and mora_quitada:
		row.status = "Pago"
	elif row.capital_pago or row.juros_pago or row.multa_paga or row.juros_mora_pago:
		row.status = "Pago Parcial"
	else:
		dias_atraso = date_diff(getdate(data_pagamento), row.data_limite_pagamento) - flt(
			settings.dias_de_tolerancia
		)
		row.status = "Atrasado" if dias_atraso > 0 else "Pendente"
