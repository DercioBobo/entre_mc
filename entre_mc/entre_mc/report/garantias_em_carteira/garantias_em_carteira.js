// Copyright (c) 2026, Dércio Bobo and contributors
// For license information, please see license.txt

frappe.query_reports["Garantias em Carteira"] = {
	filters: [
		{
			fieldname: "cliente",
			label: __("Cliente"),
			fieldtype: "Link",
			options: "Cliente",
		},
		{
			fieldname: "status",
			label: __("Estado"),
			fieldtype: "Select",
			options: "\nDisponível\nNão Disponível\nDevolvida",
		},
	],
};
