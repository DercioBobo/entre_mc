// Copyright (c) 2026, Dércio Bobo and contributors
// For license information, please see license.txt

frappe.query_reports["Desembolsos no Periodo"] = {
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
			fieldname: "produto",
			label: __("Produto"),
			fieldtype: "Link",
			options: "Produto",
		},
		{
			fieldname: "forma_de_pagamento",
			label: __("Forma de Pagamento"),
			fieldtype: "Select",
			options: "\nNumerário\nTransferência Bancária\nDepósito\nMobile Money",
		},
	],
};
