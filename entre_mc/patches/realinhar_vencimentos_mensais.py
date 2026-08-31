# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

"""Reancora as datas de vencimento dos créditos mensais já em curso ao dia do
desembolso (meses de calendário), em vez dos blocos de 30 dias com que foram
gerados - ver `entre_mc.utils.amortizacao.usar_vencimento_calendario` e a nova
opção `MC Settings.vencimento_no_dia_do_desembolso`.

O plano antigo fazia a 1ª prestação vencer 30 dias após o desembolso, o que
punha o dia de vencimento a deslizar mês após mês (desembolso a 25 -> vencimento
a 24 -> 23 -> ...). A tarefa diária lia essas datas erradas e aplicava Multa e
Juros de Mora a prestações que, pelo acordo com o cliente (pagamento sempre no
mesmo dia do mês), não estavam em atraso.

Só toca em Pedidos:
- com `frequencia == "Mensal"` (nas outras frequências o bloco fixo é o
  comportamento pretendido);
- com `status` em ("Em Curso", "Incumprimento") - créditos ativos;
- sem qualquer pagamento registado no plano (à data desta migração ainda não
  existiam Reembolsos; um plano com pagamentos é ignorado e registado em log
  para revisão manual, para nunca reescrever histórico financeiro).

Como não há pagamentos, o plano é regenerado por completo (mesmo motor, datas
de calendário), os encargos indevidos são zerados e o estado de cada prestação
- e um eventual "Incumprimento" - são recalculados face às datas corretas.
"""

import frappe
from frappe.utils import date_diff, flt, getdate, nowdate

from entre_mc.utils.amortizacao import build_plano
from entre_mc.utils.reembolso import atualizar_encargos_da_linha, atualizar_estado_da_linha

ESTADOS_ATIVOS = ("Em Curso", "Incumprimento")
CAMPOS_PAGOS = ("capital_pago", "juros_pago", "multa_paga", "juros_mora_pago")


def execute():
	frappe.reload_doc("entre_mc", "doctype", "mc_settings")
	frappe.reload_doc("entre_mc", "doctype", "plano_de_amortizacao")
	frappe.reload_doc("entre_mc", "doctype", "pedido_de_credito")

	settings = frappe.get_cached_doc("MC Settings")
	hoje = getdate(nowdate())

	nomes = frappe.get_all(
		"Pedido De Credito",
		filters={"status": ["in", ESTADOS_ATIVOS], "frequencia": "Mensal"},
		pluck="name",
	)
	for nome in nomes:
		try:
			_realinhar(nome, settings, hoje)
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			frappe.log_error(
				title=f"realinhar_vencimentos_mensais falhou para {nome}",
				message=frappe.get_traceback(),
			)


def _realinhar(nome, settings, hoje):
	pedido = frappe.get_doc("Pedido De Credito", nome)

	if any(flt(row.get(campo)) for row in pedido.plano_de_amortizacao for campo in CAMPOS_PAGOS):
		frappe.log_error(
			title=f"realinhar_vencimentos_mensais: {nome} ignorado",
			message="O plano já tem pagamentos registados; reancorar datas exigiria "
			"reconciliar Multa/Juros de Mora já cobrados. Rever manualmente.",
		)
		return

	data_desembolso = frappe.db.get_value(
		"Desembolso",
		{"pedido_de_credito": nome, "docstatus": 1},
		"data_de_desembolso",
	)
	if not data_desembolso:
		frappe.log_error(
			title=f"realinhar_vencimentos_mensais: {nome} sem Desembolso submetido",
			message="Não foi possível reancorar as datas de vencimento ao dia do desembolso.",
		)
		return

	modelo = frappe.db.get_value("Produto", pedido.produto, "modelo_de_calculo_de_juros")
	linhas = build_plano(
		capital=pedido.capital_solicitado,
		taxa_juros_percent=pedido.taxa_de_juros,
		prazo_meses=pedido.prazo,
		frequencia=pedido.frequencia,
		modelo=modelo,
		data_inicio=data_desembolso,
		vencimento_calendario=True,
	)

	antigas = [getdate(row.data_limite_pagamento) for row in sorted(pedido.plano_de_amortizacao, key=lambda r: r.numero)]
	novas = [getdate(linha["data_limite_pagamento"]) for linha in linhas]
	if antigas == novas:
		return

	pedido.set("plano_de_amortizacao", [])
	for linha in linhas:
		pedido.append("plano_de_amortizacao", linha)

	# Prestações realmente em atraso à data de hoje (face às datas corretas)
	# voltam a receber encargos - mesma lógica da tarefa diária atualizar_atrasos.
	maior_atraso = 0
	for row in pedido.plano_de_amortizacao:
		atualizar_encargos_da_linha(
			row, pedido.taxa_diaria_de_multa, pedido.juros_de_mora, settings, hoje, 2
		)
		atualizar_estado_da_linha(row, hoje, settings)
		dias_atraso = date_diff(hoje, row.data_limite_pagamento) - flt(settings.dias_de_tolerancia)
		maior_atraso = max(maior_atraso, dias_atraso)

	pedido.atualizar_saldo_em_divida()

	if pedido.status == "Incumprimento" and not (
		settings.dias_para_incumprimento and maior_atraso > settings.dias_para_incumprimento
	):
		pedido.status = "Em Curso"

	pedido.save(ignore_permissions=True)
