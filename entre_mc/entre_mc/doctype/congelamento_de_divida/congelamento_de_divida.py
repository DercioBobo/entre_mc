# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

"""Congelamento da dívida de um Pedido De Credito, na sequência de um acordo
com o cliente sobre um valor fixo.

Ao submeter, a Multa e o Juros de Mora são calculados uma última vez para a
Data do Congelamento e o crédito deixa de gerar novos encargos: todas as
prestações ficam marcadas `encargos_congelados`, e
`entre_mc.utils.reembolso.atualizar_encargos_da_linha` (usado pela tarefa
diária, pelos Reembolsos e pelos relatórios) não lhes volta a tocar. O valor
congelado fica gravado aqui, decomposto em Capital, Juros, Multa e Juros de
Mora. Para acordar um valor inferior, registar primeiro um Perdao De Multa.

O estado das prestações ("Atrasado" etc.) e o Incumprimento continuam a ser
atualizados normalmente - só os encargos param.

Cancelar descongela: os encargos voltam a ser calculados como se o
congelamento nunca tivesse existido (incluindo os dias em que esteve
congelado).
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, nowdate

from entre_mc.entre_mc.doctype.mc_settings.mc_settings import get_settings
from entre_mc.utils.reembolso import atualizar_encargos_da_linha, atualizar_estado_da_linha, decompor_saldos

ESTADOS_ATIVOS = ("Em Curso", "Incumprimento")


class CongelamentoDeDivida(Document):
	def validate(self):
		pedido = frappe.get_doc("Pedido De Credito", self.pedido_de_credito, for_update=True)
		if pedido.status not in ESTADOS_ATIVOS:
			frappe.throw(
				_("Só é possível congelar a dívida de um crédito em curso ou em incumprimento ({0}: {1}).").format(
					pedido.name, pedido.status or _("não desembolsado")
				)
			)
		if pedido.congelado:
			frappe.throw(_("A dívida do Pedido De Credito {0} já está congelada.").format(pedido.name))
		if getdate(self.data_do_congelamento) > getdate(nowdate()):
			frappe.throw(_("A Data do Congelamento não pode ser futura."))

		# Simulação em memória (o Pedido não é gravado aqui) - on_submit repete
		# o cálculo sobre as linhas reais.
		saldo, divida = _encargos_na_data(pedido, self.data_do_congelamento)
		self.capital_congelado = saldo["capital"]
		self.juros_congelados = saldo["juros"]
		self.multa_congelada = saldo["multa"]
		self.mora_congelada = saldo["mora"]
		self.valor_congelado = sum(saldo.values())
		self.divida_congelada = sum(divida.values())

	def on_submit(self):
		pedido = frappe.get_doc("Pedido De Credito", self.pedido_de_credito, for_update=True)
		_encargos_na_data(pedido, self.data_do_congelamento)
		for row in pedido.plano_de_amortizacao:
			row.encargos_congelados = 1
		pedido.congelado = 1
		pedido.data_de_congelamento = self.data_do_congelamento
		pedido.atualizar_saldo_em_divida()
		pedido.save(ignore_permissions=True)

	def on_cancel(self):
		pedido = frappe.get_doc("Pedido De Credito", self.pedido_de_credito, for_update=True)
		for row in pedido.plano_de_amortizacao:
			row.encargos_congelados = 0
		pedido.congelado = 0
		pedido.data_de_congelamento = None
		if pedido.status in ESTADOS_ATIVOS:
			_encargos_na_data(pedido, nowdate())
		pedido.atualizar_saldo_em_divida()
		pedido.save(ignore_permissions=True)


def _encargos_na_data(pedido, data):
	"""Atualiza (em memória) Multa/Juros de Mora e o estado das prestações por
	pagar de `pedido` para `data`, e devolve `decompor_saldos` nessa data."""
	settings = get_settings()
	data = getdate(data)
	for row in pedido.plano_de_amortizacao:
		if row.status == "Pago":
			continue
		atualizar_encargos_da_linha(row, pedido.taxa_diaria_de_multa, pedido.juros_de_mora, settings, data, 2)
		atualizar_estado_da_linha(row, data, settings)
	return decompor_saldos(pedido.plano_de_amortizacao, settings, data)
