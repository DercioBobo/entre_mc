// Copyright (c) 2026, Dércio Bobo and contributors
// For license information, please see license.txt

frappe.query_reports["Pedidos Pendentes de Aprovacao"] = {
	filters: [
		{
			fieldname: "workflow_state",
			label: __("Estado de Aprovação"),
			fieldtype: "Select",
			options: "\nPendente Aprovação 1\nPendente Aprovação 2",
		},
	],
};
