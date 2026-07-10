// Copyright (c) 2026, Dércio Bobo and contributors
// For license information, please see license.txt

frappe.ui.form.on("Reembolso", {
	refresh(frm) {
		render_contexto(frm);
	},

	pedido_de_credito(frm) {
		render_contexto(frm);
	},
});

function render_contexto(frm) {
	const wrapper = frm.fields_dict.contexto_html?.$wrapper;
	if (!wrapper) return;

	if (!frm.doc.pedido_de_credito) {
		wrapper.html(
			`<div class="emc-resumo-cliente"><div class="emc-resumo-empty">${__(
				"Selecione um Pedido de Crédito para ver o saldo e as prestações em aberto."
			)}</div></div>`
		);
		return;
	}

	frappe.call({
		method: "entre_mc.entre_mc.doctype.reembolso.reembolso.obter_contexto",
		args: { pedido_de_credito: frm.doc.pedido_de_credito },
		callback: (r) => {
			if (r.message) wrapper.html(build_contexto_html(r.message, frm.doc.currency));
		},
	});
}

function build_contexto_html(data, currency) {
	const { saldo_em_divida, proxima_prestacao, total_em_atraso, plano } = data;

	const cards = [
		{ label: __("Saldo em Dívida"), value: format_currency(saldo_em_divida, currency) },
		proxima_prestacao
			? {
					label: __("Próxima Prestação (Nº {0})", [proxima_prestacao.numero]),
					value: format_currency(proxima_prestacao.valor_em_falta, currency),
					warn: proxima_prestacao.status === "Atrasado",
			  }
			: { label: __("Próxima Prestação"), value: __("Nenhuma") },
	];

	if (flt(total_em_atraso) > 0) {
		cards.push({
			label: __("Total em Atraso"),
			value: format_currency(total_em_atraso, currency),
			warn: true,
		});
	}

	const cards_html = cards
		.map(
			(c) => `
			<div class="emc-resumo-card${c.warn ? " emc-resumo-card--warn" : ""}">
				<span class="emc-resumo-card-label">${c.label}</span>
				<span class="emc-resumo-card-value">${c.value}</span>
			</div>`
		)
		.join("");

	const prazo_html = proxima_prestacao?.data_limite_pagamento
		? `<p style="margin-top:10px; font-family: var(--emc-font-numeric); font-size: 12px; color: var(--emc-ink-soft);">
			${__("Data limite da próxima prestação")}: ${frappe.datetime.str_to_user(
				proxima_prestacao.data_limite_pagamento
			)}
		</p>`
		: "";

	return `
		<div class="emc-resumo-cliente">
			<div class="emc-resumo-cards">${cards_html}</div>
			${prazo_html}
			${entre_mc.render_plano_html(plano, currency)}
		</div>`;
}
