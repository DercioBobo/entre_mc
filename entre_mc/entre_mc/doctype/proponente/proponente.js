// Copyright (c) 2026, Dércio Bobo and contributors
// For license information, please see license.txt

frappe.ui.form.on("Proponente", {
	refresh(frm) {
		if (!frm.is_new() && !frm.doc.convertido_em_cliente) {
			frm.add_custom_button(__("Converter em Cliente"), () => {
				frappe.confirm(
					__("Criar um registo de Cliente a partir deste Proponente?"),
					() => {
						frappe.call({
							method: "entre_mc.entre_mc.doctype.proponente.proponente.converter_em_cliente",
							args: { proponente: frm.doc.name },
							freeze: true,
							callback: (r) => {
								if (r.message) {
									frappe.set_route("Form", "Cliente", r.message);
								}
							},
						});
					}
				);
			}).addClass("btn-primary");
		}

		if (frm.doc.convertido_em_cliente && frm.doc.cliente) {
			frm.add_custom_button(__("Ver Cliente"), () => {
				frappe.set_route("Form", "Cliente", frm.doc.cliente);
			});
		}
	},
});
