// Copyright (c) 2026, Dércio Bobo and contributors
// For license information, please see license.txt

frappe.pages["ficha-do-credito"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Ficha do Crédito"),
		single_column: true,
	});
	wrapper.ficha = new EntreMcFicha(page);
};

// /app/ficha-do-credito/<Pedido De Credito> - também ao voltar à página já aberta.
frappe.pages["ficha-do-credito"].on_page_show = function (wrapper) {
	const pedido = frappe.get_route()[1];
	if (wrapper.ficha && pedido) wrapper.ficha.abrir(decodeURIComponent(pedido));
};

const FICHA_CURRENCY = "MZN";

class EntreMcFicha {
	constructor(page) {
		this.page = page;
		this.controls = {};
		this.mostrar_vencimentos = true;
		this.inject_styles();
		this.render_shell();
		this.make_controlos();
	}

	render_shell() {
		this.page.main.html(`
			<div class="emc-ficha">
				<section class="emc-ficha-barra" id="emc-ficha-barra">
					<div class="emc-ficha-atalhos">
						<button class="btn btn-default btn-xs" data-dias="-30">${__("−30 dias")}</button>
						<button class="btn btn-default btn-xs" data-dias="-1">${__("−1 dia")}</button>
						<button class="btn btn-default btn-xs" data-dias="hoje">${__("Hoje")}</button>
						<button class="btn btn-default btn-xs" data-dias="1">${__("+1 dia")}</button>
						<button class="btn btn-default btn-xs" data-dias="30">${__("+30 dias")}</button>
					</div>
				</section>
				<div id="emc-ficha-corpo">
					<div class="emc-resumo-empty">${__("Escolha um Pedido de Crédito para ver a sua ficha.")}</div>
				</div>
			</div>
		`);
		this.$barra = this.page.main.find("#emc-ficha-barra");
		this.$corpo = this.page.main.find("#emc-ficha-corpo");

		this.$barra.on("click", "[data-dias]", (e) => {
			const dias = $(e.currentTarget).data("dias");
			const atual = this.controls.data.get_value() || frappe.datetime.get_today();
			this.controls.data.set_value(
				dias === "hoje" ? frappe.datetime.get_today() : frappe.datetime.add_days(atual, cint(dias))
			);
		});

		this.$corpo.on("change", "#emc-ficha-vencimentos", (e) => {
			this.mostrar_vencimentos = e.currentTarget.checked;
			this.render_cronologia();
		});
	}

	make_controlos() {
		const campos = [
			{
				fieldname: "pedido",
				label: __("Pedido de Crédito"),
				fieldtype: "Link",
				options: "Pedido De Credito",
				get_query: () => ({ filters: { status: ["!=", ""] } }),
			},
			{
				fieldname: "data",
				label: __("Situação em"),
				fieldtype: "Date",
				default: frappe.datetime.get_today(),
			},
		];
		campos.forEach((df) => {
			const $field = $(`<div class="emc-ficha-campo"></div>`).insertBefore(this.$barra.find(".emc-ficha-atalhos"));
			const control = frappe.ui.form.make_control({
				df: { ...df, change: () => this.on_change() },
				parent: $field,
				render_input: true,
			});
			control.refresh();
			if (df.default) control.set_value(df.default);
			this.controls[df.fieldname] = control;
		});
	}

	abrir(pedido) {
		if (this.controls.pedido.get_value() !== pedido) this.controls.pedido.set_value(pedido);
	}

	on_change() {
		clearTimeout(this._timeout);
		this._timeout = setTimeout(() => this.carregar(), 250);
	}

	carregar() {
		const pedido = this.controls.pedido.get_value();
		if (!pedido) return;
		const data = this.controls.data.get_value() || frappe.datetime.get_today();
		const chave = `${pedido}|${data}`;
		if (chave === this._chave) return;
		this._chave = chave;

		if (frappe.get_route()[1] !== pedido) {
			frappe.set_route("ficha-do-credito", pedido);
		}
		frappe.call({
			method: "entre_mc.entre_mc.page.ficha_do_credito.ficha_do_credito.obter_ficha",
			args: { pedido_de_credito: pedido, data },
			callback: (r) => {
				if (r.message && this._chave === chave) this.render(r.message);
			},
			error: () => {
				this._chave = null;
			},
		});
	}

