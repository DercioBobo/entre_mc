// Copyright (c) 2026, Dércio Bobo and contributors
// For license information, please see license.txt

frappe.query_reports["Prestacoes a Receber"] = {
	filters: [
		{
			fieldname: "pedido_de_credito",
			label: __("Pedido"),
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
		{
			fieldname: "apenas_em_atraso",
			label: __("Apenas prestações vencidas"),
			fieldtype: "Check",
		},
		{
			fieldname: "incluir_pagas",
			label: __("Incluir prestações pagas"),
			fieldtype: "Check",
		},
	],
};
