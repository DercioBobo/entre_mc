// Copyright (c) 2026, Dércio Bobo and contributors
// For license information, please see license.txt

frappe.ui.form.on("Substituicao De Garantia", {
	setup(frm) {
		frm.set_query("pedido_de_credito", () => ({
			filters: { status: ["in", ["Em Curso", "Incumprimento"]] },
		}));

		// Só as garantias já associadas ao Pedido escolhido.
		frm.set_query("garantia_atual", () => ({
			query: "entre_mc.entre_mc.doctype.devolucao_da_garantia.devolucao_da_garantia.garantias_do_pedido",
			filters: { pedido_de_credito: frm.doc.pedido_de_credito },
		}));

		// Só garantias disponíveis do mesmo cliente.
		frm.set_query("garantia_nova", () => ({
			query: "entre_mc.entre_mc.doctype.pedido_de_credito.pedido_de_credito.garantias_do_cliente",
			filters: { cliente: frm.doc.cliente },
		}));
	},

	refresh(frm) {
		if (frm.doc.docstatus === 0 && frm.doc.cliente) {
			frm.add_custom_button(__("Criar Garantia"), () => {
				frappe.new_doc("Garantia", null, (doc) => {
					doc.cliente = frm.doc.cliente;
				});
			});
		}
	},

	pedido_de_credito(frm) {
		frm.set_value("garantia_atual", null);
		frm.set_value("garantia_nova", null);
	},
});
