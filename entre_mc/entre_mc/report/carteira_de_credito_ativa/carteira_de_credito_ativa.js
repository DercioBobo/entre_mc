// Copyright (c) 2026, Dércio Bobo and contributors
// For license information, please see license.txt

frappe.query_reports["Carteira de Credito Ativa"] = {
	filters: [
		{
			fieldname: "cliente",
			label: __("Cliente"),
			fieldtype: "Link",
			options: "Cliente",
		},
		{
			fieldname: "produto",
			label: __("Produto"),
			fieldtype: "Link",
			options: "Produto",
		},
	],
};
