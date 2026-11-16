# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from entre_mc.entre_mc.doctype.prospecto.prospecto import marcar_como_proponente


class Proponente(Document):
	def after_insert(self):
		if self.prospecto_de_origem:
			marcar_como_proponente(self.prospecto_de_origem, self.name)
