# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

"""Perdão (waiver) da Multa e/ou do Juros de Mora em aberto de uma ou mais
prestações de um Pedido De Credito.

Dois modos de uso:

- Perdão parcial por período (`perdoar_tudo` desligado, o padrão):
  `periodo_de`/`periodo_ate` escolhem só uma janela de dias de atraso da
  Multa a perdoar - ex.: multa iniciada no dia 1, hoje é dia 14, mas só se
  quer perdoar o dia 10 ao 14: `calcular_multa_no_periodo` (ver
  entre_mc.utils.reembolso) calcula exatamente essa fatia, porque a Multa é
  linear nos dias de atraso. Juros de Mora não é sugerido neste modo (é um
  encargo único, sem "dias" para fatiar).

- Perdão total (`perdoar_tudo` ligado): limpa de uma vez toda a Multa e todo
  o Juros de Mora em aberto das prestações carregadas, ignorando o período.
  Pensado para quando o atraso só existe porque um Reembolso que devia ter
  sido lançado não foi (o cliente pagou, só faltou registar), não para
  perdão parcial por política.

Em qualquer dos modos, os valores continuam editáveis linha a linha antes de
submeter.

Os valores perdoados ficam em `Plano De Amortizacao.multa_perdoada` e
`juros_mora_perdoado`, nunca subtraídos de `multa_aplicada`/
`juros_mora_aplicado` - assim fica sempre visível quanto foi cobrado vs.
perdoado, e `entre_mc.utils.reembolso` (usado pela tarefa diária e por
qualquer Reembolso) passa a tratar esses valores como já liquidados.

Com `isentar_multa_futura` desligado (o padrão), o perdão da Multa cobre só a
fatia calculada acima - se a prestação continuar por pagar, volta a gerar
multa normalmente a partir do dia seguinte ao fim do período perdoado, como
qualquer atraso novo. Ligado, a prestação fica marcada `isento_de_multa` e
nunca mais volta a gerar multa, por isso `on_cancel` só desliga essa marca se
nenhum outro Perdao De Multa submetido ainda a mantiver isenta. Juros de Mora
não tem equivalente - é um encargo único, uma vez perdoado não é reaplicado.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate, nowdate

from entre_mc.entre_mc.doctype.mc_settings.mc_settings import get_settings
from entre_mc.utils.reembolso import (
	atualizar_encargos_da_linha,
	atualizar_estado_da_linha,
	calcular_multa_no_periodo,
)


class PerdaoDeMulta(Document):
	def validate(self):
		if not self.prestacoes:
			frappe.throw(_("Adicione pelo menos uma prestação a perdoar."))

		pedido = frappe.get_doc("Pedido De Credito", self.pedido_de_credito, for_update=True)
		if not pedido.status:
			frappe.throw(
				_("O Pedido De Credito {0} ainda não foi desembolsado; não há multa a perdoar.").format(
					pedido.name
				)
			)
		if pedido.status == "Liquidado":
			frappe.throw(
				_("O Pedido De Credito {0} já está liquidado; não há multa em aberto a perdoar.").format(
					pedido.name
				)
			)

		settings = get_settings()
		hoje = getdate(nowdate())
		linhas_por_numero = {row.numero: row for row in pedido.plano_de_amortizacao}

		total = 0
		for item in self.prestacoes:
			row = linhas_por_numero.get(item.numero)
			if not row:
				frappe.throw(
					_("A prestação Nº {0} não existe no Pedido De Credito {1}.").format(
						item.numero, pedido.name
					)
				)
			atualizar_encargos_da_linha(row, pedido.taxa_diaria_de_multa, pedido.juros_de_mora, settings, hoje, 2)

			item.data_limite_pagamento = row.data_limite_pagamento
			disponivel_multa = flt(flt(row.multa_aplicada) - flt(row.multa_paga) - flt(row.multa_perdoada), 2)
			disponivel_mora = flt(
				flt(row.juros_mora_aplicado) - flt(row.juros_mora_pago) - flt(row.juros_mora_perdoado), 2
			)
			item.multa_em_aberto = disponivel_multa
			item.mora_em_aberto = disponivel_mora
			if not cint(self.perdoar_tudo):
				item.dias_no_periodo, _valor_periodo = calcular_multa_no_periodo(
					row, pedido.taxa_diaria_de_multa, settings, hoje, self.periodo_de, self.periodo_ate
				)

			if flt(item.valor_perdoado_multa) <= 0 and flt(item.valor_perdoado_mora) <= 0:
				frappe.throw(
					_("A prestação Nº {0} tem de ter um valor de Multa ou de Juros de Mora a perdoar.").format(
						item.numero
					)
				)
			if flt(item.valor_perdoado_multa) - disponivel_multa > 0.01:
				frappe.throw(
					_("A prestação Nº {0} só tem {1} de Multa em aberto.").format(
						item.numero, frappe.format(disponivel_multa, {"fieldtype": "Currency"})
					)
				)
			if flt(item.valor_perdoado_mora) - disponivel_mora > 0.01:
				frappe.throw(
					_("A prestação Nº {0} só tem {1} de Juros de Mora em aberto.").format(
						item.numero, frappe.format(disponivel_mora, {"fieldtype": "Currency"})
					)
				)
			total += flt(item.valor_perdoado_multa) + flt(item.valor_perdoado_mora)

		self.total_perdoado = flt(total, 2)

	def on_submit(self):
		pedido = frappe.get_doc("Pedido De Credito", self.pedido_de_credito, for_update=True)
		settings = get_settings()
		hoje = getdate(nowdate())
		linhas_por_numero = {row.numero: row for row in pedido.plano_de_amortizacao}

		for item in self.prestacoes:
			row = linhas_por_numero[item.numero]
			atualizar_encargos_da_linha(row, pedido.taxa_diaria_de_multa, pedido.juros_de_mora, settings, hoje, 2)

			disponivel_multa = flt(flt(row.multa_aplicada) - flt(row.multa_paga) - flt(row.multa_perdoada), 2)
			valor_multa = flt(min(flt(item.valor_perdoado_multa), disponivel_multa), 2)
			item.valor_perdoado_multa = valor_multa
			if valor_multa > 0:
				row.multa_perdoada = flt(flt(row.multa_perdoada) + valor_multa, 2)

			disponivel_mora = flt(
				flt(row.juros_mora_aplicado) - flt(row.juros_mora_pago) - flt(row.juros_mora_perdoado), 2
			)
			valor_mora = flt(min(flt(item.valor_perdoado_mora), disponivel_mora), 2)
			item.valor_perdoado_mora = valor_mora
			if valor_mora > 0:
				row.juros_mora_perdoado = flt(flt(row.juros_mora_perdoado) + valor_mora, 2)

			if self.isentar_multa_futura and valor_multa > 0:
				row.isento_de_multa = 1
			atualizar_estado_da_linha(row, hoje, settings)

		pedido.atualizar_saldo_em_divida()
		pedido.save(ignore_permissions=True)

	def on_cancel(self):
		pedido = frappe.get_doc("Pedido De Credito", self.pedido_de_credito, for_update=True)
		settings = get_settings()
		hoje = getdate(nowdate())
		linhas_por_numero = {row.numero: row for row in pedido.plano_de_amortizacao}

		for item in self.prestacoes:
			row = linhas_por_numero.get(item.numero)
			if not row:
				continue

			row.multa_perdoada = flt(max(flt(row.multa_perdoada) - flt(item.valor_perdoado_multa), 0), 2)
			row.juros_mora_perdoado = flt(
				max(flt(row.juros_mora_perdoado) - flt(item.valor_perdoado_mora), 0), 2
			)
			if self.isentar_multa_futura and row.isento_de_multa:
				if not _outra_isencao_ativa(self.pedido_de_credito, item.numero, self.name):
					row.isento_de_multa = 0
			atualizar_estado_da_linha(row, hoje, settings)

		pedido.atualizar_saldo_em_divida()
		pedido.save(ignore_permissions=True)


def _outra_isencao_ativa(pedido_de_credito, numero, excluir_nome):
	"""True se outro Perdao De Multa (submetido, != excluir_nome) para o mesmo
	Pedido De Credito ainda isenta esta prestação de multa futura - usado por
	on_cancel para não desligar `isento_de_multa` por engano quando há mais do
	que um perdão ativo sobre a mesma prestação."""
	outros = frappe.get_all(
		"Perdao De Multa",
		filters={
			"pedido_de_credito": pedido_de_credito,
			"isentar_multa_futura": 1,
			"docstatus": 1,
			"name": ["!=", excluir_nome],
		},
		pluck="name",
	)
	if not outros:
		return False
	return bool(
		frappe.get_all(
			"Prestacao Perdoada",
			filters={"parenttype": "Perdao De Multa", "parent": ["in", outros], "numero": numero},
			limit_page_length=1,
		)
	)


@frappe.whitelist()
def carregar_prestacoes_em_atraso(pedido_de_credito, periodo_de=None, periodo_ate=None, perdoar_tudo=0):
	"""Prestações do Pedido De Credito com Multa e/ou Juros de Mora em aberto
	(recalculados para hoje, em memória - sem gravar), para preencher a tabela
	do Perdao De Multa.

	Sem `perdoar_tudo`: `periodo_de`/`periodo_ate` filtram e dimensionam só a
	Multa (ver `calcular_multa_no_periodo`) - Juros de Mora não é sugerido
	(fica com valor 0, editável manualmente se necessário).

	Com `perdoar_tudo`: ignora o período e sugere o valor total em aberto de
	Multa e de Juros de Mora, para a limpeza integral de um atraso indevido
	(ex.: Reembolso que devia ter sido lançado e não foi)."""
	frappe.has_permission("Pedido De Credito", "read", doc=pedido_de_credito, throw=True)

	pedido = frappe.get_doc("Pedido De Credito", pedido_de_credito)
	settings = get_settings()
	hoje = getdate(nowdate())
	perdoar_tudo = cint(perdoar_tudo)

	prestacoes = []
	for row in pedido.plano_de_amortizacao:
		if row.status == "Pago":
			continue

		atualizar_encargos_da_linha(row, pedido.taxa_diaria_de_multa, pedido.juros_de_mora, settings, hoje, 2)
		disponivel_multa = flt(flt(row.multa_aplicada) - flt(row.multa_paga) - flt(row.multa_perdoada), 2)
		disponivel_mora = flt(
			flt(row.juros_mora_aplicado) - flt(row.juros_mora_pago) - flt(row.juros_mora_perdoado), 2
		)

		dias_no_periodo = None
		if perdoar_tudo:
			valor_multa = disponivel_multa
			valor_mora = disponivel_mora
		else:
			dias_no_periodo, valor_multa = calcular_multa_no_periodo(
				row, pedido.taxa_diaria_de_multa, settings, hoje, periodo_de, periodo_ate
			)
			valor_mora = 0

		if valor_multa <= 0 and valor_mora <= 0:
			continue

		prestacoes.append(
			{
				"numero": row.numero,
				"data_limite_pagamento": row.data_limite_pagamento,
				"multa_em_aberto": disponivel_multa,
				"dias_no_periodo": dias_no_periodo,
				"valor_perdoado_multa": valor_multa,
				"mora_em_aberto": disponivel_mora,
				"valor_perdoado_mora": valor_mora,
			}
		)

	return prestacoes
