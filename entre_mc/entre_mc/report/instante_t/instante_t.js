// Copyright (c) 2026, Dércio Bobo and contributors
// For license information, please see license.txt

frappe.query_reports["Instante T"] = {
	filters: [
		{
			fieldname: "data_referencia",
			label: __("Data de Referência"),
			fieldtype: "Date",
			reqd: 1,
			default: frappe.datetime.get_today(),
			description: __(
				"Mostra cada crédito tal como estava no fim deste dia - só conta Desembolsos, Reembolsos, " +
					"Perdões de Multa e Execuções de Garantia com data até aqui."
			),
		},
		{
			fieldname: "vista",
			label: __("Vista"),
			fieldtype: "Select",
			options: "Por Crédito\nPor Prestação",
			default: "Por Crédito",
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
		{
			fieldname: "estado",
			label: __("Estado na Data"),
			fieldtype: "Select",
			options: "\nEm Curso\nIncumprimento\nLiquidado",
		},
		{
			fieldname: "incluir_liquidados",
			label: __("Incluir Liquidados"),
			fieldtype: "Check",
			default: 0,
		},
	],
};
