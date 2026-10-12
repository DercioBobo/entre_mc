# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

"""Corrige a Multa negativa no Plano De Amortizacao dos créditos com pagamentos.

Antes de `calcular_multa_acumulada`, a Multa era recalculada todos os dias como
taxa × dias × capital+juros em atraso *atual*: depois de um pagamento parcial
esse valor caía abaixo do que já tinha sido pago em multa, e a multa em falta
(`multa_aplicada - multa_paga - multa_perdoada`) ficava negativa.

- Prestações por pagar de créditos ativos: a Multa é recalculada para hoje com
  a regra nova (cada dia sobre o valor por pagar nesse dia), tal como a
  tarefa diária faria.
- Prestações já pagas (e créditos liquidados) não são recalculadas, para não
  reabrir dívida: só sobem `multa_aplicada` até ao já pago/perdoado, o que
  elimina o valor negativo sem mexer em dinheiro recebido.
"""

import frappe
from frappe.utils import flt, getdate, nowdate

from entre_mc.utils.reembolso import atualizar_encargos_da_linha, atualizar_estado_da_linha

ESTADOS_ATIVOS = ("Em Curso", "Incumprimento")


def execute():
	settings = frappe.get_cached_doc("MC Settings")
	hoje = getdate(nowdate())

	nomes = frappe.get_all("Pedido De Credito", filters={"status": ["is", "set"]}, pluck="name")
	for nome in nomes:
		try:
			_corrigir(nome, settings, hoje)
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			frappe.log_error(
				title=f"corrigir_multa_negativa falhou para {nome}",
				message=frappe.get_traceback(),
			)


def _corrigir(nome, settings, hoje):
	pedido = frappe.get_doc("Pedido De Credito", nome)
	ativo = pedido.status in ESTADOS_ATIVOS

	for row in pedido.plano_de_amortizacao:
		if ativo and row.status != "Pago":
			atualizar_encargos_da_linha(
				row, pedido.taxa_diaria_de_multa, pedido.juros_de_mora, settings, hoje, 2
			)
			atualizar_estado_da_linha(row, hoje, settings)
		else:
			row.multa_aplicada = flt(
				max(flt(row.multa_aplicada), flt(row.multa_paga) + flt(row.multa_perdoada)), 2
			)

	if ativo:
		pedido.atualizar_saldo_em_divida()
	pedido.save(ignore_permissions=True)
