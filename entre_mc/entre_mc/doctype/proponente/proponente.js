// Copyright (c) 2026, Dércio Bobo and contributors
// For license information, please see license.txt

frappe.provide("entre_mc");

// Opens a new, unsaved Cliente form pre-filled from a Proponente. Nothing is
// inserted here - the user completes and saves the real Cliente form
// themselves, so whatever fields are mandatory on Cliente are always
// enforced correctly, with no need to mirror them onto Proponente.
entre_mc.abrir_cliente_a_partir_do_proponente = function (proponente) {
	frappe.new_doc("Cliente", null, (doc) => {
		doc.proponente_de_origem = proponente.name;
		doc.nome_completo = proponente.nome_completo;
		doc.data_de_nascimento = proponente.data_de_nascimento;
		doc.ocupacao = proponente.ocupacao;
		doc.local_de_trabalho = proponente.local_de_trabalho;
		doc.rendimento_mensal = proponente.rendimento_mensal;
	});
};

frappe.ui.form.on("Proponente", {
	refresh(frm) {
		if (!frm.is_new() && !frm.doc.convertido_em_cliente) {
			frm.add_custom_button(__("Converter em Cliente"), () => {
				entre_mc.abrir_cliente_a_partir_do_proponente(frm.doc);
			}).addClass("btn-primary");
		}

		if (frm.doc.convertido_em_cliente && frm.doc.cliente) {
			frm.add_custom_button(__("Ver Cliente"), () => {
				frappe.set_route("Form", "Cliente", frm.doc.cliente);
			});
		}
	},
});
