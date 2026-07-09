# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

"""Tarefas agendadas do entre_mc (ver hooks.py -> scheduler_events)."""

import frappe
from frappe.utils import date_diff, flt, getdate, nowdate

from entre_mc.entre_mc.doctype.mc_settings.mc_settings import get_settings
from entre_mc.utils.reembolso import atualizar_encargos_da_linha, atualizar_estado_da_linha

ESTADOS_EM_ABERTO = ("Desembolsado", "Em Pagamento")


def atualizar_atrasos():
	"""Corre diariamente. Para cada Pedido De Credito em aberto:

	- recalcula Multa/Juros de Mora acumulados e o estado ("Atrasado", etc.) de
	  cada prestação ainda não paga, sem tocar em valores já pagos;
	- atualiza o Saldo em Dívida;
	- marca o Pedido como "Incumprimento" se a prestação mais antiga em dívida
	  ultrapassar `MC Settings.dias_para_incumprimento`.

	A alocação real de um pagamento continua a ser feita apenas no Reembolso -
	esta tarefa serve só para que o atraso fique visível em listas e relatórios
	mesmo quando ninguém tentou pagar.
	"""
	settings = get_settings()
	hoje = getdate(nowdate())

	for nome_pedido in frappe.get_all(
		"Pedido De Credito", filters={"status": ["in", ESTADOS_EM_ABERTO]}, pluck="name"
	):
		_atualizar_pedido(nome_pedido, settings, hoje)


def _atualizar_pedido(nome_pedido, settings, hoje):
	pedido = frappe.get_doc("Pedido De Credito", nome_pedido)
	produto = frappe.get_doc("Produto", pedido.produto)

	maior_atraso = 0
	for row in pedido.plano_de_amortizacao:
		if row.status == "Pago":
			continue
		atualizar_encargos_da_linha(row, produto, settings, hoje, 2)
		atualizar_estado_da_linha(row, hoje, settings)

		dias_atraso = date_diff(hoje, row.data_limite_pagamento) - flt(settings.dias_de_tolerancia)
		maior_atraso = max(maior_atraso, dias_atraso)

	pedido.atualizar_saldo_em_divida()

	if settings.dias_para_incumprimento and maior_atraso > settings.dias_para_incumprimento:
		pedido.status = "Incumprimento"

	pedido.save(ignore_permissions=True)
