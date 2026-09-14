// Copyright (c) 2026, Dércio Bobo and contributors
// For license information, please see license.txt

frappe.query_reports["Simulacao de Encargos Futuros"] = {
	filters: [
		{
			fieldname: "data_referencia",
			label: __("Data de Referência"),
			fieldtype: "Date",
			reqd: 1,
			default: frappe.datetime.add_days(frappe.datetime.get_today(), 30),
			description: __("Assume que nada é pago entre hoje e esta data."),
		},
		{
			fieldname: "pedido_de_credito",
			label: __("Pedido De Credito"),
			fieldtype: "Link",
			options: "Pedido De Credito",
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
	],
};
