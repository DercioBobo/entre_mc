# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class Proponente(Document):
	pass


@frappe.whitelist()
def converter_em_cliente(proponente):
	doc = frappe.get_doc("Proponente", proponente)
	if doc.convertido_em_cliente:
		frappe.throw(_("Este Proponente já foi convertido em Cliente ({0}).").format(doc.cliente))

	cliente = frappe.new_doc("Cliente")
	cliente.nome_completo = doc.nome_completo
	cliente.data_de_nascimento = doc.data_de_nascimento
	cliente.ocupacao = doc.ocupacao
	cliente.local_de_trabalho = doc.local_de_trabalho
	cliente.rendimento_mensal = doc.rendimento_mensal
	cliente.proponente_de_origem = doc.name
	cliente.insert()

	doc.convertido_em_cliente = 1
	doc.cliente = cliente.name
	doc.save()

	return cliente.name
