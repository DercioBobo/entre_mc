// Copyright (c) 2026, Dércio Bobo and contributors
// For license information, please see license.txt

frappe.ui.form.on("Desembolso", {
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
