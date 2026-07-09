// Copyright (c) 2026, Dércio Bobo and contributors
// For license information, please see license.txt

frappe.ui.form.on("Pedido De Credito", {
	onload(frm) {
		if (frm.is_new() && !frm.doc.frequencia) {
			frappe.db.get_single_value("MC Settings", "frequencia_padrao").then((value) => {
				if (value) frm.set_value("frequencia", value);
			});
		}
	},

	refresh(frm) {
		render_plano(frm);

		if (frm.is_new()) return;

		frm.add_custom_button(__("Criar Garantia"), () => {
			frappe.new_doc("Garantia", null, (doc) => {
				doc.cliente = frm.doc.cliente;
			});
			frappe.msgprint(
				__(
					"Depois de gravar a Garantia, volte a este Pedido e adicione-a ao campo Garantias."
				)
			);
		}, __("Criar"));

		if (frm.doc.workflow_state === "Aprovado" && !frm.doc.status) {
			frm.add_custom_button(__("Criar Desembolso"), () => {
				frappe.new_doc("Desembolso", null, (doc) => {
					doc.pedido_de_credito = frm.doc.name;
					doc.valor_desembolsado = frm.doc.capital_solicitado;
				});
			}, __("Criar"));
		}

		if (["Desembolsado", "Em Pagamento"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Criar Reembolso"), () => {
				frappe.new_doc("Reembolso", null, (doc) => {
					doc.pedido_de_credito = frm.doc.name;
				});
			}, __("Criar"));
		}

		frm.page.set_inner_btn_group_as_primary(__("Criar"));
	},

	simulacao_de_credito(frm) {
		if (!frm.doc.simulacao_de_credito) return;
		frappe.db.get_doc("Simulacao De Credito", frm.doc.simulacao_de_credito).then((sim) => {
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
