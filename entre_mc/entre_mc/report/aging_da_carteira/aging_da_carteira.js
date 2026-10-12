// Copyright (c) 2026, Dércio Bobo and contributors
// For license information, please see license.txt

frappe.query_reports["Aging da Carteira"] = {
	filters: [
		{
			fieldname: "data_referencia",
			label: __("Data de Referência"),
			fieldtype: "Date",
			reqd: 1,
			default: frappe.datetime.get_today(),
			description: __("Classifica os atrasos tal como estavam no fim deste dia (Instante T)."),
		},
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
