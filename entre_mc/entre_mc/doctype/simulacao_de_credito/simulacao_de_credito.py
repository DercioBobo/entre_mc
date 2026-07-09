# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowdate

from entre_mc.utils.amortizacao import build_plano


class SimulacaoDeCredito(Document):
	def validate(self):
		check_limites(self.produto, self.capital_solicitado, self.prazo)
		linhas = calcular_plano(
			self.produto, self.capital_solicitado, self.taxa_de_juros, self.prazo, self.frequencia
		)
		self.set("plano_de_amortizacao", [])
		for linha in linhas:
			self.append("plano_de_amortizacao", linha)


def check_limites(produto, capital, prazo):
	produto_doc = frappe.get_doc("Produto", produto)
	if flt(capital) > flt(produto_doc.capital_maximo):
		frappe.throw(
			_("Capital Solicitado ({0}) excede o Capital Máximo do produto ({1}).").format(
				capital, produto_doc.capital_maximo
			)
		)
	if flt(capital) < flt(produto_doc.capital_minimo):
		frappe.throw(
			_("Capital Solicitado ({0}) é inferior ao Capital Mínimo do produto ({1}).").format(
				capital, produto_doc.capital_minimo
			)
		)
	if flt(prazo) > flt(produto_doc.prazo_maximo):
		frappe.throw(
			_("Prazo solicitado ({0}) excede o Prazo Máximo do produto ({1}).").format(
				prazo, produto_doc.prazo_maximo
			)
		)
	if flt(prazo) < flt(produto_doc.prazo_minimo):
		frappe.throw(
			_("Prazo solicitado ({0}) é inferior ao Prazo Mínimo do produto ({1}).").format(
				prazo, produto_doc.prazo_minimo
			)
		)
	return produto_doc


def calcular_plano(produto, capital, taxa_de_juros, prazo, frequencia, data_inicio=None):
	produto_doc = frappe.get_doc("Produto", produto)
	return build_plano(
		capital=capital,
		taxa_juros_percent=taxa_de_juros,
		prazo_meses=prazo,
		frequencia=frequencia,
		modelo=produto_doc.modelo_de_calculo_de_juros,
		data_inicio=data_inicio or nowdate(),
	)


@frappe.whitelist()
def preview_plano(produto, capital_solicitado, taxa_de_juros, prazo, frequencia):
	"""Called by the client script to render the live amortization preview before save."""
	check_limites(produto, capital_solicitado, prazo)
	linhas = calcular_plano(produto, capital_solicitado, taxa_de_juros, prazo, frequencia)
	return linhas


@frappe.whitelist()
def criar_pedido_de_credito(simulacao):
	"""Converte o Proponente em Cliente (se ainda não o for) e cria um Pedido de
	Crédito pré-preenchido a partir desta simulação. Ponto de entrada único para
	"o cliente quer avançar com este pedido", chamado a partir da Simulação em
	vez de exigir que o utilizador vá converter o Proponente manualmente e depois
	preencher um Pedido de Crédito do zero."""
	from entre_mc.entre_mc.doctype.proponente.proponente import converter_em_cliente

	sim = frappe.get_doc("Simulacao De Credito", simulacao)
	if sim.pedido_de_credito:
		frappe.throw(
			_("Já existe um Pedido de Crédito criado a partir desta simulação ({0}).").format(
				sim.pedido_de_credito
			)
		)

	proponente = frappe.get_doc("Proponente", sim.proponente)
	cliente = proponente.cliente if proponente.convertido_em_cliente else converter_em_cliente(proponente.name)

	pedido = frappe.new_doc("Pedido De Credito")
	pedido.cliente = cliente
	pedido.produto = sim.produto
	pedido.capital_solicitado = sim.capital_solicitado
	pedido.taxa_de_juros = sim.taxa_de_juros
	pedido.prazo = sim.prazo
	pedido.finalidade = sim.finalidade
	pedido.frequencia = sim.frequencia
	pedido.simulacao_de_credito = sim.name
	pedido.insert()

	sim.pedido_de_credito = pedido.name
	sim.save()

	return pedido.name