	render(ficha) {
		this.ficha = ficha;
		const p = ficha.pedido;
		this.page.set_title(`${__("Ficha do Crédito")} · ${p.name}`);

		if (!ficha.situacao) {
			this.$corpo.html(`
				${this.html_cabecalho(ficha)}
				<div class="emc-resumo-empty">${__("Este pedido ainda não tinha sido desembolsado em {0}.", [
					frappe.datetime.str_to_user(ficha.data),
				])}</div>
			`);
			return;
		}

		this.$corpo.html(`
			${this.html_cabecalho(ficha)}
			${this.html_cards(ficha.situacao)}
			${this.html_composicao(ficha.situacao)}
			<div class="emc-ficha-colunas">
				<section>
					<h4>${__("Plano de Amortização")}</h4>
					${this.html_plano(ficha.plano)}
				</section>
				<section>
					<div class="emc-ficha-titulo-linha">
						<h4>${__("O que aconteceu")}</h4>
						<label class="emc-ficha-toggle">
							<input type="checkbox" id="emc-ficha-vencimentos" ${this.mostrar_vencimentos ? "checked" : ""}>
							${__("Mostrar vencimentos")}
						</label>
					</div>
					<div id="emc-ficha-cronologia"></div>
				</section>
			</div>
		`);
		this.render_cronologia();
	}

	html_cabecalho(ficha) {
		const p = ficha.pedido;
		const s = ficha.situacao;
		const esc = frappe.utils.escape_html;
		const badges = [];
		if (s) {
			const classe = s.estado === "Em Curso" ? "" : s.estado === "Liquidado" ? " emc-resumo-badge--ink" : " emc-resumo-badge--stamp";
			badges.push(`<span class="emc-resumo-badge${classe}">${__(s.estado)}</span>`);
			if (s.congelado_em) {
				badges.push(
					`<span class="emc-resumo-badge emc-ficha-badge--gelo">${__("Dívida congelada desde {0}", [
						frappe.datetime.str_to_user(s.congelado_em),
					])}</span>`
				);
			}
			if (s.reestruturado) badges.push(`<span class="emc-resumo-badge emc-resumo-badge--ink">${__("Reestruturado")}</span>`);
		}
		if (ficha.projecao) {
			badges.push(`<span class="emc-resumo-badge emc-resumo-badge--stamp">${__("Projeção - data futura, sem novos pagamentos")}</span>`);
		}

		const termo = (rotulo, valor) =>
			`<div class="emc-ficha-termo"><span>${rotulo}</span><strong>${valor || "—"}</strong></div>`;

		return `
			<section class="emc-ficha-cabecalho">
				<div class="emc-ficha-identidade">
					<div>
						<a class="emc-ficha-cliente" href="/app/cliente/${encodeURIComponent(p.cliente)}">${esc(p.cliente || "")}</a>
						<div class="emc-ficha-sub">
							<a href="/app/pedido-de-credito/${encodeURIComponent(p.name)}">${esc(p.name)}</a>
							· ${esc(p.produto || "")}
							${p.promotor ? "· " + esc(p.promotor) : ""}
						</div>
					</div>
					<div class="emc-ficha-badges">${badges.join("")}</div>
				</div>
				<div class="emc-ficha-termos">
					${termo(__("Crédito concedido"), format_currency(p.capital_solicitado, FICHA_CURRENCY))}
					${termo(__("Desembolso"), s ? frappe.datetime.str_to_user(s.data_de_desembolso) : "")}
					${termo(__("Último vencimento"), s && s.ultimo_vencimento ? frappe.datetime.str_to_user(s.ultimo_vencimento) : "")}
					${termo(__("Juros"), `${flt(p.taxa_de_juros)}% · ${esc(p.frequencia || "")}`)}
					${termo(__("Multa diária"), `${flt(p.taxa_diaria_de_multa)}%`)}
					${termo(__("Juros de mora"), `${flt(p.juros_de_mora)}%`)}
					${termo(__("Finalidade"), esc(p.finalidade || ""))}
					${termo(__("Garantias"), esc((p.garantias || []).join(", ")))}
				</div>
			</section>`;
	}

