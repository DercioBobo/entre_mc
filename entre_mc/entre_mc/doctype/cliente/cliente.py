# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class Cliente(Document):
	def validate(self):
		self.valor_disponivel_mensal = flt(self.rendimento_mensal_medio) - flt(self.despesas_mensais_fixas)

	def after_insert(self):
		if self.proponente_de_origem:
			frappe.db.set_value(
				"Proponente",
				self.proponente_de_origem,
				{"convertido_em_cliente": 1, "cliente": self.name},
			)


ATIVOS = ("Desembolsado", "Em Pagamento")


@frappe.whitelist()
def obter_resumo(cliente):
	"""Dados para o painel "Resumo do Cliente": histórico de Pedidos de Crédito
	e Garantias, mais os totais agregados mostrados nos cartões do topo."""
	pedidos = frappe.get_all(
		"Pedido De Credito",
		filters={"cliente": cliente},
		fields=[
			"name",
			"produto",
			"capital_solicitado",
			"workflow_state",
			"status",
			"saldo_em_divida",
			"creation",
		],
		order_by="creation desc",
	)
	garantias = frappe.get_all(
		"Garantia",
		filters={"cliente": cliente},
		fields=["name", "status", "data"],
		order_by="creation desc",
	)

	total_emprestado = sum(flt(p.capital_solicitado) for p in pedidos if p.status)
	saldo_em_divida = sum(
		flt(p.saldo_em_divida) for p in pedidos if p.status in (*ATIVOS, "Incumprimento")
	)

	return {
		"pedidos": pedidos,
		"garantias": garantias,
		"totais": {
			"total_pedidos": len(pedidos),
			"total_emprestado": total_emprestado,
			"saldo_em_divida": saldo_em_divida,
			"ativos": len([p for p in pedidos if p.status in ATIVOS]),
			"incumprimento": len([p for p in pedidos if p.status == "Incumprimento"]),
			"liquidados": len([p for p in pedidos if p.status == "Liquidado"]),
			"garantias_disponiveis": len([g for g in garantias if g.status == "Disponível"]),
		},
	}
