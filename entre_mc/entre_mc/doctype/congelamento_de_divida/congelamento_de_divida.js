// Copyright (c) 2026, Dércio Bobo and contributors
// For license information, please see license.txt

frappe.ui.form.on("Congelamento De Divida", {
	setup(frm) {
		frm.set_query("pedido_de_credito", () => ({
			filters: { status: ["in", ["Em Curso", "Incumprimento"]], congelado: 0 },
		}));
	},

	refresh(frm) {
		if (frm.doc.docstatus === 0) {
			frm.set_intro(
				__(
					"Ao submeter, o crédito deixa de gerar Multa e Juros de Mora. O Valor Congelado é calculado ao gravar."
				),
				"blue"
			);
		}
	},
});
