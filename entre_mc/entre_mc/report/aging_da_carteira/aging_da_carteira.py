# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

from frappe import _
from frappe.utils import add_days, cint, flt, getdate, nowdate

from entre_mc.entre_mc.doctype.mc_settings.mc_settings import get_settings
from entre_mc.entre_mc.report.instante_t.instante_t import get_situacoes

FAIXAS = (
	(1, 30, "1-30 dias"),
	(31, 60, "31-60 dias"),
	(61, 90, "61-90 dias"),
	(91, None, "91+ dias"),
)


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": _("Cliente"), "fieldname": "cliente", "fieldtype": "Link", "options": "Cliente", "width": 160},
		{"label": _("Faixa de Atraso"), "fieldname": "faixa", "fieldtype": "Data", "width": 130},
		{"label": _("Vencimentos de"), "fieldname": "vencimento_de", "fieldtype": "Date", "width": 115},
		{"label": _("Vencimentos até"), "fieldname": "vencimento_ate", "fieldtype": "Date", "width": 115},
		{"label": _("Nº de Prestações"), "fieldname": "num_prestacoes", "fieldtype": "Int", "width": 120},
		{"label": _("Capital em Falta"), "fieldname": "capital_em_falta", "fieldtype": "Currency", "width": 130},
		{"label": _("Juros em Falta"), "fieldname": "juros_em_falta", "fieldtype": "Currency", "width": 130},
		{"label": _("Multa"), "fieldname": "multa", "fieldtype": "Currency", "width": 110},
		{"label": _("Juros de Mora"), "fieldname": "juros_mora", "fieldtype": "Currency", "width": 120},
		{"label": _("Total em Atraso"), "fieldname": "total_em_atraso", "fieldtype": "Currency", "width": 135},
	]


def get_data(filters):
	"""Agrupa as prestações em atraso por Cliente e por faixa de dias de atraso
	(1-30/31-60/61-90/91+) tal como estavam no fim do dia `data_referencia`
	(por omissão hoje) - o plano de cada crédito é reconstruído para essa data
	pelo Instante T (`get_situacoes`): só conta Reembolsos, Perdões de Multa e
	Execuções de Garantia com data até lá, e a Multa/Juros de Mora são
	recalculados para essa data. Pelo mesmo motivo, os dias de atraso vêm das
	datas e não do `status` gravado.

	"Vencimentos de"/"Vencimentos até" mostram o intervalo de datas limite de
	pagamento que cai em cada faixa nessa data de referência (já descontada a
	tolerância de `MC Settings.dias_de_tolerancia`) - é por essa data que cada
	prestação é classificada."""
	settings = get_settings()
	data_referencia = getdate(filters.get("data_referencia") or nowdate())
	tolerancia = cint(settings.dias_de_tolerancia)

	situacoes = get_situacoes(
		{"cliente": filters.get("cliente"), "produto": filters.get("produto")}, data_referencia
	)

	buckets = {}
	for situacao in situacoes:
		cliente = situacao.pedido.cliente
		for row in situacao.rows:
			if row.dias_atraso <= 0:
				continue
			bucket = buckets.setdefault(
				(cliente, _faixa(row.dias_atraso)),
				{"num_prestacoes": 0, "capital": 0, "juros": 0, "multa": 0, "mora": 0},
			)
			bucket["num_prestacoes"] += 1
			bucket["capital"] += flt(row.capital_mensal) - flt(row.capital_pago)
			bucket["juros"] += flt(row.juros_mensais) - flt(row.juros_pago)
			bucket["multa"] += flt(row.multa_aplicada) - flt(row.multa_paga) - flt(row.multa_perdoada)
			bucket["mora"] += flt(row.juros_mora_aplicado) - flt(row.juros_mora_pago) - flt(row.juros_mora_perdoado)

	data = []
	clientes = sorted({cliente for cliente, _faixa_label in buckets}, key=lambda c: c or "")
	for cliente in clientes:
		for inicio, fim, label in FAIXAS:
			bucket = buckets.get((cliente, label))
			if not bucket:
				continue
			total = bucket["capital"] + bucket["juros"] + bucket["multa"] + bucket["mora"]
			data.append(
				{
					"cliente": cliente,
					"faixa": label,
					# dias_atraso = data_referencia - data_limite - tolerância, logo
					# a faixa [inicio, fim] corresponde a estas datas limite:
					"vencimento_de": add_days(data_referencia, -(fim + tolerancia)) if fim else None,
					"vencimento_ate": add_days(data_referencia, -(inicio + tolerancia)),
					"num_prestacoes": bucket["num_prestacoes"],
					"capital_em_falta": bucket["capital"],
					"juros_em_falta": bucket["juros"],
					"multa": bucket["multa"],
					"juros_mora": bucket["mora"],
					"total_em_atraso": total,
				}
			)
	return data


def _faixa(dias_atraso):
	for inicio, fim, label in FAIXAS:
		if (fim is None or dias_atraso <= fim) and dias_atraso >= inicio:
			return label
	return FAIXAS[-1][2]
