# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

"""Reporte mensal ao Banco de Moçambique ("Reporte Periódico de Informações de
Microfinanças - Instituições Sujeitas à Monitorização").

Uma linha por operação de crédito ainda por liquidar no último dia do mês
escolhido, com as 13 colunas do modelo oficial. A situação de cada crédito é
a desse último dia (reconstruída pelo relatório Instante T), não a de hoje -
assim o reporte de um mês já fechado dá sempre o mesmo resultado.

Colunas (numeração das Notas Explicativas do modelo):

 4. Montante do Desembolso - o crédito concedido (Capital Solicitado), não o
    valor entregue já líquido da Taxa Administrativa.
 6. Valor da Prestação - capital + juros da próxima prestação por pagar.
 8. Prazo de Reembolso - vencimento da última prestação.
10. Crédito em Dívida - capital + juros por pagar das prestações ainda não
    vencidas (exclui as em atraso).
11. Crédito em Atraso - capital + juros por pagar das prestações em atraso
    (sem Multa nem Juros de Mora).
13. PPEs - Cliente marcado como Pessoa Politicamente Exposta.

O botão "Exportar Modelo BM" devolve o ficheiro Excel do modelo oficial já
preenchido (ver `modelo_bm.py`); os dados da instituição vêm de MC Settings.
"""

import calendar
import datetime

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

from entre_mc.entre_mc.doctype.mc_settings.mc_settings import get_settings
from entre_mc.entre_mc.report.instante_t.instante_t import get_situacoes
from entre_mc.entre_mc.report.reporte_ao_banco_de_mocambique import modelo_bm

COLUNAS = (
	("operacao", "Nº da Operação (1)", "Link", 140),
	("cliente", "Nome do Cliente (2)", "Data", 200),
	("data_de_desembolso", "Data de Desembolso (3)", "Date", 120),
	("montante", "Montante do Desembolso (4)", "Currency", 150),
	("finalidade", "Finalidade do Crédito (5)", "Data", 130),
	("prestacao", "Valor da Prestação (6)", "Currency", 130),
	("periodicidade", "Periodicidade dos Pagamentos (7)", "Data", 130),
	("prazo", "Prazo de Reembolso (8)", "Date", 120),
	("taxa_de_juro", "Taxa de Juro (9)", "Percent", 100),
	("credito_em_divida", "Crédito em Dívida (10)", "Currency", 140),
	("credito_em_atraso", "Crédito em Atraso (11)", "Currency", 140),
	("dias_em_atraso", "Dias em Atraso (12)", "Int", 110),
	("ppe", "PPEs (13)", "Data", 80),
)


def execute(filters=None):
	inicio, fim = periodo(filters or {})
	return get_columns(), get_data(fim)


def get_columns():
	columns = []
	for fieldname, label, fieldtype, width in COLUNAS:
		column = {"label": _(label), "fieldname": fieldname, "fieldtype": fieldtype, "width": width}
		if fieldname == "operacao":
			column["options"] = "Pedido De Credito"
		columns.append(column)
	return columns


def periodo(filters):
	"""(primeiro dia, último dia) do mês escolhido - por omissão, o mês anterior."""
	hoje = getdate(nowdate())
	mes_anterior = hoje.replace(day=1) - datetime.timedelta(days=1)
	ano = cint(filters.get("ano")) or mes_anterior.year
	mes = filters.get("mes")
	mes = modelo_bm.MESES.index(mes) + 1 if mes in modelo_bm.MESES else mes_anterior.month
	return datetime.date(ano, mes, 1), datetime.date(ano, mes, calendar.monthrange(ano, mes)[1])


