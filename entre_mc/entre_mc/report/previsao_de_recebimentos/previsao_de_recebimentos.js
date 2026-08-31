// Copyright (c) 2026, Dércio Bobo and contributors
// For license information, please see license.txt

frappe.query_reports["Previsao de Recebimentos"] = {
	filters: [
		{
			fieldname: "data_inicio",
			label: __("De"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 1,
		},
		{
			fieldname: "data_fim",
			label: __("Até"),
			fieldtype: "Date",
			default: frappe.datetime.month_end(),
			reqd: 1,
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
		{
			fieldname: "promotor",
			label: __("Promotor"),
			fieldtype: "Link",
			options: "User",
		},
		{
			fieldname: "pedido_de_credito",
			label: __("Pedido"),
			fieldtype: "Link",
			options: "Pedido De Credito",
		},
	],
};
