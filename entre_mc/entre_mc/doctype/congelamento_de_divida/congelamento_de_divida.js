// Copyright (c) 2026, Dércio Bobo and contributors
// For license information, please see license.txt

frappe.ui.form.on("Congelamento De Divida", {
	setup(frm) {
		frm.set_query("pedido_de_credito", () => ({
			filters: { status: ["in", ["Em Curso", "Incumprimento"]], congelado: 0 },
		}));
	},

	refresh(frm) {
		if (frm.doc.docstatus === 0) {
			frm.set_intro(
				__(
					"Ao submeter, o crédito deixa de gerar Multa e Juros de Mora. O Valor Congelado é calculado ao gravar."
				),
				"blue"
			);
		}

		if (frm.doc.docstatus === 1 && !frm.doc.data_do_descongelamento) {
			frm.set_intro(
				__(
					"Congelamento ativo. Use \"Descongelar\" para o crédito voltar ao normal sem cobrar os dias congelados. Cancelar anula o congelamento e cobra esses dias."
				),
				"blue"
			);
			if (frm.perm[0] && frm.perm[0].submit) {
				frm.add_custom_button(__("Descongelar"), () => descongelar(frm)).addClass("btn-primary");
			}
		}

		if (frm.doc.docstatus === 1 && frm.doc.data_do_descongelamento) {
			frm.set_intro(
				__("Congelamento terminado em {0}.", [frappe.datetime.str_to_user(frm.doc.data_do_descongelamento)]),
				"green"
			);
		}
	},
});

function descongelar(frm) {
	frappe.prompt(
		[
			{
				fieldname: "data",
				label: __("Data do Descongelamento"),
				fieldtype: "Date",
				default: frappe.datetime.get_today(),
				reqd: 1,
				description: __("A Multa volta a contar a partir deste dia. Os dias congelados não são cobrados."),
			},
			{ fieldname: "motivo", label: __("Motivo"), fieldtype: "Small Text", reqd: 1 },
		],
		(values) => {
			frappe.call({
				method: "entre_mc.entre_mc.doctype.congelamento_de_divida.congelamento_de_divida.descongelar",
				args: { congelamento: frm.doc.name, data: values.data, motivo: values.motivo },
				freeze: true,
				callback: () => {
					frappe.show_alert({ message: __("Dívida descongelada."), indicator: "green" });
					frm.reload_doc();
				},
			});
		},
		__("Descongelar Dívida"),
		__("Descongelar")
	);
}
