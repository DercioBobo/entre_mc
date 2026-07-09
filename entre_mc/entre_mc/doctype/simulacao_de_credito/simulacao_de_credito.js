// Copyright (c) 2026, Dércio Bobo and contributors
// For license information, please see license.txt

frappe.ui.form.on("Simulacao De Credito", {
	onload(frm) {
		if (frm.is_new() && !frm.doc.frequencia) {
			frappe.db.get_single_value("MC Settings", "frequencia_padrao").then((value) => {
				if (value) frm.set_value("frequencia", value);
			});
		}
	},

	refresh(frm) {
		render_preview(frm);

		frm.add_custom_button(__("Simulador Rápido"), () => {
			frappe.set_route("simulador-de-credito");
		});

		if (frm.is_new()) return;

		if (frm.doc.pedido_de_credito) {
			frm.add_custom_button(__("Ver Pedido de Crédito"), () => {
				frappe.set_route("Form", "Pedido De Credito", frm.doc.pedido_de_credito);
			});
			return;
		}

		frm.add_custom_button(__("Converter em Cliente e Criar Pedido de Crédito"), () => {
			frappe.db.get_doc("Proponente", frm.doc.proponente).then((proponente) => {
				if (proponente.convertido_em_cliente) {
					frappe.confirm(
						__(
							"Isto cria um Pedido de Crédito pré-preenchido a partir desta simulação. Continuar?"
						),
						() => {
							frappe.call({
								method:
									"entre_mc.entre_mc.doctype.simulacao_de_credito.simulacao_de_credito.criar_pedido_de_credito",
								args: { simulacao: frm.doc.name },
								freeze: true,
								callback: (r) => {
									if (r.message) {
										frappe.set_route("Form", "Pedido De Credito", r.message);
									}
								},
							});
						}
					);
				} else {
					frappe.msgprint({
						title: __("Cliente ainda não existe"),
						message: __(
							"Este Proponente ainda não é Cliente. Crie o registo de Cliente, complete os dados e grave; depois volte a esta simulação e clique novamente neste botão para criar o Pedido de Crédito."
						),
						primary_action: {
							label: __("Criar Cliente"),
							action: () => {
								entre_mc.abrir_cliente_a_partir_do_proponente(proponente);
							},
						},
					});
				}
			});
		}).addClass("btn-primary");
	},

	produto(frm) {
		render_preview(frm);
	},
	capital_solicitado(frm) {
		render_preview(frm);
	},
	taxa_de_juros(frm) {
		render_preview(frm);
	},
	prazo(frm) {
		render_preview(frm);
	},
	frequencia(frm) {
		render_preview(frm);
	},
});

let preview_timeout = null;

function render_preview(frm) {
	const wrapper = frm.fields_dict.pre_visualizacao_html?.$wrapper;
	if (!wrapper) return;

	// A saved doc already has the authoritative plan in the child table - use it directly.
	if (!frm.is_dirty() && frm.doc.plano_de_amortizacao?.length) {
		wrapper.html(entre_mc.render_plano_html(frm.doc.plano_de_amortizacao, frm.doc.currency));
		return;
	}

	const { produto, capital_solicitado, taxa_de_juros, prazo, frequencia } = frm.doc;
	if (!produto || !capital_solicitado || !taxa_de_juros || !prazo || !frequencia) {
		wrapper.html(entre_mc.render_plano_html([]));
		return;
	}

	clearTimeout(preview_timeout);
	preview_timeout = setTimeout(() => {
		frappe.call({
			method: "entre_mc.entre_mc.doctype.simulacao_de_credito.simulacao_de_credito.preview_plano",
			args: { produto, capital_solicitado, taxa_de_juros, prazo, frequencia },
			callback: (r) => {
				wrapper.html(entre_mc.render_plano_html(r.message));
			},
			error: () => {
				wrapper.html(
					`<div class="text-danger">${__("Não foi possível calcular o plano - verifique os limites do produto.")}</div>`
				);
			},
		});
	}, 400);
}
