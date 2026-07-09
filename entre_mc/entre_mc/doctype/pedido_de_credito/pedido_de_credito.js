// Copyright (c) 2026, Dércio Bobo and contributors
// For license information, please see license.txt

frappe.ui.form.on("Pedido de Credito", {
	onload(frm) {
		if (frm.is_new() && !frm.doc.frequencia) {
			frappe.db.get_single_value("MC Settings", "frequencia_padrao").then((value) => {
				if (value) frm.set_value("frequencia", value);
			});
		}
	},

	refresh(frm) {
		render_plano(frm);
	},

	simulacao_de_credito(frm) {
		if (!frm.doc.simulacao_de_credito) return;
		frappe.db.get_doc("Simulacao de Credito", frm.doc.simulacao_de_credito).then((sim) => {
			frm.set_value({
				produto: sim.produto,
				capital_solicitado: sim.capital_solicitado,
				taxa_de_juros: sim.taxa_de_juros,
				prazo: sim.prazo,
				finalidade: sim.finalidade,
				frequencia: sim.frequencia,
			});
		});
	},
});

function render_plano(frm) {
	const wrapper = frm.fields_dict.pre_visualizacao_html?.$wrapper;
	if (!wrapper) return;
	wrapper.html(entre_mc.render_plano_html(frm.doc.plano_de_amortizacao, frm.doc.currency));
}
