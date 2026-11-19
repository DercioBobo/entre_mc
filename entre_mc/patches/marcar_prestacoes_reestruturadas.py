# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

"""Antes do estado "Reestruturado", a Reestruturação fechava como "Pago" as
prestações que ainda tinham algo em aberto mas já tinham movimentos (pagas em
parte ou com perdão). Corrige essas linhas: são as que, no `plano_anterior`
de uma Reestruturação submetida, não estavam "Pago" e continuam no plano do
Pedido (numero <= ultima_prestacao_mantida) agora como "Pago"."""

import frappe


def execute():
	for rest in frappe.get_all(
		"Reestruturacao De Credito",
		filters={"docstatus": 1},
		fields=["name", "pedido_de_credito", "ultima_prestacao_mantida"],
	):
		numeros = frappe.get_all(
			"Plano De Amortizacao",
			filters={
				"parenttype": "Reestruturacao De Credito",
				"parent": rest.name,
				"parentfield": "plano_anterior",
				"status": ["!=", "Pago"],
				"numero": ["<=", int(rest.ultima_prestacao_mantida or 0)],
			},
			pluck="numero",
		)
		if not numeros:
			continue

		for name in frappe.get_all(
			"Plano De Amortizacao",
			filters={
				"parenttype": "Pedido De Credito",
				"parent": rest.pedido_de_credito,
				"numero": ["in", numeros],
				"status": "Pago",
			},
			pluck="name",
		):
			frappe.db.set_value("Plano De Amortizacao", name, "status", "Reestruturado", update_modified=False)
