// Copyright (c) 2026, Dércio Bobo and contributors
// For license information, please see license.txt

frappe.ui.form.on("Reestruturacao De Credito", {
	setup(frm) {
		frm.set_query("pedido_de_credito", () => ({
			filters: { status: ["in", ["Em Curso", "Incumprimento"]] },
		}));
	},

	onload(frm) {
		// Criado a partir do Pedido (botão Criar): o campo já vem preenchido.
		if (frm.is_new() && frm.doc.pedido_de_credito && !frm.doc.nova_frequencia) {
			frm.trigger("pedido_de_credito");
		}
	},

	refresh(frm) {
		if (frm.doc.docstatus === 0) {
			frm.set_intro(
				__(
					"Grave para calcular o Saldo em Aberto e o Novo Plano. Ao submeter, o novo plano substitui as prestações por pagar do Pedido; o plano anterior fica guardado aqui."
				),
				"blue"
			);
		}
	},

	// Parte das condições em vigor - o utilizador só altera o que foi acordado.
	pedido_de_credito(frm) {
		if (!frm.doc.pedido_de_credito) return;
		frappe.call({
			method: "entre_mc.entre_mc.doctype.reestruturacao_de_credito.reestruturacao_de_credito.condicoes_atuais",
			args: { pedido_de_credito: frm.doc.pedido_de_credito },
			callback: (r) => {
				if (!r.message) return;
				frm.set_value("nova_taxa_de_juros", r.message.taxa_de_juros);
				frm.set_value("nova_frequencia", r.message.frequencia);
				if (!frm.doc.novo_prazo) frm.set_value("novo_prazo", r.message.prazo);
			},
		});
	},
});
