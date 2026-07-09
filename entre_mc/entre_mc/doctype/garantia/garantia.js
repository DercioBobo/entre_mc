// Copyright (c) 2026, Dércio Bobo and contributors
// For license information, please see license.txt

frappe.ui.form.on("Garantia", {
	refresh(frm) {
		render_gallery(frm);
	},
});

frappe.ui.form.on("Item De Garantia", {
	itens_add(frm) {
		render_gallery(frm);
	},
	itens_remove(frm) {
		render_gallery(frm);
	},
	nome(frm) {
		render_gallery(frm);
	},
	categoria(frm) {
		render_gallery(frm);
	},
	estado(frm) {
		render_gallery(frm);
	},
	valor_de_mercado(frm) {
		render_gallery(frm);
	},
	imagem(frm) {
		render_gallery(frm);
	},
});

function render_gallery(frm) {
	const wrapper = frm.fields_dict.galeria_html?.$wrapper;
	if (!wrapper) return;
	wrapper.html(entre_mc.render_garantia_gallery_html(frm.doc.itens, frm.doc.currency));
}
