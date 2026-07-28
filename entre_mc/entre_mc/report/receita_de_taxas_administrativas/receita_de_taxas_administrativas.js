// Copyright (c) 2026, Dércio Bobo and contributors
// For license information, please see license.txt

frappe.query_reports["Receita de Taxas Administrativas"] = {
	filters: [
		{
			fieldname: "data_inicio",
			label: __("Data de Desembolso (De)"),
			fieldtype: "Date",
		},
		{
			fieldname: "data_fim",
			label: __("Data de Desembolso (Até)"),
			fieldtype: "Date",
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
