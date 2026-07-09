# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt

from entre_mc.entre_mc.doctype.simulacao_de_credito.simulacao_de_credito import (
	calcular_plano,
	check_limites,
)

APROVADO = "Aprovado"


class PedidoDeCredito(Document):
	def validate(self):
		if not self.workflow_state:
			self.workflow_state = "Rascunho"

		check_limites(self.produto, self.capital_solicitado, self.prazo)

		if self.workflow_state == APROVADO and not self.plano_de_amortizacao:
			self.gerar_plano_de_amortizacao()

		self.atualizar_saldo_em_divida()

	def gerar_plano_de_amortizacao(self):
		linhas = calcular_plano(
			self.produto, self.capital_solicitado, self.taxa_de_juros, self.prazo, self.frequencia
		)
		self.set("plano_de_amortizacao", [])
		for linha in linhas:
			self.append("plano_de_amortizacao", linha)

	def atualizar_saldo_em_divida(self):
		"""Soma do que ainda falta pagar (capital + juros + multa + mora) em todas as prestações.

		Antes de qualquer reembolso isto coincide com o Saldo previsto na última linha do
		plano; depois de reembolsos parciais reflecte o valor real ainda em dívida.
		"""
		total = 0
		for row in self.plano_de_amortizacao:
			total += flt(row.capital_mensal) - flt(row.capital_pago)
			total += flt(row.juros_mensais) - flt(row.juros_pago)
			total += flt(row.multa_aplicada) - flt(row.multa_paga)
			total += flt(row.juros_mora_aplicado) - flt(row.juros_mora_pago)
		self.saldo_em_divida = total

	def marcar_como_liquidado(self):
		self.status = "Liquidado"
		self.save(ignore_permissions=True)

	def marcar_como_desembolsado(self):
		self.status = "Desembolsado"
		self.save(ignore_permissions=True)

	def todas_as_prestacoes_pagas(self):
		return bool(self.plano_de_amortizacao) and all(
			row.status == "Pago" for row in self.plano_de_amortizacao
		)
