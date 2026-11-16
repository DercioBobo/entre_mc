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

// Separadores da lista de créditos: [chave, rótulo, filtro sobre o crédito].
const SEPARADORES = [
	["todos", "Todos", () => true],
	["em_dia", "Em dia", (c) => c.situacao === "Em dia"],
	["em_atraso", "Em atraso", (c) => c.situacao === "Em atraso"],
	["incumprimento", "Incumprimento", (c) => c.situacao === "Incumprimento"],
	["congelados", "Congelados", (c) => c.congelado],
	["reestruturados", "Reestruturados", (c) => c.reestruturado],
	["liquidados", "Liquidados", (c) => c.situacao === "Liquidado"],
];

const COLUNAS = [
	["cliente", "Cliente", "texto"],
	["name", "Pedido", "texto"],
	["situacao", "Situação", "texto"],
	["data_de_desembolso", "Desembolso", "data"],
	["capital_solicitado", "Crédito", "moeda"],
	["saldo_do_credito", "Falta pagar", "moeda"],
	["divida", "Em atraso", "moeda"],
	["multa_e_mora", "Multa + Mora", "moeda"],
	["dias_atraso", "Dias", "numero"],
	["proximo_vencimento", "Próx. vencimento", "data"],
];

class EntreMcPainel {
	constructor(page) {
		this.page = page;
		this.controls = {};
		this.creditos = [];
		this.separador = "todos";
		this.pesquisa = "";
		this.ordem = { campo: "dias_atraso", desc: true };
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

				<section class="emc-painel-lista">
					<div class="emc-painel-lista-topo">
						<h4>${__("Créditos")}</h4>
						<input type="text" class="form-control input-sm emc-painel-pesquisa"
							placeholder="${__("Procurar cliente, pedido, produto ou promotor…")}">
					</div>
					<div class="emc-painel-separadores" id="emc-painel-separadores"></div>
					<div class="emc-resumo-table-wrap">
						<table class="emc-resumo-table emc-painel-creditos">
							<thead><tr id="emc-painel-cabecalho"></tr></thead>
							<tbody id="emc-painel-creditos-rows"></tbody>
							<tfoot id="emc-painel-creditos-total"></tfoot>
						</table>
					</div>
					<p class="emc-painel-nota">${__("Clique num crédito para abrir a sua ficha.")}</p>
				</section>
			</div>
		`);

		this.$filtros = this.page.main.find("#emc-painel-filtros");
		this.$cards = this.page.main.find("#emc-painel-cards");
		this.$separadores = this.page.main.find("#emc-painel-separadores");
		this.$cabecalho = this.page.main.find("#emc-painel-cabecalho");
		this.$rows = this.page.main.find("#emc-painel-creditos-rows");
		this.$total = this.page.main.find("#emc-painel-creditos-total");

		this.$filtros.find(".emc-painel-limpar").on("click", () => {
			Object.values(this.controls).forEach((control) => control.set_value(""));
		});

		this.page.main.find(".emc-painel-pesquisa").on("input", (e) => {
			this.pesquisa = (e.currentTarget.value || "").trim().toLowerCase();
			this.render_creditos();
		});

		this.$separadores.on("click", "[data-separador]", (e) => {
			this.separador = $(e.currentTarget).data("separador");
			// Os liquidados só são pedidos ao servidor quando alguém os quer ver.
			if (this.separador === "liquidados" && !this.com_liquidados) {
				this.com_liquidados = true;
				this.carregar();
				return;
			}
			this.render_separadores();
			this.render_creditos();
		});

		this.$cabecalho.on("click", "[data-campo]", (e) => {
			const campo = $(e.currentTarget).data("campo");
			this.ordem = { campo, desc: this.ordem.campo === campo ? !this.ordem.desc : true };
			this.render_cabecalho();
			this.render_creditos();
		});

		this.$rows.on("click", "tr[data-pedido]", (e) => {
			if ($(e.target).closest("a").length) return;
			frappe.set_route("ficha-do-credito", $(e.currentTarget).data("pedido"));
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
		if (this.com_liquidados) valores.incluir_liquidados = 1;
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
		this.creditos = data.creditos || [];
		this.render_cards(data.cards);
		this.render_separadores();
		this.render_cabecalho();
		this.render_creditos();
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
				label: __("Com Atraso"),
				value: cint(cards.num_em_atraso),
				warn: cint(cards.num_em_atraso) > 0,
			},
			{
				label: __("Incumprimentos"),
				value: cint(cards.num_incumprimento),
				warn: cint(cards.num_incumprimento) > 0,
			},
			{ label: __("Congelados"), value: cint(cards.num_congelados) },
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

	render_separadores() {
		this.$separadores.html(
			SEPARADORES.map(([chave, rotulo, filtro]) => {
				// Antes de serem pedidos ao servidor, não se sabe quantos liquidados há.
				const total =
					chave === "liquidados" && !this.com_liquidados ? "" : ` <span>${this.creditos.filter(filtro).length}</span>`;
				return `<button class="emc-painel-separador${chave === this.separador ? " is-ativo" : ""}"
					data-separador="${chave}">${__(rotulo)}${total}</button>`;
			}).join("")
		);
	}

	render_cabecalho() {
		this.$cabecalho.html(
			COLUNAS.map(([campo, rotulo, tipo]) => {
				const seta = this.ordem.campo === campo ? (this.ordem.desc ? " ↓" : " ↑") : "";
				return `<th class="${tipo === "moeda" || tipo === "numero" ? "emc-num" : ""}" data-campo="${campo}">${__(
					rotulo
				)}${seta}</th>`;
			}).join("")
		);
	}

	creditos_visiveis() {
		const filtro = SEPARADORES.find(([chave]) => chave === this.separador)[2];
		const termo = this.pesquisa;
		const { campo, desc } = this.ordem;
		const tipo = COLUNAS.find(([c]) => c === campo)[2];

		return this.creditos
			.filter(filtro)
			.filter(
				(c) =>
					!termo ||
					[c.cliente, c.name, c.produto, c.promotor].some((v) => (v || "").toLowerCase().includes(termo))
			)
			.sort((a, b) => {
				let x = a[campo];
				let y = b[campo];
				let r;
				if (tipo === "moeda" || tipo === "numero") {
					r = flt(x) - flt(y);
				} else {
					r = String(x || "").localeCompare(String(y || ""), "pt");
				}
				return desc ? -r : r;
			});
	}

	render_creditos() {
		const esc = frappe.utils.escape_html;
		const moeda = (v) => (flt(v) ? format_currency(v, CURRENCY) : "—");
		const data = (v) => (v ? frappe.datetime.str_to_user(v) : "—");
		const rows = this.creditos_visiveis();

		if (!rows.length) {
			this.$rows.html(
				`<tr><td colspan="${COLUNAS.length}" class="text-muted">${__("Sem créditos para os filtros selecionados.")}</td></tr>`
			);
			this.$total.html("");
			return;
		}

		const classe_situacao = {
			"Em dia": "",
			"Em atraso": " emc-resumo-badge--stamp",
			Incumprimento: " emc-resumo-badge--stamp",
			Liquidado: " emc-resumo-badge--ink",
		};

		this.$rows.html(
			rows
				.map((c) => {
					const marcas =
						(c.congelado ? `<span class="emc-resumo-badge emc-painel-badge--gelo">${__("Congelado")}</span>` : "") +
						(c.reestruturado ? `<span class="emc-resumo-badge emc-resumo-badge--ink">${__("Reestruturado")}</span>` : "");
					return `
					<tr data-pedido="${esc(c.name)}" class="${c.dias_atraso > 0 ? "emc-painel-linha--atraso" : ""}">
						<td>
							<strong>${esc(c.cliente || "")}</strong>
							<div class="emc-painel-sub">${esc(c.produto || "")}${c.promotor ? " · " + esc(c.promotor) : ""}</div>
						</td>
						<td><a href="/app/pedido-de-credito/${encodeURIComponent(c.name)}">${esc(c.name)}</a></td>
						<td>
							<span class="emc-resumo-badge${classe_situacao[c.situacao] || ""}">${__(c.situacao)}</span>
							${marcas}
						</td>
						<td>${data(c.data_de_desembolso)}</td>
						<td class="emc-num">${moeda(c.capital_solicitado)}</td>
						<td class="emc-num"><strong>${moeda(c.saldo_do_credito)}</strong></td>
						<td class="emc-num${flt(c.divida) > 0 ? " emc-painel-alerta" : ""}">${moeda(c.divida)}</td>
						<td class="emc-num">${moeda(c.multa_e_mora)}</td>
						<td class="emc-num${c.dias_atraso > 0 ? " emc-painel-alerta" : ""}">${c.dias_atraso || "—"}</td>
						<td>${data(c.proximo_vencimento)}</td>
					</tr>`;
				})
				.join("")
		);

		const soma = (campo) => rows.reduce((t, c) => t + flt(c[campo]), 0);
		this.$total.html(`
			<tr>
				<td colspan="4">${__("{0} créditos", [rows.length])}</td>
				<td class="emc-num">${moeda(soma("capital_solicitado"))}</td>
				<td class="emc-num">${moeda(soma("saldo_do_credito"))}</td>
				<td class="emc-num">${moeda(soma("divida"))}</td>
				<td class="emc-num">${moeda(soma("multa_e_mora"))}</td>
				<td colspan="2"></td>
			</tr>`);
	}

	inject_styles() {
		if (document.getElementById("emc-painel-style")) return;
		const style = document.createElement("style");
		style.id = "emc-painel-style";
		style.textContent = `
			.emc-painel {
				max-width: 1240px;
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
			.emc-painel-lista {
				margin-top: 22px;
			}
			.emc-painel-lista-topo {
				display: flex;
				justify-content: space-between;
				align-items: center;
				gap: 12px;
				flex-wrap: wrap;
				margin-bottom: 10px;
			}
			.emc-painel-lista h4 {
				font-family: var(--emc-font-display);
				margin: 0;
				color: var(--emc-accent-deep);
			}
			.emc-painel-pesquisa {
				max-width: 340px;
			}
			.emc-painel-separadores {
				display: flex;
				flex-wrap: wrap;
				gap: 6px;
				margin-bottom: 10px;
			}
			.emc-painel-separador {
				border: 1px solid var(--emc-line);
				background: var(--emc-paper);
				color: var(--emc-ink-soft);
				border-radius: 14px;
				padding: 3px 12px;
				font-size: 12px;
				font-weight: 600;
			}
			.emc-painel-separador span {
				margin-left: 4px;
				font-variant-numeric: tabular-nums;
				opacity: 0.75;
			}
			.emc-painel-separador.is-ativo {
				background: var(--emc-accent);
				border-color: var(--emc-accent);
				color: #f2fbf5;
			}
			.emc-painel-creditos thead th[data-campo] {
				cursor: pointer;
				user-select: none;
			}
			.emc-painel-creditos tbody tr[data-pedido] {
				cursor: pointer;
			}
			.emc-painel-creditos tbody tr.emc-painel-linha--atraso td {
				background: #fbeee9;
			}
			.emc-painel-creditos tfoot td {
				padding: 8px 10px;
				font-weight: 700;
				border-top: 2px solid var(--emc-accent);
				background: var(--emc-paper);
				white-space: nowrap;
				font-variant-numeric: tabular-nums;
			}
			.emc-painel-sub {
				font-size: 11px;
				color: var(--emc-ink-soft);
			}
			.emc-painel-alerta {
				color: var(--emc-stamp);
				font-weight: 700;
			}
			.emc-painel-badge--gelo {
				background: #dcebf7;
				color: #1d4f7a;
			}
			.emc-painel-nota {
				margin-top: 8px;
				font-size: 12px;
				color: var(--emc-ink-soft);
			}
		`;
		document.head.appendChild(style);
	}
}
