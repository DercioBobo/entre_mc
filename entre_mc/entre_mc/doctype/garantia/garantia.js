// Copyright (c) 2026, Dércio Bobo and contributors
// For license information, please see license.txt

frappe.ui.form.on("Garantia", {
	refresh(frm) {
		render_gallery(frm);

		if (frm.is_new() || frm.doc.status !== "Disponível") return;

		frm.add_custom_button(__("Executar Garantia"), () => {
			frappe.new_doc("Execucao De Garantia", null, (doc) => {
				doc.garantia = frm.doc.name;
				doc.cliente = frm.doc.cliente;
			});
		});

		frm.add_custom_button(__("Devolver Garantia"), () => {
			frappe.new_doc("Devolucao Da Garantia", null, (doc) => {
				doc.garantia = frm.doc.name;
				doc.cliente = frm.doc.cliente;
			});
		});
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
