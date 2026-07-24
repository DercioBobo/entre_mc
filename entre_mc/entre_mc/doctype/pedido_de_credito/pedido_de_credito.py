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
			# Estimativa: gerada logo após aprovação, anteriormente ao desembolso real.
			# As datas ficam ancoradas em hoje só para efeitos de pré-visualização/impressão -
			# confirmar_desembolso() volta a gerar o plano com a data real de desembolso,
			# que é a que efetivamente conta para vencimentos e mora.
			self.gerar_plano_de_amortizacao()

		self.atualizar_saldo_em_divida()

	def gerar_plano_de_amortizacao(self, data_inicio=None):
		linhas = calcular_plano(
			self.produto,
			self.capital_solicitado,
			self.taxa_de_juros,
			self.prazo,
			self.frequencia,
			data_inicio=data_inicio or self.data_de_inicio_prevista,
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

	def confirmar_desembolso(self, data_de_desembolso):
		"""Ancora o plano de amortização à data real de desembolso.

		O plano gerado em Aprovado era só uma estimativa (baseada na data de
		aprovação); o cliente só passa a dever a partir de quando recebe o
		dinheiro, por isso as datas de vencimento têm de partir daqui, não da
		aprovação. Seguro de regenerar por completo porque, antes do desembolso,
		não pode ainda existir nenhum Reembolso contra este pedido.
		"""
		self.gerar_plano_de_amortizacao(data_inicio=data_de_desembolso)
		self.status = "Desembolsado"
		self.save(ignore_permissions=True)

	def todas_as_prestacoes_pagas(self):
		return bool(self.plano_de_amortizacao) and all(
			row.status == "Pago" for row in self.plano_de_amortizacao
		)
