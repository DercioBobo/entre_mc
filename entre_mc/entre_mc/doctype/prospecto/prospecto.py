# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

"""Prospecto: pessoa identificada no trabalho de prospecção no terreno, antes
de ser Proponente.

O Estado acompanha o processo até ao fim: os primeiros (Novo, Contactado,
Interessado, Em Negociação, Perdido) são geridos pelo utilizador; "Proponente"
e "Cliente" são postos automaticamente quando o Proponente criado a partir
daqui é gravado (ver Proponente.after_insert) e quando esse Proponente é
convertido em Cliente (ver Cliente.after_insert).
"""

import frappe
from frappe import _
from frappe.model.document import Document


class Prospecto(Document):
	def validate(self):
		# O estado nunca fica atrás do que já aconteceu de facto.
		if self.cliente:
			self.estado = "Cliente"
		elif self.proponente:
			self.estado = "Proponente"
		elif self.estado in ("Proponente", "Cliente"):
			frappe.throw(
				_('O estado "{0}" é atribuído automaticamente ao converter o Prospecto em Proponente.').format(
					self.estado
				)
			)


def marcar_como_proponente(prospecto, proponente):
	frappe.db.set_value("Prospecto", prospecto, {"estado": "Proponente", "proponente": proponente})


def marcar_como_cliente(proponente, cliente):
	prospecto = frappe.db.get_value("Proponente", proponente, "prospecto_de_origem")
	if prospecto:
		frappe.db.set_value("Prospecto", prospecto, {"estado": "Cliente", "cliente": cliente})
