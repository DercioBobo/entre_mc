// Copyright (c) 2026, Dércio Bobo and contributors
// For license information, please see license.txt

frappe.pages["simulador-de-credito"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Simulador de Crédito",
		single_column: true,
	});

	new EntreMcSimulador(page);
};

class EntreMcSimulador {
	constructor(page) {
		this.page = page;
		this.timeout = null;
		this.render_shell();
		this.bind_inputs();
		this.load_default_frequencia();
	}

	render_shell() {
		this.inject_styles();

		this.page.main.html(`
			<div class="emc-simulador">
				<header class="emc-header">
					<span class="emc-eyebrow">Sem proponente · sem cliente · sem produto</span>
					<h1 class="emc-title">Simulador de Crédito</h1>
					<p class="emc-subtitle">Escreva os números e leia a resposta na hora — para quando alguém pergunta "quanto é que eu pago?".</p>
				</header>

				<section class="emc-inputs" aria-label="Dados do crédito">
					<div class="emc-field">
						<label for="emc-capital">Capital</label>
						<input id="emc-capital" type="number" inputmode="decimal" min="0" step="1" placeholder="0" />
					</div>
					<div class="emc-field">
						<label for="emc-taxa">Taxa de Juros <span class="emc-unit">% / mês</span></label>
						<input id="emc-taxa" type="number" inputmode="decimal" min="0" step="0.1" placeholder="0" />
					</div>
					<div class="emc-field">
						<label for="emc-prazo">Prazo <span class="emc-unit">meses</span></label>
						<input id="emc-prazo" type="number" inputmode="numeric" min="1" step="1" placeholder="0" />
					</div>
					<div class="emc-field">
						<label for="emc-modelo">Modelo</label>
						<select id="emc-modelo">
							<option value="Constante">Constante</option>
							<option value="Decrescente">Decrescente</option>
							<option value="Misto">Misto</option>
						</select>
					</div>
					<div class="emc-field">
						<label for="emc-frequencia">Frequência</label>
						<select id="emc-frequencia">
							<option value="Diário">Diário</option>
							<option value="Semanal">Semanal</option>
							<option value="Quinzenal">Quinzenal</option>
							<option value="Mensal" selected>Mensal</option>
						</select>
					</div>
				</section>

				<section class="emc-resultado" aria-live="polite">
					<div class="emc-display emc-display--empty">
						<span class="emc-display-label">Prestação</span>
						<span class="emc-display-value">—</span>
						<div class="emc-display-meta">
							<span><span class="emc-display-meta-label">Total a pagar</span><span class="emc-display-meta-value">—</span></span>
							<span><span class="emc-display-meta-label">Total de juros</span><span class="emc-display-meta-value">—</span></span>
							<span><span class="emc-display-meta-label">Nº de prestações</span><span class="emc-display-meta-value">—</span></span>
						</div>
					</div>
				</section>

				<section class="emc-tape-wrap">
					<div class="emc-tape-body">
						<table class="emc-tape">
							<thead>
								<tr>
									<th>Nº</th>
									<th>Vencimento</th>
									<th class="emc-num">Capital</th>
									<th class="emc-num">Juros</th>
									<th class="emc-num">Prestação</th>
									<th class="emc-num">Saldo</th>
								</tr>
							</thead>
							<tbody id="emc-tape-rows">
								<tr class="emc-tape-empty">
									<td colspan="6">Preencha os campos acima para ver o plano de amortização.</td>
								</tr>
							</tbody>
						</table>
					</div>
					<div class="emc-tape-tear"></div>
				</section>
			</div>
		`);

		this.$capital = this.page.main.find("#emc-capital");
		this.$taxa = this.page.main.find("#emc-taxa");
		this.$prazo = this.page.main.find("#emc-prazo");
		this.$modelo = this.page.main.find("#emc-modelo");
		this.$frequencia = this.page.main.find("#emc-frequencia");
		this.$display = this.page.main.find(".emc-display");
		this.$displayValue = this.page.main.find(".emc-display-value");
		this.$metaValues = this.page.main.find(".emc-display-meta-value");
		this.$rows = this.page.main.find("#emc-tape-rows");
	}

	load_default_frequencia() {
		frappe.db.get_single_value("MC Settings", "frequencia_padrao").then((value) => {
			if (value) this.$frequencia.val(value);
		});
	}

	bind_inputs() {
		const trigger = () => this.schedule_calc();
		this.page.main.find("#emc-capital, #emc-taxa, #emc-prazo").on("input", trigger);
		this.page.main.find("#emc-modelo, #emc-frequencia").on("change", trigger);
	}

	schedule_calc() {
		clearTimeout(this.timeout);
		this.timeout = setTimeout(() => this.calcular(), 300);
	}

