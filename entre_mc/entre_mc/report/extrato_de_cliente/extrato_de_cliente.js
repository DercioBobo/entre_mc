// Copyright (c) 2026, Dércio Bobo and contributors
// For license information, please see license.txt

frappe.query_reports["Extrato de Cliente"] = {
	filters: [
		{
			fieldname: "cliente",
			label: __("Cliente"),
			fieldtype: "Link",
			options: "Cliente",
			reqd: 1,
		},
		{
			fieldname: "pedido_de_credito",
			label: __("Pedido de Crédito"),
			fieldtype: "Link",
			options: "Pedido De Credito",
			get_query: () => {
				const cliente = frappe.query_report.get_filter_value("cliente");
				return cliente ? { filters: { cliente } } : {};
			},
		},
		{
			fieldname: "data_inicio",
			label: __("De"),
			fieldtype: "Date",
		},
		{
			fieldname: "data_fim",
			label: __("Até"),
			fieldtype: "Date",
		},
		{
			fieldname: "incluir_prestacoes",
			label: __("Incluir Prestações Agendadas"),
			fieldtype: "Check",
			default: 1,
		},
	],

	formatter: (value, row, column, data, default_formatter) => {
		value = default_formatter(value, row, column, data);

		if (!data) return value;

		if (column.fieldname === "debito" && data.debito) {
			value = `<span style="color: var(--red-600, #c0392b);">${value}</span>`;
		}
		if (column.fieldname === "credito" && data.credito) {
			value = `<span style="color: var(--green-600, #1f7a4d); font-weight: 600;">${value}</span>`;
		}
		if (column.fieldname === "estado" && data.estado === "Atrasado") {
			value = `<span style="color: var(--red-600, #c0392b); font-weight: 600;">${value}</span>`;
		}
		if ((column.fieldname === "multa" || column.fieldname === "juros_mora") && flt(data[column.fieldname])) {
			value = `<span style="color: var(--red-600, #c0392b);">${value}</span>`;
		}
		if (column.fieldname === "tipo") {
			value = `<span style="font-family: var(--emc-font-mono, monospace); font-size: 11px; text-transform: uppercase; letter-spacing: 0.03em;">${value}</span>`;
		}
		return value;
	},
};
