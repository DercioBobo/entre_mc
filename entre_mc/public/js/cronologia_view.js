// Copyright (c) 2026, Dércio Bobo and contributors
// For license information, please see license.txt

frappe.provide("entre_mc");

// Cronologia de um crédito (o que lhe aconteceu, do mais recente para o mais
// antigo) - usada pela Ficha do Crédito e pelo formulário do Pedido De Credito.
// `eventos` vem de ficha_do_credito._cronologia; o estilo está em entre_mc.css.
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
