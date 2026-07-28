# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

"""Consolida os antigos estados "Desembolsado" e "Em Pagamento" de Pedido De
Credito num único estado "Em Curso". As duas distinções nunca eram lidas de
forma diferente em lado nenhum do código - só assinalavam se já tinha havido
o primeiro pagamento, informação recuperável a partir do histórico de
Reembolso caso venha a ser precisa."""

import frappe


def execute():
	frappe.reload_doctype("Pedido De Credito")

	total = frappe.db.count("Pedido De Credito", {"status": ["in", ["Desembolsado", "Em Pagamento"]]})
	if not total:
		return

	frappe.db.sql(
		"""
		UPDATE `tabPedido De Credito`
		SET status = 'Em Curso'
		WHERE status IN ('Desembolsado', 'Em Pagamento')
		"""
	)
	frappe.db.commit()
