# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class Desembolso(Document):
	def validate(self):
		pedido = frappe.get_doc("Pedido de Crédito", self.pedido_de_credito)
		if pedido.workflow_state != "Aprovado":
			frappe.throw(_("O Pedido de Crédito {0} ainda não foi aprovado.").format(pedido.name))
		if pedido.status:
			frappe.throw(
				_("O Pedido de Crédito {0} já tem um desembolso registado ({1}).").format(
					pedido.name, pedido.status
				)
			)

	def on_submit(self):
		pedido = frappe.get_doc("Pedido de Crédito", self.pedido_de_credito)
		pedido.marcar_como_desembolsado()
