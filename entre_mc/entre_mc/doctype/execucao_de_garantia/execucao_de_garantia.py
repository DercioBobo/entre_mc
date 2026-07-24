# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class ExecucaoDeGarantia(Document):
	def validate(self):
		garantia = frappe.get_doc("Garantia", self.garantia)
		if garantia.status != "Disponível":
			frappe.throw(
				_("A Garantia {0} não está disponível para execução (estado atual: {1}).").format(
					garantia.name, garantia.status
				)
			)

	def on_submit(self):
		pedido = frappe.get_doc("Pedido De Credito", self.pedido_de_credito)
		pedido.marcar_como_liquidado(
			motivo=_(
				"Liquidado por dação em pagamento - execução da Garantia {0} ({1}) em {2}."
			).format(self.garantia, self.name, frappe.utils.formatdate(self.data))
		)

		frappe.db.set_value("Garantia", self.garantia, "status", "Não Disponível")