	calcular() {
		const capital = flt(this.$capital.val());
		const taxa_de_juros = flt(this.$taxa.val());
		const prazo = cint(this.$prazo.val());
		const modelo = this.$modelo.val();
		const frequencia = this.$frequencia.val();

		if (!capital || !taxa_de_juros || !prazo) {
			this.render_empty();
			return;
		}

		frappe.call({
			method: "entre_mc.entre_mc.page.simulador_de_credito.simulador_de_credito.calcular",
			args: { capital, taxa_de_juros, prazo, modelo, frequencia },
			callback: (r) => this.render_resultado(r.message || []),
			error: () => this.render_empty(),
		});
	}

	render_empty() {
		this.$display.addClass("emc-display--empty");
		this.$displayValue.text("—");
		this.$metaValues.text("—");
		this.$rows.html(
			`<tr class="emc-tape-empty"><td colspan="6">Preencha os campos acima para ver o plano de amortização.</td></tr>`
		);
	}

	render_resultado(linhas) {
		if (!linhas.length) {
			this.render_empty();
			return;
		}

		const primeira = linhas[0];
		const total_prestacoes = linhas.reduce((sum, l) => sum + flt(l.prestacao_total), 0);
		const total_juros = linhas.reduce((sum, l) => sum + flt(l.juros_mensais), 0);

		this.$display.removeClass("emc-display--empty");
		this.$displayValue.text(format_currency(primeira.prestacao_total, "MZN"));

		const meta = this.$metaValues.toArray();
		meta[0] && $(meta[0]).text(format_currency(total_prestacoes, "MZN"));
		meta[1] && $(meta[1]).text(format_currency(total_juros, "MZN"));
		meta[2] && $(meta[2]).text(linhas.length);

		const rows = linhas
			.map(
				(l) => `
				<tr>
					<td>${l.numero}</td>
					<td>${frappe.datetime.str_to_user(l.data_limite_pagamento)}</td>
					<td class="emc-num">${format_currency(l.capital_mensal, "MZN")}</td>
					<td class="emc-num">${format_currency(l.juros_mensais, "MZN")}</td>
					<td class="emc-num emc-num--strong">${format_currency(l.prestacao_total, "MZN")}</td>
					<td class="emc-num">${format_currency(l.saldo, "MZN")}</td>
				</tr>`
			)
			.join("");
		this.$rows.html(rows);
	}

