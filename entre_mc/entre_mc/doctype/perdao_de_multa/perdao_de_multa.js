// Copyright (c) 2026, Dércio Bobo and contributors
// For license information, please see license.txt

frappe.ui.form.on("Perdao De Multa", {
	onload(frm) {
		frm.set_query("pedido_de_credito", () => ({
			filters: { status: ["not in", ["", "Liquidado"]] },
		}));
	},

	refresh(frm) {
		if (frm.doc.docstatus === 0) remover_linhas_vazias(frm);
		toggle_botao_carregar(frm);
	},

	// O refresh não corre ao mudar um campo, por isso num documento novo/não
	// gravado o botão só apareceria depois de gravar.
	pedido_de_credito(frm) {
		toggle_botao_carregar(frm);
		aviso_recarregar(frm);
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

function toggle_botao_carregar(frm) {
	const label = __("Carregar Prestações em Atraso");
	frm.remove_custom_button(label);
	if (frm.doc.docstatus !== 0 || !frm.doc.pedido_de_credito) return;

	frm.add_custom_button(label, () => carregar_prestacoes(frm));
}

function remover_linhas_vazias(frm) {
	const linhas = (frm.doc.prestacoes || []).filter((p) => p.numero);
	if (linhas.length !== (frm.doc.prestacoes || []).length) {
		frm.doc.prestacoes = linhas;
		linhas.forEach((p, i) => (p.idx = i + 1));
		frm.refresh_field("prestacoes");
	}
}

function aviso_recarregar(frm) {
	// Só avisa se já houver prestações carregadas (ignora a linha vazia que o
	// Frappe cria) e limpa antes de mostrar, senão os avisos acumulam-se.
	frm.dashboard.clear_headline();
	if ((frm.doc.prestacoes || []).some((p) => p.numero)) {
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
			if (!frm.doc.perdoar_tudo && !frm.doc.periodo_de && !frm.doc.periodo_ate) {
				frm.dashboard.set_headline_alert(
					`<div class="text-muted">${__(
						"Sem período: carregada toda a Multa em aberto. Ajuste os valores se o perdão for parcial."
					)}</div>`,
					"yellow"
				);
			}
		},
	});
}
