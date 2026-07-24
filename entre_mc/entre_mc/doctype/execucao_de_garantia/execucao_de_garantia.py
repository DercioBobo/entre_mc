# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class ExecucaoDeGarantia(Document):
	def validate(self):
		garantia = frappe.get_doc("Garantia", self.garantia)
		if garantia.status != "Disponível":
			frappe.throw(
				_("A Garantia {0} não está disponível para execução (estado atual: {1}).").format(
					garantia.name, garantia.status
				)
			)

		garantias_do_pedido = frappe.get_all(
			"Pedido Garantia", filters={"parent": self.pedido_de_credito}, pluck="garantia"
		)
		if self.garantia not in garantias_do_pedido:
			frappe.throw(
				_("A Garantia {0} não está associada ao Pedido De Credito {1}.").format(
					self.garantia, self.pedido_de_credito
				)
			)

		# Capturado aqui (antes do write-off em on_submit -> marcar_como_liquidado)
		# porque depois de liquidado o saldo do Pedido passa a 0 - sem isto,
		# perdia-se o registo de quanto foi efetivamente dado como liquidado por
		# esta garantia (usado no Extrato de Cliente).
		pedido = frappe.get_doc("Pedido De Credito", self.pedido_de_credito)
		self.valor_liquidado = pedido.saldo_em_divida

	def on_submit(self):
		pedido = frappe.get_doc("Pedido De Credito", self.pedido_de_credito)
		pedido.marcar_como_liquidado(
			motivo=_(
				"Liquidado por dação em pagamento - execução da Garantia {0} ({1}) em {2}."
			).format(self.garantia, self.name, frappe.utils.formatdate(self.data))
		)

		frappe.db.set_value("Garantia", self.garantia, "status", "Não Disponível")


@frappe.whitelist()
def garantias_do_pedido(doctype, txt, searchfield, start, page_len, filters):
	"""Query do Link "Garantia": só as garantias associadas ao Pedido De Credito
	já escolhido (e ainda disponíveis) - a garantia e o pedido têm de andar
	sempre a par, nunca uma execução com uma garantia de outro pedido."""
	frappe.has_permission("Garantia", "read", throw=True)

	pedido_de_credito = (filters or {}).get("pedido_de_credito")
	if not pedido_de_credito:
		return []
	nomes = frappe.get_all("Pedido Garantia", filters={"parent": pedido_de_credito}, pluck="garantia")
	if not nomes:
		return []
	return frappe.get_all(
		"Garantia",
		filters=[
			["name", "in", nomes],
			["status", "=", "Disponível"],
			["name", "like", f"%{txt}%"],
		],
		limit_start=start,
		limit_page_length=page_len,
		as_list=True,
	)


@frappe.whitelist()
def pedidos_da_garantia(doctype, txt, searchfield, start, page_len, filters):
	"""Query do Link "Pedido De Credito": só os pedidos a que a Garantia já
	escolhida está associada - mesma regra, no sentido inverso."""
	frappe.has_permission("Pedido De Credito", "read", throw=True)

	garantia = (filters or {}).get("garantia")
	if not garantia:
		return []
	nomes = frappe.get_all("Pedido Garantia", filters={"garantia": garantia}, pluck="parent")
	if not nomes:
		return []
	return frappe.get_all(
		"Pedido De Credito",
		filters=[
			["name", "in", nomes],
			["name", "like", f"%{txt}%"],
		],
		limit_start=start,
		limit_page_length=page_len,
		as_list=True,
	)