	html_cards(s) {
		const moeda = (v) => format_currency(v, FICHA_CURRENCY);
		const proxima = s.proxima
			? `${moeda(s.proxima.em_falta)}<small>${__("Nº {0} · {1}", [
					s.proxima.numero,
					frappe.datetime.str_to_user(s.proxima.data_limite_pagamento),
			  ])}</small>`
			: "—";
		const items = [
			{ label: __("Falta pagar (saldo)"), value: moeda(s.saldo_do_credito) },
			{ label: __("Em atraso (dívida)"), value: moeda(s.divida), warn: flt(s.divida) > 0 },
			{ label: __("Dias de atraso"), value: cint(s.dias_atraso), warn: cint(s.dias_atraso) > 0 },
			{ label: __("Já reembolsado"), value: moeda(s.total_reembolsado) },
			{
				label: __("Prestações pagas"),
				value: `${cint(s.prestacoes_pagas)} / ${cint(s.prestacoes)}`,
			},
			{ label: __("Próxima prestação"), value: proxima, warn: s.proxima && cint(s.proxima.dias_atraso) > 0 },
		];
		return `<section class="emc-resumo-cards emc-ficha-cards">${items
			.map(
				(c) => `
				<div class="emc-resumo-card${c.warn ? " emc-resumo-card--warn" : ""}">
					<span class="emc-resumo-card-label">${c.label}</span>
					<span class="emc-resumo-card-value">${c.value}</span>
				</div>`
			)
			.join("")}</section>`;
	}

	// De que é feito o que falta pagar e o que já foi pago.
	html_composicao(s) {
		const moeda = (v) => format_currency(v, FICHA_CURRENCY);
		const linhas = [
			["capital", __("Capital")],
			["juros", __("Juros")],
			["multa", __("Multa")],
			["mora", __("Juros de Mora")],
		];
		const perdoado = { multa: s.multa_perdoada, mora: s.mora_perdoada };
		const total_falta = linhas.reduce((t, [k]) => t + flt(s.em_falta[k]), 0);
		const total_pago = linhas.reduce((t, [k]) => t + flt(s.pago[k]), 0);
		const barra = linhas
			.map(([k]) => {
				const pct = total_falta > 0 ? (Math.max(flt(s.em_falta[k]), 0) / total_falta) * 100 : 0;
				return pct > 0 ? `<span class="emc-ficha-seg emc-ficha-seg--${k}" style="width:${pct.toFixed(2)}%"></span>` : "";
			})
			.join("");

		return `
			<section class="emc-ficha-composicao">
				<h4>${__("De que é feita a dívida")}</h4>
				<div class="emc-ficha-barra-comp">${barra}</div>
				<div class="emc-resumo-table-wrap">
					<table class="emc-resumo-table">
						<thead><tr>
							<th></th>
							<th class="emc-num">${__("Já pago")}</th>
							<th class="emc-num">${__("Perdoado")}</th>
							<th class="emc-num">${__("Falta pagar")}</th>
						</tr></thead>
						<tbody>
							${linhas
								.map(
									([k, rotulo]) => `<tr>
										<td><span class="emc-ficha-ponto emc-ficha-seg--${k}"></span>${rotulo}</td>
										<td class="emc-num">${moeda(s.pago[k])}</td>
										<td class="emc-num">${k in perdoado ? moeda(perdoado[k]) : "—"}</td>
										<td class="emc-num"><strong>${moeda(s.em_falta[k])}</strong></td>
									</tr>`
								)
								.join("")}
							<tr class="emc-ficha-total">
								<td>${__("Total")}</td>
								<td class="emc-num">${moeda(total_pago)}</td>
								<td class="emc-num">${moeda(flt(s.multa_perdoada) + flt(s.mora_perdoada))}</td>
								<td class="emc-num"><strong>${moeda(total_falta)}</strong></td>
							</tr>
						</tbody>
					</table>
				</div>
			</section>`;
	}

