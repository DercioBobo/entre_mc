// Copyright (c) 2026, Dércio Bobo and contributors
// For license information, please see license.txt

frappe.ui.form.on("Execucao De Garantia", {
	setup(frm) {
		frm.set_query("garantia", () => {
			if (!frm.doc.pedido_de_credito) {
				return { filters: { status: "Disponível" } };
			}
			return {
				query: "entre_mc.entre_mc.doctype.execucao_de_garantia.execucao_de_garantia.garantias_do_pedido",
				filters: { pedido_de_credito: frm.doc.pedido_de_credito },
			};
		});

		frm.set_query("pedido_de_credito", () => {
			if (!frm.doc.garantia) return {};
			return {
				query: "entre_mc.entre_mc.doctype.execucao_de_garantia.execucao_de_garantia.pedidos_da_garantia",
				filters: { garantia: frm.doc.garantia },
			};
		});
	},
});
