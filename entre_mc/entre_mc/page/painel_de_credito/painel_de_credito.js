// Copyright (c) 2026, Dércio Bobo and contributors
// For license information, please see license.txt

frappe.pages["painel-de-credito"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Painel de Crédito",
		single_column: true,
	});

	new EntreMcPainel(page);
};

const CURRENCY = "MZN";

class EntreMcPainel {
	constructor(page) {
		this.page = page;
		this.controls = {};
		this.render_shell();
		this.make_filtros();
		this.carregar();
	}

	render_shell() {
		this.inject_styles();

		this.page.main.html(`
			<div class="emc-painel">
				<section class="emc-painel-filtros" id="emc-painel-filtros">
					<button class="btn btn-default btn-sm emc-painel-limpar">${__("Limpar Filtros")}</button>
				</section>

				<section class="emc-resumo-cards" id="emc-painel-cards"></section>

				<div class="emc-painel-tabelas">
					<section>
						<h4>${__("Carteira em Risco")}</h4>
						<div class="emc-resumo-table-wrap">
							<table class="emc-resumo-table">
								<thead>
									<tr>
										<th>${__("Pedido")}</th>
										<th>${__("Cliente")}</th>
										<th class="emc-num">${__("Saldo do Crédito")}</th>
										<th class="emc-num">${__("Dívida")}</th>
										<th class="emc-num">${__("Em Risco")}</th>
									</tr>
								</thead>
								<tbody id="emc-painel-risco-rows"></tbody>
							</table>
						</div>
					</section>

					<section>
						<h4>${__("Créditos em Atraso")}</h4>
						<div class="emc-resumo-table-wrap">
							<table class="emc-resumo-table">
								<thead>
									<tr>
										<th>${__("Pedido")}</th>
										<th>${__("Cliente")}</th>
										<th>${__("Nº")}</th>
										<th>${__("Data Limite")}</th>
										<th class="emc-num">${__("Dias de Atraso")}</th>
										<th class="emc-num">${__("Total em Atraso")}</th>
									</tr>
								</thead>
								<tbody id="emc-painel-atraso-rows"></tbody>
							</table>
						</div>
					</section>
				</div>
			</div>
		`);

		this.$filtros = this.page.main.find("#emc-painel-filtros");
		this.$cards = this.page.main.find("#emc-painel-cards");
		this.$riscoRows = this.page.main.find("#emc-painel-risco-rows");
		this.$atrasoRows = this.page.main.find("#emc-painel-atraso-rows");

		this.$filtros.find(".emc-painel-limpar").on("click", () => {
			Object.values(this.controls).forEach((control) => control.set_value(""));
		});
	}

	make_filtros() {
		const campos = [
			{ fieldname: "cliente", label: __("Cliente"), fieldtype: "Link", options: "Cliente" },
			{ fieldname: "produto", label: __("Produto"), fieldtype: "Link", options: "Produto" },
			{
				fieldname: "finalidade",
				label: __("Finalidade"),
				fieldtype: "Select",
				options: "\nComercio\nAgricultura\nPecuaria\nIndústria\nServiços\nConsumo\nOutros",
			},
			{ fieldname: "data_inicio", label: __("Desembolsos de"), fieldtype: "Date" },
			{ fieldname: "data_fim", label: __("até"), fieldtype: "Date" },
		];

		campos.forEach((df) => {
			const $field = $(`<div class="emc-painel-filtro"></div>`).insertBefore(
				this.$filtros.find(".emc-painel-limpar")
			);
			const control = frappe.ui.form.make_control({
				df: { ...df, change: () => this.on_filtro_change() },
				parent: $field,
				render_input: true,
			});
			control.refresh();
			this.controls[df.fieldname] = control;
		});
	}

	on_filtro_change() {
		clearTimeout(this._timeout);
		this._timeout = setTimeout(() => this.carregar(), 300);
	}

	valores_filtro() {
		const valores = {};
		Object.entries(this.controls).forEach(([fieldname, control]) => {
			const value = control.get_value();
			if (value) valores[fieldname] = value;
		});
		return valores;
	}

	carregar() {
		frappe.call({
			method: "entre_mc.entre_mc.page.painel_de_credito.painel_de_credito.obter_painel",
			args: this.valores_filtro(),
			callback: (r) => r.message && this.render(r.message),
		});
	}

	render(data) {
		this.render_cards(data.cards);
		this.render_tabela_risco(data.carteira_em_risco);
		this.render_tabela_atraso(data.creditos_em_atraso);
	}

