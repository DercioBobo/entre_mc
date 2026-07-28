// Copyright (c) 2026, Dércio Bobo and contributors
// For license information, please see license.txt

frappe.ui.form.on("Pedido De Credito", {
	setup(frm) {
		frm.set_query("simulacao_de_credito", () => {
			if (!frm.doc.cliente) return {};
			return {
				query: "entre_mc.entre_mc.doctype.pedido_de_credito.pedido_de_credito.simulacoes_do_cliente",
				filters: { cliente: frm.doc.cliente },
			};
		});

		frm.set_query("garantias", () => {
			if (!frm.doc.cliente) return {};
			return {
				query: "entre_mc.entre_mc.doctype.pedido_de_credito.pedido_de_credito.garantias_do_cliente",
				filters: { cliente: frm.doc.cliente },
			};
		});
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
					// valor_desembolsado é pré-preenchido pelo próprio Desembolso
					// (com o Valor a Desembolsar, já líquido da Taxa Administrativa)
					// quando pedido_de_credito é definido - ver desembolso.js.
					if (frm.doc.data_de_inicio_prevista) {
						doc.data_de_desembolso = frm.doc.data_de_inicio_prevista;
					}
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

	produto(frm) {
		if (!frm.doc.produto) return;
		// taxa_de_juros stays editable (unlike multa/mora), so it can't use
		// fetch_from - the framework forces fetch_from fields read-only.
		frappe.db.get_value("Produto", frm.doc.produto, "taxa_de_juros").then((r) => {
			if (r.message && r.message.taxa_de_juros != null) {
				frm.set_value("taxa_de_juros", r.message.taxa_de_juros);
			}
		});
	},

	simulacao_de_credito(frm) {
		if (!frm.doc.simulacao_de_credito) return;
		frappe.db.get_doc("Simulacao De Credito", frm.doc.simulacao_de_credito).then((sim) => {
			// Assigned directly on frm.doc (not via frm.set_value) so that setting
			// `produto` doesn't trigger its own fetch_from/onchange and overwrite
			// taxa_diaria_de_multa/juros_de_mora with the *current* Produto rates -
			// every field here must come from the simulation as it was saved, not
			// be re-derived from produto.
			Object.assign(frm.doc, {
				produto: sim.produto,
				capital_solicitado: sim.capital_solicitado,
				taxa_de_juros: sim.taxa_de_juros,
				taxa_diaria_de_multa: sim.taxa_diaria_de_multa,
				juros_de_mora: sim.juros_de_mora,
				prazo: sim.prazo,
				finalidade: sim.finalidade,
				frequencia: sim.frequencia,
			});
			frm.dirty();
			frm.refresh_fields();
		});
	},
});

function render_plano(frm) {
	const wrapper = frm.fields_dict.pre_visualizacao_html?.$wrapper;
	if (!wrapper) return;

	if (frm.is_new() || !["Desembolsado", "Em Pagamento"].includes(frm.doc.status)) {
		wrapper.html(entre_mc.render_plano_html(frm.doc.plano_de_amortizacao, frm.doc.currency));
		return;
	}

	// Multa/Juros de Mora gravados só ficam atualizados após a tarefa diária
	// ou um Reembolso submetido - aqui recalculamos em memória para que uma
	// prestação que ficou em atraso hoje já apareça correta sem esperar por isso.
	frappe.call({
		method: "entre_mc.entre_mc.doctype.pedido_de_credito.pedido_de_credito.plano_com_encargos_atuais",
		args: { pedido_de_credito: frm.doc.name },
		callback: (r) => {
			wrapper.html(entre_mc.render_plano_html(r.message || frm.doc.plano_de_amortizacao, frm.doc.currency));
		},
	});
}