	inject_styles() {
		if (document.getElementById("emc-simulador-style")) return;
		const style = document.createElement("style");
		style.id = "emc-simulador-style";
		style.textContent = `
			@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Roboto+Mono:wght@400;500;700&display=swap');

			.emc-simulador {
				--emc-paper: #fdfdf9;
				--emc-band: #dfefe4;
				--emc-ink: #16261e;
				--emc-ink-soft: #4b5d53;
				--emc-accent: #1f7a4d;
				--emc-accent-deep: #14532f;
				--emc-stamp: #b4472a;
				--emc-line: #c7d9cc;
				--emc-font-display: "Space Grotesk", -apple-system, "Segoe UI", sans-serif;
				--emc-font-mono: "Roboto Mono", ui-monospace, "SFMono-Regular", "Cascadia Code", monospace;

				max-width: 900px;
				margin: 0 auto;
				padding: 8px 4px 48px;
				color: var(--emc-ink);
				font-family: var(--emc-font-display);
			}

			.emc-header {
				padding: 8px 4px 20px;
				border-bottom: 1px solid var(--emc-line);
				margin-bottom: 24px;
			}
			.emc-eyebrow {
				display: inline-block;
				font-family: var(--emc-font-mono);
				font-size: 11px;
				letter-spacing: 0.08em;
				text-transform: uppercase;
				color: var(--emc-accent-deep);
				background: var(--emc-band);
				padding: 3px 8px;
				border-radius: 3px;
				margin-bottom: 10px;
			}
			.emc-title {
				font-family: var(--emc-font-display);
				font-weight: 700;
				font-size: 30px;
				line-height: 1.15;
				margin: 0 0 6px;
				color: var(--emc-ink);
			}
			.emc-subtitle {
				margin: 0;
				color: var(--emc-ink-soft);
				font-size: 14px;
				max-width: 56ch;
			}

			.emc-inputs {
				display: grid;
				grid-template-columns: 1.3fr 1fr 1fr 1fr 1fr;
				gap: 12px;
				background: var(--emc-paper);
				border: 1px solid var(--emc-line);
				border-top: 3px solid var(--emc-accent);
				border-radius: 6px;
				padding: 18px;
				margin-bottom: 20px;
			}
			.emc-field label {
				display: block;
				font-family: var(--emc-font-mono);
				font-size: 11px;
				letter-spacing: 0.04em;
				text-transform: uppercase;
				color: var(--emc-ink-soft);
				margin-bottom: 6px;
			}
			.emc-field .emc-unit {
				text-transform: none;
				letter-spacing: 0;
				color: var(--emc-ink-soft);
				opacity: 0.8;
			}
			.emc-field input,
			.emc-field select {
				width: 100%;
				box-sizing: border-box;
				font-family: var(--emc-font-mono);
				font-size: 17px;
				font-variant-numeric: tabular-nums;
				color: var(--emc-ink);
				background: #fff;
				border: 1px solid var(--emc-line);
				border-radius: 4px;
				padding: 8px 10px;
				transition: border-color 120ms ease, box-shadow 120ms ease;
			}
			.emc-field input:focus,
			.emc-field select:focus {
				outline: none;
				border-color: var(--emc-accent);
				box-shadow: 0 0 0 3px rgba(31, 122, 77, 0.15);
			}

			.emc-resultado {
				margin-bottom: 4px;
			}
			.emc-display {
				background: var(--emc-ink);
				border-radius: 8px;
				padding: 26px 24px;
				text-align: center;
				transition: opacity 150ms ease;
			}
			.emc-display--empty {
				opacity: 0.55;
			}
			.emc-display-label {
				display: block;
				font-family: var(--emc-font-mono);
				font-size: 12px;
				letter-spacing: 0.1em;
				text-transform: uppercase;
				color: #9fcab0;
				margin-bottom: 6px;
			}
			.emc-display-value {
				display: block;
				font-family: var(--emc-font-mono);
				font-weight: 700;
				font-size: clamp(32px, 6vw, 52px);
				font-variant-numeric: tabular-nums;
				letter-spacing: -0.01em;
				color: #f2fbf5;
			}
			.emc-display-meta {
				display: flex;
				justify-content: center;
				flex-wrap: wrap;
				gap: 24px;
				margin-top: 18px;
				padding-top: 16px;
				border-top: 1px dashed rgba(159, 202, 176, 0.35);
			}
			.emc-display-meta-label {
				display: block;
				font-family: var(--emc-font-mono);
				font-size: 10px;
				letter-spacing: 0.06em;
				text-transform: uppercase;
				color: #9fcab0;
				margin-bottom: 2px;
			}
			.emc-display-meta-value {
				display: block;
				font-family: var(--emc-font-mono);
				font-size: 15px;
				font-variant-numeric: tabular-nums;
				color: #f2fbf5;
			}

			.emc-tape-wrap {
				margin-top: 22px;
			}
			.emc-tape-body {
				background: var(--emc-paper);
				border: 1px solid var(--emc-line);
				border-bottom: none;
				border-radius: 6px 6px 0 0;
				overflow-x: auto;
			}
			table.emc-tape {
				width: 100%;
				border-collapse: collapse;
				font-family: var(--emc-font-mono);
				font-size: 13px;
			}
			.emc-tape thead th {
				position: sticky;
				top: 0;
				background: var(--emc-accent);
				color: #f2fbf5;
				font-weight: 500;
				font-size: 11px;
				letter-spacing: 0.05em;
				text-transform: uppercase;
				text-align: left;
				padding: 10px 12px;
			}
			.emc-tape tbody td {
				padding: 8px 12px;
				border-bottom: 1px solid var(--emc-line);
				white-space: nowrap;
				font-variant-numeric: tabular-nums;
			}
			.emc-tape tbody tr:nth-child(even) {
				background: var(--emc-band);
			}
			.emc-tape .emc-num {
				text-align: right;
			}
			.emc-tape .emc-num--strong {
				font-weight: 700;
				color: var(--emc-accent-deep);
			}
			.emc-tape-empty td {
				font-family: var(--emc-font-display);
				color: var(--emc-ink-soft);
				text-align: center;
				padding: 28px 12px;
				white-space: normal;
			}

			.emc-tape-tear {
				height: 14px;
				background-image:
					linear-gradient(135deg, var(--emc-band-shadow, #f2f0e9) 25%, transparent 25%),
					linear-gradient(225deg, var(--emc-band-shadow, #f2f0e9) 25%, transparent 25%);
				background-size: 16px 16px;
				background-position: top;
				border: 1px solid var(--emc-line);
				border-top: none;
				border-radius: 0 0 6px 6px;
			}

			@media (max-width: 720px) {
				.emc-inputs {
					grid-template-columns: 1fr 1fr;
				}
			}
			@media (max-width: 480px) {
				.emc-inputs {
					grid-template-columns: 1fr;
				}
				.emc-display-meta {
					gap: 16px;
				}
			}

			@media (prefers-reduced-motion: reduce) {
				.emc-display,
				.emc-field input,
				.emc-field select {
					transition: none;
				}
			}
		`;
		document.head.appendChild(style);
	}
}
