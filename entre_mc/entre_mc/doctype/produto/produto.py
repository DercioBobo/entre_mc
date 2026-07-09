# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class Produto(Document):
	def validate(self):
		if self.capital_minimo > self.capital_maximo:
			frappe.throw(_("Capital Mínimo não pode ser maior que Capital Máximo."))
		if self.prazo_minimo > self.prazo_maximo:
			frappe.throw(_("Prazo Mínimo não pode ser maior que Prazo Máximo."))
