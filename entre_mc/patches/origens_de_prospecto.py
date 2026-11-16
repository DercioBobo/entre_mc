# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

"""Cria as Origens de Prospecto por defeito.

Corre em instalações novas (hooks.py -> after_install) e, como patch, nos
sites que já existiam quando Prospecto.origem passou de Select a Link. Nesses,
as origens já usadas em Prospectos (ex.: "Balcão", que era uma opção do
Select) também são criadas, para os registos antigos não ficarem a apontar
para uma origem inexistente.
"""

import frappe

ORIGENS_POR_DEFEITO = ("Terreno", "Redes Sociais", "Indicação", "Outro")


def execute():
	origens = list(ORIGENS_POR_DEFEITO)
	if frappe.db.table_exists("Prospecto"):
		for origem in frappe.get_all("Prospecto", filters={"origem": ["is", "set"]}, pluck="origem", distinct=True):
			if origem not in origens:
				origens.append(origem)

	for origem in origens:
		if not frappe.db.exists("Origem De Prospecto", origem):
			frappe.get_doc({"doctype": "Origem De Prospecto", "origem": origem}).insert(ignore_permissions=True)
