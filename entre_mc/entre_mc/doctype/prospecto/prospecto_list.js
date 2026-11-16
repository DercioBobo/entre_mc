// Copyright (c) 2026, Dércio Bobo and contributors
// For license information, please see license.txt

frappe.listview_settings["Prospecto"] = {
	get_indicator(doc) {
		const cores = {
			Novo: "gray",
			Contactado: "blue",
			Interessado: "orange",
			"Em Negociação": "yellow",
			Proponente: "purple",
			Cliente: "green",
			Perdido: "red",
		};
		return [__(doc.estado), cores[doc.estado] || "gray", `estado,=,${doc.estado}`];
	},
};
