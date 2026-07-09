// Copyright (c) 2026, Dércio Bobo and contributors
// For license information, please see license.txt

frappe.provide("entre_mc");

// Shared HTML renderer for a Plano de Amortização, used by both
// Simulação de Crédito (live pre-save preview) and Pedido de Crédito
// (post-approval schedule view).
entre_mc.render_plano_html = function (rows, currency) {
	if (!rows || !rows.length) {
		return `<div class="text-muted entre-mc-plano-empty">${__(
			"Preencha os campos acima para gerar o plano de amortização."
		)}</div>`;
	}

	let total_capital = 0;
	let total_juros = 0;
	let total_prestacao = 0;

	const body = rows
		.map((r) => {
			total_capital += flt(r.capital_mensal);
			total_juros += flt(r.juros_mensais);
			total_prestacao += flt(r.prestacao_total);
			const atrasado = r.status === "Atrasado";
			const pago = r.status === "Pago";
			const row_class = atrasado ? "entre-mc-atrasado" : pago ? "entre-mc-pago" : "";
			return `<tr class="${row_class}">
				<td>${r.numero || ""}</td>
				<td>${frappe.datetime.str_to_user(r.data_limite_pagamento) || ""}</td>
				<td class="text-right">${format_currency(r.capital_mensal, currency)}</td>
				<td class="text-right">${format_currency(r.juros_mensais, currency)}</td>
				<td class="text-right"><strong>${format_currency(r.prestacao_total, currency)}</strong></td>
				<td class="text-right">${format_currency(r.saldo, currency)}</td>
				${r.status ? `<td>${__(r.status)}</td>` : ""}
			</tr>`;
		})
		.join("");

	const has_status = !!rows[0].status;

	return `
		<div class="entre-mc-plano-wrapper">
			<table class="table table-bordered table-sm entre-mc-plano-table">
				<thead>
					<tr>
						<th>${__("Nº")}</th>
						<th>${__("Data Limite")}</th>
						<th class="text-right">${__("Capital")}</th>
						<th class="text-right">${__("Juros")}</th>
						<th class="text-right">${__("Prestação")}</th>
						<th class="text-right">${__("Saldo")}</th>
						${has_status ? `<th>${__("Estado")}</th>` : ""}
					</tr>
				</thead>
				<tbody>${body}</tbody>
				<tfoot>
					<tr>
						<th colspan="2">${__("Total")}</th>
						<th class="text-right">${format_currency(total_capital, currency)}</th>
						<th class="text-right">${format_currency(total_juros, currency)}</th>
						<th class="text-right">${format_currency(total_prestacao, currency)}</th>
						<th></th>
						${has_status ? "<th></th>" : ""}
					</tr>
				</tfoot>
			</table>
		</div>`;
};
