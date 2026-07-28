// Copyright (c) 2026, Dércio Bobo and contributors
// For license information, please see license.txt

frappe.ui.form.on("Desembolso", {
	onload(frm) {
		frm.set_query("pedido_de_credito", () => ({
			filters: { workflow_state: "Aprovado", status: "" },
		}));
	},

	pedido_de_credito(frm) {
		if (!frm.doc.pedido_de_credito) return;
		// valor_desembolsado fica editável (o tesoureiro pode ter de o ajustar em
		// casos excecionais) - por isso pré-preenchemos aqui em vez de fetch_from.
		frappe.db.get_value("Pedido De Credito", frm.doc.pedido_de_credito, "valor_a_desembolsar").then((r) => {
			if (r.message && r.message.valor_a_desembolsar != null) {
				frm.set_value("valor_desembolsado", r.message.valor_a_desembolsar);
			}
		});
	},

	cliente(frm) {
		if (!frm.doc.cliente) return;
		// Dados Bancários ficam editáveis (ao contrário de taxa_diaria_de_multa/juros_de_mora
		// em Pedido De Credito) porque este desembolso pode legitimamente usar uma conta
		// diferente da que está gravada no Cliente - por isso não usamos fetch_from aqui.
		frappe.db.get_value("Cliente", frm.doc.cliente, ["banco", "numero_de_conta", "nib"]).then((r) => {
			if (!r.message) return;
			frm.set_value("banco", r.message.banco);
			frm.set_value("numero_de_conta", r.message.numero_de_conta);
			frm.set_value("nib", r.message.nib);
		});
	},
});
