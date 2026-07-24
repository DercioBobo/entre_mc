// Copyright (c) 2026, Dércio Bobo and contributors
// For license information, please see license.txt

frappe.ui.form.on("Devolucao Da Garantia", {
	setup(frm) {
		frm.set_query("garantia", () => {
			if (!frm.doc.pedido_de_credito) {
				return { filters: { status: "Disponível" } };
			}
			return {
				query: "entre_mc.entre_mc.doctype.devolucao_da_garantia.devolucao_da_garantia.garantias_do_pedido",
				filters: { pedido_de_credito: frm.doc.pedido_de_credito },
			};
		});

		frm.set_query("pedido_de_credito", () => {
			if (!frm.doc.garantia) {
				return { filters: { status: "Liquidado" } };
			}
			return {
				query: "entre_mc.entre_mc.doctype.devolucao_da_garantia.devolucao_da_garantia.pedidos_da_garantia",
				filters: { garantia: frm.doc.garantia },
			};
		});
	},
});
