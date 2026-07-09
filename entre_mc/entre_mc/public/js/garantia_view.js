// Copyright (c) 2026, Dércio Bobo and contributors
// For license information, please see license.txt

frappe.provide("entre_mc");

const GARANTIA_ESTADO_COLOR = {
	Novo: "green",
	Usado: "orange",
};

// Card gallery for the Item de Garantia child table, used instead of the
// default grid on the Garantia form.
entre_mc.render_garantia_gallery_html = function (itens, currency) {
	if (!itens || !itens.length) {
		return `<div class="text-muted">${__("Nenhum item adicionado à tabela de garantias.")}</div>`;
	}

	const cards = itens
		.map((item) => {
			const img = item.imagem
				? `<img src="${item.imagem}" alt="${frappe.utils.escape_html(item.nome || "")}">`
				: `<div class="entre-mc-garantia-noimg text-muted d-flex align-items-center justify-content-center" style="height:130px;">${__(
						"Sem imagem"
					)}</div>`;
			const indicator = GARANTIA_ESTADO_COLOR[item.estado] || "gray";
			return `<div class="entre-mc-garantia-card">
				${img}
				<div class="entre-mc-garantia-body">
					<div class="entre-mc-garantia-title">${frappe.utils.escape_html(item.nome || "")}</div>
					<div class="entre-mc-garantia-meta">${frappe.utils.escape_html(item.categoria || "")}</div>
					<div class="entre-mc-garantia-meta">${format_currency(item.valor_de_mercado, currency)}</div>
					<span class="entre-mc-garantia-status indicator-pill ${indicator}">${__(item.estado || "")}</span>
				</div>
			</div>`;
		})
		.join("");

	return `<div class="entre-mc-garantia-gallery">${cards}</div>`;
};
