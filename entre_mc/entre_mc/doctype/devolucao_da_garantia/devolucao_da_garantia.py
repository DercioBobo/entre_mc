# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class DevolucaoDaGarantia(Document):
	def validate(self):
		garantia = frappe.get_doc("Garantia", self.garantia)
		if garantia.status != "Disponível":
			frappe.throw(
				_("A Garantia {0} não está disponível para devolução (estado atual: {1}).").format(
					garantia.name, garantia.status
				)
			)

	def on_submit(self):
		frappe.db.set_value("Garantia", self.garantia, "status", "Devolvida")
