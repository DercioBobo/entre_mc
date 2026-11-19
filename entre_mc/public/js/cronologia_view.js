// Copyright (c) 2026, Dércio Bobo and contributors
// For license information, please see license.txt

frappe.provide("entre_mc");

// Estilo injetado aqui (e não em entre_mc.css) para não depender de um
// `bench build` - este ficheiro é carregado com frappe.require pelo Pedido.
(function () {
	if (document.getElementById("emc-cronologia-style")) return;
	const style = document.createElement("style");
	style.id = "emc-cronologia-style";
	style.textContent = `
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
})();

// Cronologia de um crédito (o que lhe aconteceu, do mais recente para o mais
// antigo) - usada pela Ficha do Crédito e pelo formulário do Pedido De Credito.
// `eventos` vem de ficha_do_credito._cronologia; o estilo é injetado acima.
entre_mc.render_cronologia_html = function (eventos, currency, mostrar_vencimentos) {
	const esc = frappe.utils.escape_html;
	const lista = (eventos || []).filter((e) => mostrar_vencimentos || e.tipo !== "Vencimento");
	if (!lista.length) {
		return `<div class="emc-resumo-empty">${__("Sem movimentos até esta data.")}</div>`;
	}
	const sinal = { entrada: "+", saida: "−" };
	return `<ol class="emc-ficha-cronologia">${lista
		.map((e) => {
			const titulo = e.doctype
				? `<a href="/app/${frappe.router.slug(e.doctype)}/${encodeURIComponent(e.name)}">${esc(e.titulo)}</a>`
				: esc(e.titulo);
			const valor =
				e.valor != null && e.valor !== ""
					? `<span class="emc-ficha-ev-valor">${sinal[e.sentido] || ""}${format_currency(e.valor, currency)}</span>`
					: "";
			return `<li class="emc-ficha-ev emc-ficha-ev--${e.sentido}">
				<span class="emc-ficha-ev-data">${frappe.datetime.str_to_user(e.data)}</span>
				<div class="emc-ficha-ev-corpo">
					<div class="emc-ficha-ev-topo"><span class="emc-ficha-ev-titulo">${titulo}</span>${valor}</div>
					${e.detalhe ? `<div class="emc-ficha-ev-detalhe">${esc(e.detalhe)}</div>` : ""}
				</div>
			</li>`;
		})
		.join("")}</ol>`;
};
