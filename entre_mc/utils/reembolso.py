# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

"""Motor de alocação de reembolsos.

Aplica um pagamento às prestações em aberto do Plano De Amortizacao, seguindo
obrigatoriamente a ordem de liquidação definida na especificação:

- Sem multa nem juros de mora: Juros -> Capital
- Apenas multa: Multa -> Juros -> Capital
- Multa e juros de mora: Juros de Mora -> Multa -> Juros -> Capital
- Apenas juros de mora: Juros de Mora -> Juros -> Capital

Multa é recalculada com base nos dias de atraso até à data em questão - tanto
aqui (no momento de um pagamento) como na tarefa diária
`entre_mc.tasks.atualizar_atrasos`, que mantém o estado "Atrasado" e os
encargos acumulados visíveis mesmo sem nenhum pagamento ser registado.

Juros de Mora, ao contrário da Multa, é um encargo único: aplicado uma só vez
quando a prestação entra em atraso (Juros de Mora % × capital+juros em atraso
nesse momento) e nunca recalculado depois disso, mesmo que o atraso continue
ou a prestação seja paga parcialmente.
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


def aplicar_alocacao(rows, taxa_diaria_de_multa, juros_de_mora, settings, montante_pago, data_pagamento):
	"""Muta `rows` (linhas do Plano De Amortizacao, ordenadas por número) in place.

	`taxa_diaria_de_multa` e `juros_de_mora` devem vir do Pedido de Crédito (herdadas do
	Produto no momento da criação do pedido), não do Produto ao vivo - assim, alterar as
	taxas de um Produto não reescreve retroativamente os encargos de pedidos já criados.

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

		atualizar_encargos_da_linha(row, taxa_diaria_de_multa, juros_de_mora, settings, data_pagamento, precision)

		devido = {
			"juros_mora": flt(flt(row.juros_mora_aplicado) - flt(row.juros_mora_pago), precision),
			"multa": flt(flt(row.multa_aplicada) - flt(row.multa_paga), precision),
			"juros": flt(flt(row.juros_mensais) - flt(row.juros_pago), precision),
			"capital": flt(flt(row.capital_mensal) - flt(row.capital_pago), precision),
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


def calcular_saldos(rows, settings, hoje):
	"""A partir das linhas (não pagas ou não) de um Plano De Amortizacao, devolve
	`(saldo_do_credito, divida, em_risco)`:

	- `saldo_do_credito`: tudo o que ainda falta pagar (capital + juros + multa +
	  mora), vencido ou não - é o saldo normal do crédito em curso, não uma dívida.
	- `divida`: só a parte de prestações já em atraso (data_limite_pagamento + a
	  tolerância já ultrapassada) - o termo "dívida" só se aplica aqui, nunca ao
	  saldo do crédito ainda dentro do prazo.
	- `em_risco`: `divida` + a próxima prestação ainda não vencida (0 se não houver
	  nenhuma prestação em atraso) - um cliente já atrasado numa prestação tende a
	  atrasar-se também na seguinte, por isso essa é a soma que compõe a "Carteira
	  em Risco".

	Usa `data_limite_pagamento`/`dias_de_tolerancia` para decidir o que está em
	atraso, nunca o `status` gravado na linha - esse só é atualizado pela tarefa
	diária `atualizar_atrasos` ou por um Reembolso submetido, por isso não pode
	ser a fonte de verdade aqui (ver Creditos em Atraso, que tinha o mesmo problema).
	"""
	hoje = getdate(hoje)
	saldo_do_credito = 0
	divida = 0
	proxima_numero = None
	proxima_valor = 0

	for row in rows:
		valor_em_falta = flt(
			(flt(row.capital_mensal) - flt(row.capital_pago))
			+ (flt(row.juros_mensais) - flt(row.juros_pago))
			+ (flt(row.multa_aplicada) - flt(row.multa_paga))
			+ (flt(row.juros_mora_aplicado) - flt(row.juros_mora_pago))
		)
		if valor_em_falta <= 0:
			continue
		saldo_do_credito += valor_em_falta

		dias_atraso = date_diff(hoje, row.data_limite_pagamento) - flt(settings.dias_de_tolerancia)
		if dias_atraso > 0:
			divida += valor_em_falta
		elif proxima_numero is None or row.numero < proxima_numero:
			proxima_numero = row.numero
			proxima_valor = valor_em_falta

	em_risco = flt(divida + proxima_valor) if divida and proxima_numero is not None else 0
	return flt(saldo_do_credito), flt(divida), em_risco


def atualizar_encargos_da_linha(row, taxa_diaria_de_multa, juros_de_mora, settings, data_pagamento, precision):
	dias_atraso = date_diff(data_pagamento, row.data_limite_pagamento) - flt(settings.dias_de_tolerancia)
	if dias_atraso <= 0:
		return

	prestacao_em_atraso = flt(
		(flt(row.capital_mensal) - flt(row.capital_pago)) + (flt(row.juros_mensais) - flt(row.juros_pago)),
		precision,
	)

	if taxa_diaria_de_multa:
		row.multa_aplicada = flt(
			flt(taxa_diaria_de_multa) / 100 * dias_atraso * prestacao_em_atraso, precision
		)
	if juros_de_mora and not row.juros_mora_aplicado:
		# Encargo único: aplicado uma só vez quando a prestação entra em atraso,
		# não volta a ser recalculado nos dias seguintes nem escala com dias_atraso.
		row.juros_mora_aplicado = flt(flt(juros_de_mora) / 100 * prestacao_em_atraso, precision)


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
