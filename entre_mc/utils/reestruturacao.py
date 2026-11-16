# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

"""Regras partilhadas entre Reestruturacao De Credito e os documentos que
mexem nas prestações de um Pedido De Credito (Reembolso, Perdao De Multa)."""

import frappe
from frappe import _
from frappe.utils import flt

CAMPOS_DE_MOVIMENTO = (
	"capital_pago",
	"juros_pago",
	"multa_paga",
	"multa_perdoada",
	"juros_mora_pago",
	"juros_mora_perdoado",
)


def tem_movimentos(row):
	"""A prestação já recebeu algum pagamento ou perdão."""
	return any(flt(row.get(campo)) > 0 for campo in CAMPOS_DE_MOVIMENTO)


def impedir_cancelamento_apos_reestruturacao(pedido_de_credito, numeros):
	"""Uma Reestruturacao De Credito fecha as prestações anteriores pelo que já
	tinha sido pago/perdoado nelas e passa o resto para o novo plano. Cancelar
	depois disso um Reembolso ou Perdao De Multa dessas prestações reabriria
	nelas um valor que já está no novo plano - por isso tem de se cancelar
	primeiro a Reestruturação."""
	limite = frappe.db.sql(
		"""
		select max(ultima_prestacao_mantida) from `tabReestruturacao De Credito`
		where docstatus = 1 and pedido_de_credito = %s
		""",
		pedido_de_credito,
	)[0][0]
	if limite and any(int(numero or 0) <= int(limite) for numero in numeros):
		frappe.throw(
			_(
				"Este documento afeta prestações anteriores a uma Reestruturação do Pedido De Credito {0}. "
				"Cancele primeiro a Reestruturação."
			).format(pedido_de_credito)
		)
