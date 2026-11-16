// Copyright (c) 2026, Dércio Bobo and contributors
// For license information, please see license.txt

frappe.ui.form.on("Prospecto", {
	refresh(frm) {
		if (frm.is_new()) return;

		if (!frm.doc.proponente && frm.doc.estado !== "Perdido") {
			// Abre um Proponente novo, por gravar, pré-preenchido - os campos
			// obrigatórios do Proponente (BI, data de nascimento) são pedidos
			// pelo próprio formulário.
			frm.add_custom_button(__("Converter em Proponente"), () => {
				frappe.new_doc("Proponente", null, (doc) => {
					doc.prospecto_de_origem = frm.doc.name;
					doc.nome_completo = frm.doc.nome_completo;
					doc.ocupacao = frm.doc.ocupacao;
					doc.provincia = frm.doc.provincia;
					doc.distrito = frm.doc.distrito;
					doc.bairro = frm.doc.bairro;
					doc.endereco = frm.doc.endereco;
					doc.numero_da_casa = frm.doc.numero_da_casa;
					doc.quarteirao = frm.doc.quarteirao;
				});
			}).addClass("btn-primary");
		}

		if (frm.doc.proponente) {
			frm.add_custom_button(__("Ver Proponente"), () => {
				frappe.set_route("Form", "Proponente", frm.doc.proponente);
			});
		}
		if (frm.doc.cliente) {
			frm.add_custom_button(__("Ver Cliente"), () => {
				frappe.set_route("Form", "Cliente", frm.doc.cliente);
			});
		}
	},
});
