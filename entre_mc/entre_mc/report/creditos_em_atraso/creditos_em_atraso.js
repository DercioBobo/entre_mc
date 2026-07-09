// Copyright (c) 2026, Dércio Bobo and contributors
// For license information, please see license.txt

frappe.query_reports["Creditos em Atraso"] = {
	filters: [
		{
			fieldname: "cliente",
			label: __("Cliente"),
			fieldtype: "Link",
			options: "Cliente",
		},
	],
};
