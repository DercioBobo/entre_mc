// Copyright (c) 2026, Dércio Bobo and contributors
// For license information, please see license.txt

frappe.query_reports["Relatorio de Cobrancas"] = {
	filters: [
		{
			fieldname: "data_inicio",
			label: __("De"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
		},
		{
			fieldname: "data_fim",
			label: __("Até"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "cliente",
			label: __("Cliente"),
			fieldtype: "Link",
			options: "Cliente",
		},
		{
			fieldname: "pedido_de_credito",
			label: __("Pedido de Crédito"),
			fieldtype: "Link",
			options: "Pedido De Credito",
		},
	],
};
