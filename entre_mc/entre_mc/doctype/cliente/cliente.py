# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

from frappe.model.document import Document
from frappe.utils import flt


class Cliente(Document):
	def validate(self):
		self.valor_disponivel_mensal = flt(self.rendimento_mensal_medio) - flt(self.despesas_mensais_fixas)
