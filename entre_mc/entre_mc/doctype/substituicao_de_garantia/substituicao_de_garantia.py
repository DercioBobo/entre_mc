# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

"""Substituição da Garantia de um Pedido De Credito por outra equivalente do
mesmo cliente, com o crédito ainda em curso.

Ao submeter, a Garantia a Substituir é trocada pela Nova Garantia no campo
Garantias do Pedido. O Destino da garantia antiga depende da sua Posse: se
estava com a Empresa, é "Devolvida ao Cliente" (fica "Devolvida") ou
"Mantida em Carteira"; se só foi listada e nunca foi tomada (Posse =
Cliente), não há nada a devolver - sai do Pedido e continua "Disponível". Estes documentos são o histórico das garantias
que o processo já teve. Cancelar repõe a garantia original.
"""

import frappe
from frappe import _
from frappe.model.document import Document

ESTADOS_ATIVOS = ("Em Curso", "Incumprimento")
DEVOLVIDA = "Devolvida ao Cliente"
NAO_TOMADA = "Não foi tomada (ficou com o Cliente)"


class SubstituicaoDeGarantia(Document):
	def validate(self):
		pedido = frappe.get_doc("Pedido De Credito", self.pedido_de_credito)
		if pedido.status not in ESTADOS_ATIVOS:
			frappe.throw(
				_("Só é possível substituir a garantia de um crédito em curso ou em incumprimento ({0}: {1}).").format(
					pedido.name, pedido.status or _("não desembolsado")
				)
			)
		if self.garantia_atual == self.garantia_nova:
			frappe.throw(_("A Nova Garantia tem de ser diferente da Garantia a Substituir."))

		garantias_do_pedido = [row.garantia for row in pedido.garantias]
		if self.garantia_atual not in garantias_do_pedido:
			frappe.throw(
				_("A Garantia {0} não está associada ao Pedido De Credito {1}.").format(
					self.garantia_atual, pedido.name
				)
			)
		if self.garantia_nova in garantias_do_pedido:
			frappe.throw(
				_("A Garantia {0} já está associada ao Pedido De Credito {1}.").format(self.garantia_nova, pedido.name)
			)

		posse = frappe.db.get_value("Garantia", self.garantia_atual, "posse")
		if self.destino_da_garantia_antiga == DEVOLVIDA and posse == "Cliente":
			frappe.throw(
				_(
					'A Garantia {0} está na posse do Cliente - não há nada a devolver. Escolha o destino "{1}".'
				).format(self.garantia_atual, NAO_TOMADA)
			)
		if self.destino_da_garantia_antiga == NAO_TOMADA and posse == "Empresa":
			frappe.throw(
				_(
					"A Garantia {0} está na posse da Empresa. Escolha se é devolvida ao Cliente ou mantida em carteira."
				).format(self.garantia_atual)
			)

		nova = frappe.db.get_value("Garantia", self.garantia_nova, ["cliente", "status"], as_dict=True)
		if nova.cliente != pedido.cliente:
			frappe.throw(
				_("A Garantia {0} pertence a outro cliente, não a {1}.").format(self.garantia_nova, pedido.cliente)
			)
		if nova.status != "Disponível":
			frappe.throw(
				_("A Garantia {0} não está disponível (estado atual: {1}).").format(self.garantia_nova, nova.status)
			)

	def on_submit(self):
		self._trocar(self.garantia_atual, self.garantia_nova)
		if self.destino_da_garantia_antiga == DEVOLVIDA:
			frappe.db.set_value("Garantia", self.garantia_atual, "status", "Devolvida")

	def on_cancel(self):
		self._trocar(self.garantia_nova, self.garantia_atual)
		if self.destino_da_garantia_antiga == DEVOLVIDA:
			frappe.db.set_value("Garantia", self.garantia_atual, "status", "Disponível")

	def _trocar(self, de, para):
		pedido = frappe.get_doc("Pedido De Credito", self.pedido_de_credito, for_update=True)
		linha = next((row for row in pedido.garantias if row.garantia == de), None)
		if not linha:
			frappe.throw(
				_("A Garantia {0} já não está associada ao Pedido De Credito {1}.").format(de, pedido.name)
			)
		linha.garantia = para
		pedido.save(ignore_permissions=True)


@frappe.whitelist()
def garantias_para_substituicao(doctype, txt, searchfield, start, page_len, filters):
	"""Query do Link "Nova Garantia": garantias disponíveis do mesmo Cliente que
	ainda não estão associadas a este Pedido De Credito - nunca a própria
	garantia que está a ser substituída."""
	frappe.has_permission("Garantia", "read", throw=True)

	filters = filters or {}
	cliente = filters.get("cliente")
	if not cliente:
		return []

	excluir = set()
	if filters.get("pedido_de_credito"):
		excluir.update(
			frappe.get_all("Pedido Garantia", filters={"parent": filters["pedido_de_credito"]}, pluck="garantia")
		)
	if filters.get("garantia_atual"):
		excluir.add(filters["garantia_atual"])

	condicoes = [
		["cliente", "=", cliente],
		["status", "=", "Disponível"],
		["name", "like", f"%{txt}%"],
	]
	if excluir:
		condicoes.append(["name", "not in", list(excluir)])
	return frappe.get_all(
		"Garantia", filters=condicoes, limit_start=start, limit_page_length=page_len, as_list=True
	)