	html_plano(plano) {
		const moeda = (v) => format_currency(v, FICHA_CURRENCY);
		const classe_estado = { Pago: " emc-resumo-badge--ink", Atrasado: " emc-resumo-badge--stamp" };
		return `
			<div class="emc-resumo-table-wrap">
				<table class="emc-resumo-table">
					<thead><tr>
						<th>${__("Nº")}</th>
						<th>${__("Vencimento")}</th>
						<th>${__("Estado")}</th>
						<th class="emc-num">${__("Capital")}</th>
						<th class="emc-num">${__("Juros")}</th>
						<th class="emc-num">${__("Multa")}</th>
						<th class="emc-num">${__("Mora")}</th>
						<th class="emc-num">${__("Pago")}</th>
						<th class="emc-num">${__("Falta")}</th>
						<th class="emc-num">${__("Dias")}</th>
					</tr></thead>
					<tbody>
						${plano
							.map(
								(r) => `<tr class="${cint(r.dias_atraso) > 0 ? "emc-ficha-linha--atraso" : ""}">
									<td>${r.numero}</td>
									<td>${frappe.datetime.str_to_user(r.data_limite_pagamento)}</td>
									<td><span class="emc-resumo-badge${classe_estado[r.status] || ""}">${__(r.status)}</span></td>
									<td class="emc-num">${moeda(r.capital_mensal)}</td>
									<td class="emc-num">${moeda(r.juros_mensais)}</td>
									<td class="emc-num">${flt(r.multa_aplicada) ? moeda(r.multa_aplicada) : "—"}</td>
									<td class="emc-num">${flt(r.juros_mora_aplicado) ? moeda(r.juros_mora_aplicado) : "—"}</td>
									<td class="emc-num">${flt(r.pago) ? moeda(r.pago) : "—"}</td>
									<td class="emc-num"><strong>${flt(r.em_falta) ? moeda(r.em_falta) : "—"}</strong></td>
									<td class="emc-num">${cint(r.dias_atraso) || "—"}</td>
								</tr>`
							)
							.join("")}
					</tbody>
				</table>
			</div>`;
	}

	render_cronologia() {
		const $alvo = this.$corpo.find("#emc-ficha-cronologia");
		if (!$alvo.length || !this.ficha) return;
		const esc = frappe.utils.escape_html;
		const eventos = (this.ficha.cronologia || []).filter(
			(e) => this.mostrar_vencimentos || e.tipo !== "Vencimento"
		);
		if (!eventos.length) {
			$alvo.html(`<div class="emc-resumo-empty">${__("Sem movimentos até esta data.")}</div>`);
			return;
		}
		const sinal = { entrada: "+", saida: "−" };
		$alvo.html(
			`<ol class="emc-ficha-cronologia">${eventos
				.map((e) => {
					const titulo = e.doctype
						? `<a href="/app/${frappe.router.slug(e.doctype)}/${encodeURIComponent(e.name)}">${esc(e.titulo)}</a>`
						: esc(e.titulo);
					const valor =
						e.valor != null && e.valor !== ""
							? `<span class="emc-ficha-ev-valor">${sinal[e.sentido] || ""}${format_currency(e.valor, FICHA_CURRENCY)}</span>`
							: "";
					return `<li class="emc-ficha-ev emc-ficha-ev--${e.sentido}">
						<span class="emc-ficha-ev-data">${frappe.datetime.str_to_user(e.data)}</span>
						<div class="emc-ficha-ev-corpo">
							<div class="emc-ficha-ev-topo"><span class="emc-ficha-ev-titulo">${titulo}</span>${valor}</div>
							${e.detalhe ? `<div class="emc-ficha-ev-detalhe">${esc(e.detalhe)}</div>` : ""}
						</div>
					</li>`;
				})
				.join("")}</ol>`
		);
	}