def get_data(fim):
	situacoes = get_situacoes({}, fim)
	if not situacoes:
		return []

	nomes = [s.pedido.name for s in situacoes]
	pedidos = {
		p.name: p
		for p in frappe.get_all(
			"Pedido De Credito",
			filters={"name": ["in", nomes]},
			fields=["name", "cliente", "capital_solicitado", "finalidade", "frequencia", "taxa_de_juros"],
		)
	}
	clientes = {
		c.name: c
		for c in frappe.get_all(
			"Cliente",
			filters={"name": ["in", list({p.cliente for p in pedidos.values()})]},
			fields=["name", "nome_completo", "pessoa_politicamente_exposta"],
		)
	}

	data = []
	for situacao in situacoes:
		pedido = pedidos[situacao.pedido.name]
		cliente = clientes.get(pedido.cliente) or frappe._dict()
		rows = situacao.rows

		por_pagar = [r for r in rows if r.em_falta > 0]
		proxima = min(por_pagar, key=lambda r: r.numero) if por_pagar else None
		em_atraso = [r for r in rows if r.dias_atraso > 0]
		por_vencer = [r for r in rows if r.dias_atraso <= 0]

		data.append(
			{
				"operacao": pedido.name,
				"cliente": cliente.get("nome_completo") or pedido.cliente,
				"data_de_desembolso": situacao.desembolso.data_de_desembolso,
				"montante": flt(pedido.capital_solicitado),
				"finalidade": pedido.finalidade,
				"prestacao": flt(proxima.capital_mensal + proxima.juros_mensais, 2) if proxima else 0,
				"periodicidade": pedido.frequencia,
				"prazo": max((r.data_limite_pagamento for r in rows), default=None),
				"taxa_de_juro": flt(pedido.taxa_de_juros),
				"credito_em_divida": _capital_e_juros_por_pagar(por_vencer),
				"credito_em_atraso": _capital_e_juros_por_pagar(em_atraso),
				"dias_em_atraso": max((r.dias_atraso for r in rows), default=0),
				"ppe": _("Sim") if cliente.get("pessoa_politicamente_exposta") else _("Não"),
			}
		)

	data.sort(key=lambda d: (d["data_de_desembolso"], d["operacao"]))
	return data


def _capital_e_juros_por_pagar(rows):
	return flt(
		sum(
			max(flt(r.capital_mensal) - flt(r.capital_pago), 0) + max(flt(r.juros_mensais) - flt(r.juros_pago), 0)
			for r in rows
		),
		2,
	)


def dados_da_instituicao():
	"""Identificação da instituição para o cabeçalho do modelo - de MC Settings,
	com a Empresa como recurso para a denominação, telefone e e-mail."""
	settings = get_settings()
	empresa = (
		frappe.db.get_value(
			"Company", settings.company, ["company_name", "phone_no", "email"], as_dict=True
		)
		if settings.company
		else None
	) or frappe._dict()
	return {
		"denominacao": settings.bm_denominacao or empresa.company_name,
		"endereco": settings.bm_endereco,
		"provincia": settings.bm_provincia,
		"distrito": settings.bm_distrito,
		"telefone": settings.bm_telefone or empresa.phone_no,
		"fax": settings.bm_fax,
		"email": settings.bm_email or empresa.email,
		"numero_de_trabalhadores": settings.bm_numero_de_trabalhadores,
		"data_de_inicio_das_actividades": settings.bm_data_de_inicio_das_actividades,
		"responsavel": settings.bm_responsavel,
		"instituicao_representada": settings.bm_instituicao_representada,
	}


@frappe.whitelist()
def exportar_modelo(mes=None, ano=None):
	"""Descarrega o modelo Excel do Banco de Moçambique preenchido para o mês."""
	if not frappe.has_permission("Pedido De Credito", "report"):
		frappe.throw(_("Sem permissão para este relatório."), frappe.PermissionError)
	frappe.only_for(
		("System Manager", "Gestor de Crédito", "Analista de Crédito", "Oficial de Crédito", "Tesoureiro")
	)

	inicio, fim = periodo({"mes": mes, "ano": ano})
	campos = [fieldname for fieldname, _label, _fieldtype, _width in COLUNAS]
	linhas = [[linha[campo] for campo in campos] for linha in get_data(fim)]

	frappe.response["filename"] = f"Reporte BM - {modelo_bm.MESES[fim.month - 1]} {fim.year}.xlsx"
	frappe.response["filecontent"] = modelo_bm.gerar(inicio, fim, dados_da_instituicao(), linhas)
	frappe.response["type"] = "binary"
