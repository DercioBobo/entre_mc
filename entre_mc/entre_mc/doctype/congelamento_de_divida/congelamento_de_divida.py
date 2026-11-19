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
atualizados normalmente - só os encargos param. Os Reembolsos funcionam como
sempre.

Há duas formas de sair do congelamento, com efeitos diferentes:

- Descongelar (botão no documento submetido, ver `descongelar`): o crédito
  volta ao normal a partir da Data do Descongelamento. A Multa volta a contar
  desse dia em diante, mas os dias em que a dívida esteve congelada nunca são
  cobrados. O documento fica "Terminado", como registo do período.
- Cancelar: anula o congelamento, como se nunca tivesse existido - a Multa é
  recalculada incluindo os dias em que esteve congelado. Só para corrigir um
  congelamento registado por engano.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, nowdate

from entre_mc.entre_mc.doctype.mc_settings.mc_settings import get_settings
from entre_mc.utils.reembolso import (
	ESTADOS_FECHADOS,
	atualizar_encargos_da_linha,
	atualizar_estado_da_linha,
	decompor_saldos,
	limpar_cache_de_periodos_congelados,
)

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

		anterior = frappe.db.sql(
			"""
			select max(data_do_descongelamento) from `tabCongelamento De Divida`
			where docstatus = 1 and pedido_de_credito = %s and name != %s
			""",
			(self.pedido_de_credito, self.name or ""),
		)[0][0]
		if anterior and getdate(self.data_do_congelamento) < getdate(anterior):
			frappe.throw(
				_("A Data do Congelamento não pode ser anterior ao último descongelamento deste crédito ({0}).").format(
					frappe.utils.formatdate(anterior)
				)
			)

		self.estado = "Ativo"
		self.data_do_descongelamento = None
		self.motivo_do_descongelamento = None

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
		_marcar_pedido(pedido, congelado=1, desde=self.data_do_congelamento)
		pedido.atualizar_saldo_em_divida()
		pedido.save(ignore_permissions=True)
		limpar_cache_de_periodos_congelados()

	def on_cancel(self):
		# Este documento deixa de contar como período congelado: a Multa passa a
		# ser calculada como se o congelamento nunca tivesse existido.
		limpar_cache_de_periodos_congelados()
		pedido = frappe.get_doc("Pedido De Credito", self.pedido_de_credito, for_update=True)
		if not self.data_do_descongelamento:
			# Ainda estava ativo. Se já tinha sido descongelado, o Pedido pode
			# entretanto ter outro congelamento em vigor - não lhe mexer.
			_marcar_pedido(pedido, congelado=0)
		if pedido.status in ESTADOS_ATIVOS:
			_encargos_na_data(pedido, nowdate())
		pedido.atualizar_saldo_em_divida()
		pedido.save(ignore_permissions=True)


@frappe.whitelist()
def descongelar(congelamento, data=None, motivo=None):
	"""Termina o congelamento: o crédito volta a gerar Multa e Juros de Mora a
	partir de `data`, sem cobrar os dias em que esteve congelado."""
	doc = frappe.get_doc("Congelamento De Divida", congelamento)
	doc.check_permission("submit")

	if doc.docstatus != 1:
		frappe.throw(_("Só é possível descongelar um Congelamento submetido."))
	if doc.data_do_descongelamento:
		frappe.throw(
			_("Este Congelamento já foi terminado em {0}.").format(
				frappe.utils.formatdate(doc.data_do_descongelamento)
			)
		)

	data = getdate(data or nowdate())
	if data > getdate(nowdate()):
		frappe.throw(_("A Data do Descongelamento não pode ser futura."))
	if data < getdate(doc.data_do_congelamento):
		frappe.throw(_("A Data do Descongelamento não pode ser anterior à Data do Congelamento."))

	pedido = frappe.get_doc("Pedido De Credito", doc.pedido_de_credito, for_update=True)

	doc.db_set(
		{"estado": "Terminado", "data_do_descongelamento": data, "motivo_do_descongelamento": motivo}
	)
	limpar_cache_de_periodos_congelados()

	_marcar_pedido(pedido, congelado=0)
	if pedido.status in ESTADOS_ATIVOS:
		# Já com o período congelado excluído (ver `_intervalos_com_multa`).
		_encargos_na_data(pedido, nowdate())
	pedido.atualizar_saldo_em_divida()
	pedido.save(ignore_permissions=True)

	doc.add_comment(
		"Info",
		_("Dívida descongelada a partir de {0}. {1}").format(frappe.utils.formatdate(data), motivo or ""),
	)
	return {"saldo_em_divida": pedido.saldo_em_divida}


def _marcar_pedido(pedido, congelado, desde=None):
	for row in pedido.plano_de_amortizacao:
		row.encargos_congelados = congelado
	pedido.congelado = congelado
	pedido.data_de_congelamento = desde if congelado else None


def _encargos_na_data(pedido, data):
	"""Atualiza (em memória) Multa/Juros de Mora e o estado das prestações por
	pagar de `pedido` para `data`, e devolve `decompor_saldos` nessa data."""
	settings = get_settings()
	data = getdate(data)
	for row in pedido.plano_de_amortizacao:
		if row.status in ESTADOS_FECHADOS:
			continue
		atualizar_encargos_da_linha(row, pedido.taxa_diaria_de_multa, pedido.juros_de_mora, settings, data, 2)
		atualizar_estado_da_linha(row, data, settings)
	return decompor_saldos(pedido.plano_de_amortizacao, settings, data)
