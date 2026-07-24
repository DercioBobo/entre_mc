# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

import frappe
from frappe import _
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

		self.validar_simulacao_do_mesmo_cliente()
		self.validar_garantias_do_mesmo_cliente()

		check_limites(self.produto, self.capital_solicitado, self.prazo)

		if self.workflow_state == APROVADO and not self.plano_de_amortizacao:
			# Estimativa: gerada logo após aprovação, anteriormente ao desembolso real.
			# As datas ficam ancoradas em hoje só para efeitos de pré-visualização/impressão -
			# confirmar_desembolso() volta a gerar o plano com a data real de desembolso,
			# que é a que efetivamente conta para vencimentos e mora.
			self.gerar_plano_de_amortizacao()

		self.atualizar_saldo_em_divida()

	def validar_simulacao_do_mesmo_cliente(self):
		"""A simulação de origem tem de pertencer ao mesmo cliente deste pedido -
		um Proponente só é ligado a um Cliente depois de convertido, por isso a
		comparação passa sempre por essa cadeia (simulação -> proponente -> cliente)."""
		if not self.simulacao_de_credito:
			return
		proponente = frappe.db.get_value("Simulacao De Credito", self.simulacao_de_credito, "proponente")
		cliente_da_simulacao = frappe.db.get_value("Proponente", proponente, "cliente") if proponente else None
		if cliente_da_simulacao and cliente_da_simulacao != self.cliente:
			frappe.throw(
				_("A Simulacao De Credito {0} pertence a outro cliente, não a {1}.").format(
					self.simulacao_de_credito, self.cliente
				)
			)

	def validar_garantias_do_mesmo_cliente(self):
		"""As garantias associadas têm de pertencer ao mesmo cliente deste pedido."""
		for row in self.garantias:
			garantia_cliente = frappe.db.get_value("Garantia", row.garantia, "cliente")
			if garantia_cliente and garantia_cliente != self.cliente:
				frappe.throw(
					_("A Garantia {0} pertence a outro cliente, não a {1}.").format(
						row.garantia, self.cliente
					)
				)

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

	def marcar_como_liquidado(self, motivo=None):
		"""Chamado quando a Garantia associada é executada (dação em pagamento): a
		dívida é dada como extinta independentemente do valor da garantia face ao
		saldo em dívida, pelo que todas as prestações pendentes são marcadas como
		pagas e o saldo em dívida zera. Não há lugar a reembolsos depois disto -
		ver o bloqueio em Reembolso.validate()."""
		for row in self.plano_de_amortizacao:
			row.capital_pago = row.capital_mensal
			row.juros_pago = row.juros_mensais
			row.multa_paga = row.multa_aplicada
			row.juros_mora_pago = row.juros_mora_aplicado
			row.status = "Pago"
		self.atualizar_saldo_em_divida()
		self.status = "Liquidado"
		if motivo:
			self.observacoes_liquidacao = motivo
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


@frappe.whitelist()
def simulacoes_do_cliente(doctype, txt, searchfield, start, page_len, filters):
	"""Query do Link "Simulacao De Credito": só simulações cujo Proponente já foi
	convertido no Cliente escolhido - a simulação de origem tem de pertencer
	sempre ao mesmo cliente do pedido."""
	cliente = (filters or {}).get("cliente")
	if not cliente:
		return []
	proponentes = frappe.get_all("Proponente", filters={"cliente": cliente}, pluck="name")
	if not proponentes:
		return []
	return frappe.get_all(
		"Simulacao De Credito",
		filters=[
			["proponente", "in", proponentes],
			["name", "like", f"%{txt}%"],
		],
		limit_start=start,
		limit_page_length=page_len,
		as_list=True,
	)


@frappe.whitelist()
def garantias_do_cliente(doctype, txt, searchfield, start, page_len, filters):
	"""Query do campo "Garantias": só garantias disponíveis pertencentes ao
	Cliente escolhido - nunca garantias de outro cliente."""
	cliente = (filters or {}).get("cliente")
	if not cliente:
		return []
	return frappe.get_all(
		"Garantia",
		filters=[
			["cliente", "=", cliente],
			["status", "=", "Disponível"],
			["name", "like", f"%{txt}%"],
		],
		limit_start=start,
		limit_page_length=page_len,
		as_list=True,
	)
