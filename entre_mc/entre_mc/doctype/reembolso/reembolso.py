# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt

from entre_mc.entre_mc.doctype.mc_settings.mc_settings import get_settings
from entre_mc.utils.reembolso import aplicar_alocacao

LABEL_TO_CAMPO_PAGO = {
	"Juros de Mora": "juros_mora_pago",
	"Multa": "multa_paga",
	"Juros": "juros_pago",
	"Capital": "capital_pago",
}


class Reembolso(Document):
	def validate(self):
		"""Pré-visualização: simula a alocação sobre uma cópia em memória do plano,
		sem persistir alterações no Pedido De Credito."""
		pedido = frappe.get_doc("Pedido De Credito", self.pedido_de_credito)
		settings = get_settings()

		alocacoes = aplicar_alocacao(
			pedido.plano_de_amortizacao,
			pedido.taxa_diaria_de_multa,
			pedido.juros_de_mora,
			settings,
			self.montante_pago,
			self.data_de_pagamento,
		)

		self.set("alocacoes", [])
		for alocacao in alocacoes:
			self.append("alocacoes", alocacao)

	def on_submit(self):
		"""Aplica a alocação a sério, persistindo o Pedido De Credito.

		`validate()` já correu como parte deste submit e gravou `self.alocacoes` com
		uma simulação sobre uma cópia em memória do plano; aqui recalculamos (de
		forma determinística, com os mesmos dados) diretamente sobre as linhas reais
		do Pedido para as persistir - sem voltar a tocar em `self.alocacoes`.
		"""
		pedido = frappe.get_doc("Pedido De Credito", self.pedido_de_credito)
		settings = get_settings()

		aplicar_alocacao(
			pedido.plano_de_amortizacao,
			pedido.taxa_diaria_de_multa,
			pedido.juros_de_mora,
			settings,
			self.montante_pago,
			self.data_de_pagamento,
		)

		pedido.atualizar_saldo_em_divida()
		if pedido.status == "Desembolsado":
			pedido.status = "Em Pagamento"
		if pedido.todas_as_prestacoes_pagas():
			pedido.status = "Liquidado"
		pedido.save(ignore_permissions=True)

	def on_cancel(self):
		"""Reverte exatamente os valores registados por este Reembolso."""
		pedido = frappe.get_doc("Pedido De Credito", self.pedido_de_credito)
		linhas_por_numero = {row.numero: row for row in pedido.plano_de_amortizacao}

		for alocacao in self.alocacoes:
			row = linhas_por_numero.get(alocacao.prestacao)
			if not row:
				continue
			campo = LABEL_TO_CAMPO_PAGO[alocacao.componente]
			row.set(campo, flt(row.get(campo)) - flt(alocacao.valor))
			row.status = "Pago Parcial" if any(
				flt(row.get(c)) > 0
				for c in ("capital_pago", "juros_pago", "multa_paga", "juros_mora_pago")
			) else "Pendente"

		pedido.atualizar_saldo_em_divida()
		if pedido.status == "Liquidado" and not pedido.todas_as_prestacoes_pagas():
			pedido.status = "Em Pagamento"
		pedido.save(ignore_permissions=True)


@frappe.whitelist()
def obter_contexto(pedido_de_credito):
	"""Dados para o painel "Situação do Pedido" no Reembolso: saldo em dívida,
	a próxima prestação em falta e o total em atraso (se houver), mais o plano
	de amortização completo para a tabela abaixo - para quem regista o
	pagamento saber quanto falta pagar sem ter de abrir o Pedido em separado."""
	pedido = frappe.get_doc("Pedido De Credito", pedido_de_credito)
	linhas = pedido.plano_de_amortizacao

	nao_pagas = [linha for linha in linhas if linha.status != "Pago"]
	proxima = min(nao_pagas, key=lambda linha: linha.numero) if nao_pagas else None

	total_em_atraso = sum(_valor_em_falta(linha) for linha in linhas if linha.status == "Atrasado")

	return {
		"saldo_em_divida": pedido.saldo_em_divida,
		"proxima_prestacao": {
			"numero": proxima.numero,
			"data_limite_pagamento": proxima.data_limite_pagamento,
			"valor_em_falta": _valor_em_falta(proxima),
			"status": proxima.status,
		}
		if proxima
		else None,
		"total_em_atraso": total_em_atraso,
		"plano": [linha.as_dict() for linha in linhas],
	}


def _valor_em_falta(linha):
	return flt(
		(linha.capital_mensal - linha.capital_pago)
		+ (linha.juros_mensais - linha.juros_pago)
		+ (linha.multa_aplicada - linha.multa_paga)
		+ (linha.juros_mora_aplicado - linha.juros_mora_pago)
	)