	render_cards(cards) {
		const items = [
			{ label: __("Saldo do Crédito"), value: format_currency(cards.saldo_do_credito, CURRENCY) },
			{
				label: __("Dívida"),
				value: format_currency(cards.divida, CURRENCY),
				warn: flt(cards.divida) > 0,
			},
			{
				label: __("Em Risco"),
				value: format_currency(cards.em_risco, CURRENCY),
				warn: flt(cards.em_risco) > 0,
			},
			{
				label: __("PAR %"),
				value: `${flt(cards.par_percent).toFixed(1)}%`,
				warn: flt(cards.par_percent) > 0,
			},
			{ label: __("Créditos Ativos"), value: cint(cards.num_ativos) },
			{
				label: __("Incumprimentos"),
				value: cint(cards.num_incumprimento),
				warn: cint(cards.num_incumprimento) > 0,
			},
			{ label: __("Desembolsado no Período"), value: format_currency(cards.desembolsado_periodo, CURRENCY) },
			{ label: __("Taxas Cobradas no Período"), value: format_currency(cards.taxas_periodo, CURRENCY) },
		];

		this.$cards.html(
			items
				.map(
					(c) => `
					<div class="emc-resumo-card${c.warn ? " emc-resumo-card--warn" : ""}">
						<span class="emc-resumo-card-label">${c.label}</span>
						<span class="emc-resumo-card-value">${c.value}</span>
					</div>`
				)
				.join("")
		);
	}

	render_tabela_risco(rows) {
		if (!rows || !rows.length) {
			this.$riscoRows.html(
				`<tr><td colspan="5" class="text-muted">${__("Sem créditos em risco para os filtros selecionados.")}</td></tr>`
			);
			return;
		}
		this.$riscoRows.html(
			rows
				.map(
					(r) => `
					<tr>
						<td><a href="/app/pedido-de-credito/${encodeURIComponent(r.name)}">${frappe.utils.escape_html(r.name)}</a></td>
						<td>${frappe.utils.escape_html(r.cliente || "")}</td>
						<td class="emc-num">${format_currency(r.saldo_do_credito, CURRENCY)}</td>
						<td class="emc-num">${format_currency(r.divida, CURRENCY)}</td>
						<td class="emc-num">${format_currency(r.em_risco, CURRENCY)}</td>
					</tr>`
				)
				.join("")
		);
	}

	render_tabela_atraso(rows) {
		if (!rows || !rows.length) {
			this.$atrasoRows.html(
				`<tr><td colspan="6" class="text-muted">${__("Sem prestações em atraso para os filtros selecionados.")}</td></tr>`
			);
			return;
		}
		this.$atrasoRows.html(
			rows
				.map(
					(r) => `
					<tr>
						<td><a href="/app/pedido-de-credito/${encodeURIComponent(r.parent)}">${frappe.utils.escape_html(r.parent)}</a></td>
						<td>${frappe.utils.escape_html(r.cliente || "")}</td>
						<td>${r.numero}</td>
						<td>${frappe.datetime.str_to_user(r.data_limite_pagamento)}</td>
						<td class="emc-num">${r.dias_atraso}</td>
						<td class="emc-num">${format_currency(r.total_em_atraso, CURRENCY)}</td>
					</tr>`
				)
				.join("")
		);
	}

	inject_styles() {
		if (document.getElementById("emc-painel-style")) return;
		const style = document.createElement("style");
		style.id = "emc-painel-style";
		style.textContent = `
			.emc-painel {
				max-width: 1100px;
				margin: 0 auto;
				padding: 8px 4px 48px;
				font-family: var(--emc-font-numeric);
				color: var(--emc-ink);
			}
			.emc-painel-filtros {
				display: flex;
				flex-wrap: wrap;
				align-items: flex-end;
				gap: 14px;
				background: var(--emc-paper);
				border: 1px solid var(--emc-line);
				border-top: 3px solid var(--emc-accent);
				border-radius: 6px;
				padding: 16px;
				margin-bottom: 18px;
			}
			.emc-painel-filtro {
				min-width: 160px;
			}
			.emc-painel-limpar {
				margin-bottom: 2px;
			}
			.emc-painel-tabelas {
				display: grid;
				grid-template-columns: 1fr 1fr;
				gap: 18px;
				margin-top: 22px;
			}
			.emc-painel-tabelas h4 {
				font-family: var(--emc-font-display);
				margin: 0 0 8px;
				color: var(--emc-accent-deep);
			}
			@media (max-width: 900px) {
				.emc-painel-tabelas {
					grid-template-columns: 1fr;
				}
			}
		`;
		document.head.appendChild(style);
	}
}