	inject_styles() {
		if (document.getElementById("emc-ficha-style")) return;
		const style = document.createElement("style");
		style.id = "emc-ficha-style";
		style.textContent = `
			.emc-ficha {
				max-width: 1240px;
				margin: 0 auto;
				padding: 8px 4px 48px;
				font-family: var(--emc-font-numeric);
				color: var(--emc-ink);
			}
			.emc-ficha h4 {
				font-family: var(--emc-font-display);
				margin: 0 0 8px;
				color: var(--emc-accent-deep);
			}
			.emc-ficha-barra {
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
			.emc-ficha-campo { min-width: 220px; }
			.emc-ficha-campo .form-group { margin-bottom: 0; }
			.emc-ficha-atalhos { display: flex; gap: 6px; flex-wrap: wrap; padding-bottom: 4px; }
			.emc-ficha-cabecalho {
				background: var(--emc-paper);
				border: 1px solid var(--emc-line);
				border-radius: 6px;
				padding: 16px 18px;
				margin-bottom: 14px;
			}
			.emc-ficha-identidade {
				display: flex;
				justify-content: space-between;
				align-items: flex-start;
				gap: 12px;
				flex-wrap: wrap;
				margin-bottom: 14px;
			}
			.emc-ficha-cliente {
				font-family: var(--emc-font-display);
				font-size: 24px;
				font-weight: 600;
				color: var(--emc-accent-deep);
			}
			.emc-ficha-sub { color: var(--emc-ink-soft); font-size: 13px; }
			.emc-ficha-badges { display: flex; gap: 6px; flex-wrap: wrap; }
			.emc-ficha-badge--gelo { background: #dcebf7; color: #1d4f7a; }
			.emc-ficha-termos {
				display: grid;
				grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
				gap: 10px 18px;
				border-top: 1px solid var(--emc-line);
				padding-top: 12px;
			}
			.emc-ficha-termo span {
				display: block;
				font-size: 10px;
				font-weight: 600;
				letter-spacing: 0.06em;
				text-transform: uppercase;
				color: var(--emc-ink-soft);
			}
			.emc-ficha-termo strong { font-size: 13.5px; font-variant-numeric: tabular-nums; }
			.emc-ficha-cards { grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); }
			.emc-ficha-cards .emc-resumo-card-value { font-size: 20px; }
			.emc-ficha-cards .emc-resumo-card-value small {
				display: block;
				font-family: var(--emc-font-numeric);
				font-size: 11px;
				font-weight: 500;
				color: var(--emc-ink-soft);
			}
			.emc-ficha-composicao { margin-bottom: 22px; }
			.emc-ficha-barra-comp {
				display: flex;
				gap: 2px;
				height: 12px;
				border-radius: 6px;
				overflow: hidden;
				background: var(--emc-band);
				margin-bottom: 10px;
			}
			.emc-ficha-seg { display: block; height: 100%; }
			.emc-ficha-seg--capital { background: #14532f; }
			.emc-ficha-seg--juros { background: #4f9d74; }
			.emc-ficha-seg--multa { background: #b4472a; }
			.emc-ficha-seg--mora { background: #d98a3d; }
			.emc-ficha-ponto {
				display: inline-block;
				width: 9px;
				height: 9px;
				border-radius: 2px;
				margin-right: 8px;
			}
			.emc-ficha .emc-resumo-table tr.emc-ficha-total td {
				border-top: 2px solid var(--emc-accent);
				font-weight: 700;
				background: var(--emc-paper);
			}
			.emc-ficha .emc-resumo-table tr.emc-ficha-linha--atraso td { background: #fbeee9; }
			.emc-ficha-colunas {
				display: grid;
				grid-template-columns: minmax(0, 3fr) minmax(0, 2fr);
				gap: 22px;
				align-items: start;
			}
			@media (max-width: 1000px) {
				.emc-ficha-colunas { grid-template-columns: 1fr; }
			}
			.emc-ficha-titulo-linha {
				display: flex;
				justify-content: space-between;
				align-items: baseline;
				gap: 10px;
			}
			.emc-ficha-toggle { font-size: 12px; font-weight: 500; color: var(--emc-ink-soft); margin: 0; }
			.emc-ficha-cronologia { list-style: none; margin: 0; padding: 0; }
			.emc-ficha-ev {
				display: grid;
				grid-template-columns: 82px minmax(0, 1fr);
				gap: 10px;
				padding: 9px 0 9px 12px;
				border-left: 3px solid var(--emc-line);
				border-bottom: 1px solid var(--emc-line);
			}
			.emc-ficha-ev--entrada { border-left-color: var(--emc-accent); }
			.emc-ficha-ev--saida { border-left-color: var(--emc-ink); }
			.emc-ficha-ev--alivio { border-left-color: #3b7fb8; }
			.emc-ficha-ev--alerta { border-left-color: var(--emc-stamp); }
			.emc-ficha-ev-data { font-size: 12px; color: var(--emc-ink-soft); font-variant-numeric: tabular-nums; padding-top: 1px; }
			.emc-ficha-ev-topo { display: flex; justify-content: space-between; gap: 10px; }
			.emc-ficha-ev-titulo { font-weight: 700; font-size: 13px; }
			.emc-ficha-ev-valor { font-weight: 700; font-size: 13px; font-variant-numeric: tabular-nums; white-space: nowrap; }
			.emc-ficha-ev--entrada .emc-ficha-ev-valor { color: var(--emc-accent); }
			.emc-ficha-ev--alerta .emc-ficha-ev-valor { color: var(--emc-stamp); }
			.emc-ficha-ev-detalhe { font-size: 12px; color: var(--emc-ink-soft); margin-top: 2px; white-space: normal; }
		`;
		document.head.appendChild(style);
	}
}
