// Copyright (c) 2026, Dércio Bobo and contributors
// For license information, please see license.txt

frappe.ui.form.on("Simulacao de Credito", {
	onload(frm) {
		if (frm.is_new() && !frm.doc.frequencia) {
			frappe.db.get_single_value("MC Settings", "frequencia_padrao").then((value) => {
				if (value) frm.set_value("frequencia", value);
			});
		}
	},

	refresh(frm) {
		render_preview(frm);
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
