// Copyright (c) 2026, Dércio Bobo and contributors
// For license information, please see license.txt

frappe.ui.form.on("Cliente", {
	refresh(frm) {
		if (frm.doc.proponente_de_origem) {
			frm.add_custom_button(__("Ver Proponente"), () => {
				frappe.set_route("Form", "Proponente", frm.doc.proponente_de_origem);
			});
		}

		render_resumo(frm);
	},
});

const BADGE_CLASS = {
	Desembolsado: "",
	"Em Pagamento": "",
	Liquidado: "emc-resumo-badge--ink",
	Incumprimento: "emc-resumo-badge--stamp",
};

function render_resumo(frm) {
	const wrapper = frm.fields_dict.resumo_html?.$wrapper;
	if (!wrapper) return;

	if (frm.is_new()) {
		wrapper.html(
			`<div class="emc-resumo-cliente"><div class="emc-resumo-empty">${__(
				"Grave o Cliente para ver o resumo de crédito."
			)}</div></div>`
		);
		return;
	}

	frappe.call({
		method: "entre_mc.entre_mc.doctype.cliente.cliente.obter_resumo",
		args: { cliente: frm.doc.name },
		callback: (r) => {
			if (r.message) wrapper.html(build_resumo_html(r.message, frm.doc.currency));
		},
	});
}

function build_resumo_html(data, currency) {
	const { pedidos, garantias, totais } = data;

	if (!totais.total_pedidos) {
		return `<div class="emc-resumo-cliente"><div class="emc-resumo-empty">${__(
			"Este cliente ainda não tem pedidos de crédito."
		)}</div></div>`;
	}

	const cards = [
		{ label: __("Créditos"), value: totais.total_pedidos },
		{ label: __("Ativos"), value: totais.ativos },
		{ label: __("Total Emprestado"), value: format_currency(totais.total_emprestado, currency) },
		{ label: __("Saldo em Dívida"), value: format_currency(totais.saldo_em_divida, currency) },
		{
			label: __("Incumprimento"),
			value: totais.incumprimento,
			warn: totais.incumprimento > 0,
		},
		{ label: __("Garantias Disponíveis"), value: totais.garantias_disponiveis },
	]
		.map(
			(c) => `
			<div class="emc-resumo-card${c.warn ? " emc-resumo-card--warn" : ""}">
				<span class="emc-resumo-card-label">${c.label}</span>
				<span class="emc-resumo-card-value">${c.value}</span>
			</div>`
		)
		.join("");

	const rows = pedidos
		.map((p) => {
			const estado = p.status || p.workflow_state;
			const badgeClass = BADGE_CLASS[p.status] ?? "";
			return `
				<tr>
					<td><a href="/app/pedido-de-credito/${encodeURIComponent(p.name)}">${p.name}</a></td>
					<td>${frappe.utils.escape_html(p.produto || "")}</td>
					<td class="emc-num">${format_currency(p.capital_solicitado, currency)}</td>
					<td><span class="emc-resumo-badge ${badgeClass}">${__(estado || "")}</span></td>
					<td class="emc-num">${format_currency(p.saldo_em_divida, currency)}</td>
					<td>${frappe.datetime.str_to_user(p.creation)}</td>
				</tr>`;
		})
		.join("");

	const garantiasLine = garantias.length
		? `<p style="margin-top:10px; font-family: var(--emc-font-mono); font-size: 12px; color: var(--emc-ink-soft);">
			${__("Garantias")}: ${garantias
				.map((g) => `${g.name} (${__(g.status)})`)
				.join(" · ")}
		</p>`
		: "";

	return `
		<div class="emc-resumo-cliente">
			<div class="emc-resumo-cards">${cards}</div>
			<div class="emc-resumo-table-wrap">
				<table class="emc-resumo-table">
					<thead>
						<tr>
							<th>${__("Pedido")}</th>
							<th>${__("Produto")}</th>
							<th class="emc-num">${__("Capital")}</th>
							<th>${__("Estado")}</th>
							<th class="emc-num">${__("Saldo")}</th>
							<th>${__("Data")}</th>
						</tr>
					</thead>
					<tbody>${rows}</tbody>
				</table>
			</div>
			${garantiasLine}
		</div>`;
}
