# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

"""Reestruturação de um Pedido De Credito: novo plano de amortização acordado
com o cliente devedor, sem perder o plano anterior.

Ao submeter:

- o plano em vigor é copiado na íntegra para `plano_anterior` (o histórico);
- as prestações já pagas ficam como estão; as pagas em parte (ou com perdão)
  são fechadas pelo que já foi pago/perdoado nelas, com o estado
  "Reestruturado"; as que não têm qualquer
  movimento saem do plano;
- tudo o que ficou por pagar (Capital, Juros, Multa e Juros de Mora à Data da
  Reestruturação) é substituído pelo `novo_plano`, calculado sobre o Valor a
  Reestruturar com as novas condições e o modelo de juros do Produto. As
  novas prestações continuam a numeração das que ficaram.

As prestações mantidas nunca são renumeradas, por isso os Reembolsos e
Perdões anteriores continuam a apontar para as prestações certas. Em
contrapartida, deixam de poder ser cancelados enquanto a Reestruturação
estiver submetida (ver `entre_mc.utils.reestruturacao`).

Cancelar repõe o plano anterior, desde que o novo plano ainda não tenha
pagamentos nem perdões e que não exista uma Reestruturação posterior.

Limitação conhecida: o relatório Instante T reconstrói o passado a partir do
plano em vigor, por isso para datas anteriores à Reestruturação mostra o novo
plano, não o antigo (que está em `plano_anterior`).
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, nowdate

from entre_mc.entre_mc.doctype.mc_settings.mc_settings import get_settings
from entre_mc.entre_mc.doctype.simulacao_de_credito.simulacao_de_credito import calcular_plano
from entre_mc.utils.reembolso import (
	ESTADOS_FECHADOS,
	atualizar_encargos_da_linha,
	atualizar_estado_da_linha,
	decompor_saldos,
)
from entre_mc.utils.reestruturacao import tem_movimentos

ESTADOS_ATIVOS = ("Em Curso", "Incumprimento")
CAMPOS_NAO_COPIADOS = ("Section Break", "Column Break", "Tab Break", "HTML", "Button")


class ReestruturacaoDeCredito(Document):
	def validate(self):
		pedido = frappe.get_doc("Pedido De Credito", self.pedido_de_credito, for_update=True)
		if pedido.status not in ESTADOS_ATIVOS:
			frappe.throw(
				_("Só é possível reestruturar um crédito em curso ou em incumprimento ({0}: {1}).").format(
					pedido.name, pedido.status or _("não desembolsado")
				)
			)
		if getdate(self.data_da_reestruturacao) > getdate(nowdate()):
			frappe.throw(_("A Data da Reestruturação não pode ser futura."))
		if flt(self.novo_prazo) <= 0:
			frappe.throw(_("Indique o Prazo (meses) do novo plano."))
		if flt(self.nova_taxa_de_juros) < 0:
			frappe.throw(_("A Taxa de Juros não pode ser negativa."))

		# Tudo em memória - o Pedido só é alterado em on_submit.
		saldo = _encargos_na_data(pedido, self.data_da_reestruturacao)
		self.capital_em_aberto = saldo["capital"]
		self.juros_em_aberto = saldo["juros"]
		self.multa_em_aberto = saldo["multa"]
		self.mora_em_aberto = saldo["mora"]
		self.saldo_total = flt(sum(saldo.values()), 2)
		if self.saldo_total <= 0:
			frappe.throw(_("O Pedido De Credito {0} não tem saldo em aberto a reestruturar.").format(pedido.name))

		if not flt(self.valor_a_reestruturar):
			self.valor_a_reestruturar = self.saldo_total
		if flt(self.valor_a_reestruturar) <= 0:
			frappe.throw(_("O Valor a Reestruturar tem de ser positivo."))
		self.diferenca = flt(flt(self.valor_a_reestruturar) - self.saldo_total, 2)

		if not self.nova_frequencia:
			self.nova_frequencia = pedido.frequencia
		if not self.data_de_inicio:
			self.data_de_inicio = self.data_da_reestruturacao

		mantidas = [row for row in pedido.plano_de_amortizacao if _fica_no_plano(row)]
		self.ultima_prestacao_mantida = max((row.numero for row in mantidas), default=0)

		linhas = calcular_plano(
			pedido.produto,
			self.valor_a_reestruturar,
			self.nova_taxa_de_juros,
			self.novo_prazo,
			self.nova_frequencia,
			data_inicio=self.data_de_inicio,
		)
		self.set("novo_plano", [])
		for linha in linhas:
			linha["numero"] = self.ultima_prestacao_mantida + linha["numero"]
			linha["status"] = "Pendente"
			self.append("novo_plano", linha)

	def before_submit(self):
		"""Guarda o plano em vigor (já com os encargos à Data da Reestruturação)
		como histórico, antes de on_submit o alterar."""
		pedido = frappe.get_doc("Pedido De Credito", self.pedido_de_credito, for_update=True)
		_encargos_na_data(pedido, self.data_da_reestruturacao)
		self.set("plano_anterior", [])
		for row in sorted(pedido.plano_de_amortizacao, key=lambda r: r.numero):
			self.append("plano_anterior", _copiar_linha(row))

	def on_submit(self):
		pedido = frappe.get_doc("Pedido De Credito", self.pedido_de_credito, for_update=True)
		_encargos_na_data(pedido, self.data_da_reestruturacao)

		for row in list(pedido.plano_de_amortizacao):
			if row.status in ESTADOS_FECHADOS:
				continue
			if tem_movimentos(row):
				_fechar_pelo_que_foi_pago(row)
			else:
				pedido.remove(row)

		for linha in self.novo_plano:
			nova = _copiar_linha(linha)
			nova["encargos_congelados"] = 1 if pedido.congelado else 0
			pedido.append("plano_de_amortizacao", nova)

		pedido.reestruturado = 1
		# O novo plano ainda não tem atrasos; se voltar a ter, a tarefa diária
		# repõe o Incumprimento.
		pedido.status = "Em Curso"
		pedido.atualizar_saldo_em_divida()
		pedido.save(ignore_permissions=True)

	def on_cancel(self):
		pedido = frappe.get_doc("Pedido De Credito", self.pedido_de_credito, for_update=True)

		posterior = frappe.db.exists(
			"Reestruturacao De Credito",
			{
				"pedido_de_credito": self.pedido_de_credito,
				"docstatus": 1,
				"name": ["!=", self.name],
				"creation": [">", self.creation],
			},
		)
		if posterior:
			frappe.throw(
				_("Existe uma Reestruturação posterior ({0}) deste Pedido De Credito. Cancele-a primeiro.").format(
					posterior
				)
			)

		limite = int(self.ultima_prestacao_mantida or 0)
		for row in pedido.plano_de_amortizacao:
			if row.numero > limite and tem_movimentos(row):
				frappe.throw(
					_(
						"A prestação {0} do novo plano já tem pagamentos ou perdões. "
						"Cancele primeiro esses Reembolsos/Perdões."
					).format(row.numero)
				)

		pedido.set("plano_de_amortizacao", [])
		for linha in self.plano_anterior:
			antiga = _copiar_linha(linha)
			antiga["encargos_congelados"] = 1 if pedido.congelado else 0
			pedido.append("plano_de_amortizacao", antiga)

		pedido.reestruturado = (
			1
			if frappe.db.exists(
				"Reestruturacao De Credito",
				{"pedido_de_credito": self.pedido_de_credito, "docstatus": 1, "name": ["!=", self.name]},
			)
			else 0
		)
		pedido.status = "Em Curso"
		_encargos_na_data(pedido, nowdate())
		pedido.atualizar_saldo_em_divida()
		pedido.save(ignore_permissions=True)


def _fica_no_plano(row):
	return row.status in ESTADOS_FECHADOS or tem_movimentos(row)


def _fechar_pelo_que_foi_pago(row):
	"""O que faltava pagar nesta prestação passa para o novo plano; aqui fica só
	o que já foi efetivamente pago ou perdoado."""
	row.capital_mensal = flt(row.capital_pago)
	row.juros_mensais = flt(row.juros_pago)
	row.prestacao_total = flt(row.capital_mensal + row.juros_mensais, 2)
	row.multa_aplicada = flt(flt(row.multa_paga) + flt(row.multa_perdoada), 2)
	row.juros_mora_aplicado = flt(flt(row.juros_mora_pago) + flt(row.juros_mora_perdoado), 2)
	row.status = "Reestruturado"


def _copiar_linha(row):
	campos = [
		df.fieldname
		for df in frappe.get_meta("Plano De Amortizacao").fields
		if df.fieldtype not in CAMPOS_NAO_COPIADOS
	]
	return {campo: row.get(campo) for campo in campos}


def _encargos_na_data(pedido, data):
	"""Atualiza (em memória) Multa/Juros de Mora e o estado das prestações por
	pagar de `pedido` para `data`, e devolve o saldo em aberto decomposto."""
	settings = get_settings()
	data = getdate(data)
	for row in pedido.plano_de_amortizacao:
		if row.status in ESTADOS_FECHADOS:
			continue
		atualizar_encargos_da_linha(row, pedido.taxa_diaria_de_multa, pedido.juros_de_mora, settings, data, 2)
		atualizar_estado_da_linha(row, data, settings)
	saldo, _divida = decompor_saldos(pedido.plano_de_amortizacao, settings, data)
	return saldo


@frappe.whitelist()
def condicoes_atuais(pedido_de_credito):
	"""Condições em vigor do Pedido, para pré-preencher as Novas Condições."""
	frappe.has_permission("Pedido De Credito", "read", doc=pedido_de_credito, throw=True)
	return frappe.db.get_value(
		"Pedido De Credito", pedido_de_credito, ["taxa_de_juros", "frequencia", "prazo"], as_dict=True
	)
