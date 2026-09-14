// Copyright (c) 2026, Dércio Bobo and contributors
// For license information, please see license.txt

frappe.ui.form.on("Perdao De Multa", {
	onload(frm) {
		frm.set_query("pedido_de_credito", () => ({
			filters: { status: ["not in", ["", "Liquidado"]] },
		}));
	},

	refresh(frm) {
		if (frm.doc.docstatus !== 0 || !frm.doc.pedido_de_credito) return;

		frm.add_custom_button(__("Carregar Prestações em Atraso"), () => carregar_prestacoes(frm));
	},

	// Reflete a mudança no cabeçalho em vez de recarregar sozinho - o utilizador
	// pode estar a ajustar valores manualmente na tabela e um recarrego
	// automático apagaria isso sem aviso.
	periodo_de(frm) {
		aviso_recarregar(frm);
	},
	periodo_ate(frm) {
		aviso_recarregar(frm);
	},
	perdoar_tudo(frm) {
		aviso_recarregar(frm);
	},
});

function aviso_recarregar(frm) {
	if (frm.doc.prestacoes && frm.doc.prestacoes.length) {
		frm.dashboard.set_headline_alert(
			`<div class="text-muted">${__(
				"Opções alteradas - clique novamente em \"Carregar Prestações em Atraso\" para recalcular os valores."
			)}</div>`
		);
	}
}

function carregar_prestacoes(frm) {
	frappe.call({
		method: "entre_mc.entre_mc.doctype.perdao_de_multa.perdao_de_multa.carregar_prestacoes_em_atraso",
		args: {
			pedido_de_credito: frm.doc.pedido_de_credito,
			periodo_de: frm.doc.periodo_de,
			periodo_ate: frm.doc.periodo_ate,
			perdoar_tudo: frm.doc.perdoar_tudo,
		},
		callback: (r) => {
			const prestacoes = r.message || [];
			if (!prestacoes.length) {
				frappe.msgprint(
					__("Não há prestações com Multa ou Juros de Mora em aberto para este Pedido de Crédito nas condições indicadas.")
				);
				return;
			}
			frm.clear_table("prestacoes");
			prestacoes.forEach((p) => {
				const row = frm.add_child("prestacoes");
				row.numero = p.numero;
				row.data_limite_pagamento = p.data_limite_pagamento;
				row.multa_em_aberto = p.multa_em_aberto;
				row.dias_no_periodo = p.dias_no_periodo;
				row.valor_perdoado_multa = p.valor_perdoado_multa;
				row.mora_em_aberto = p.mora_em_aberto;
				row.valor_perdoado_mora = p.valor_perdoado_mora;
			});
			frm.refresh_field("prestacoes");
			frm.dashboard.clear_headline();
		},
	});
}
