# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import nowdate

from entre_mc.utils.amortizacao import MODELOS, build_plano


@frappe.whitelist()
def calcular(capital, taxa_de_juros, prazo, modelo, frequencia):
	"""Cálculo instantâneo, sem Proponente/Cliente/Produto - usado pelo Simulador
	de Crédito para responder "quanto é que a pessoa paga" na hora."""
	if modelo not in MODELOS:
		frappe.throw(f"Modelo de cálculo de juros inválido: {modelo}")

	return build_plano(
		capital=capital,
		taxa_juros_percent=taxa_de_juros,
		prazo_meses=prazo,
		frequencia=frequencia,
		modelo=modelo,
		data_inicio=nowdate(),
	)
