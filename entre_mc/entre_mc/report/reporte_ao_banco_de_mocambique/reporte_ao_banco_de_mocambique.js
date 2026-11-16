// Copyright (c) 2026, Dércio Bobo and contributors
// For license information, please see license.txt

(() => {
	const MESES = [
		"Janeiro",
		"Fevereiro",
		"Março",
		"Abril",
		"Maio",
		"Junho",
		"Julho",
		"Agosto",
		"Setembro",
		"Outubro",
		"Novembro",
		"Dezembro",
	];

	// O reporte é feito depois de o mês fechar: por omissão, o mês anterior.
	const mes_anterior = frappe.datetime.str_to_obj(frappe.datetime.add_months(frappe.datetime.month_start(), -1));

	frappe.query_reports["Reporte ao Banco de Mocambique"] = {
		filters: [
			{
				fieldname: "mes",
				label: __("Mês"),
				fieldtype: "Select",
				options: MESES.join("\n"),
				default: MESES[mes_anterior.getMonth()],
				reqd: 1,
			},
			{
				fieldname: "ano",
				label: __("Ano"),
				fieldtype: "Int",
				default: mes_anterior.getFullYear(),
				reqd: 1,
			},
		],

		onload(report) {
			report.page.add_inner_button(__("Exportar Modelo BM (Excel)"), () => {
				const filters = report.get_values();
				if (!filters) return;
				open_url_post(frappe.request.url, {
					cmd: "entre_mc.entre_mc.report.reporte_ao_banco_de_mocambique.reporte_ao_banco_de_mocambique.exportar_modelo",
					mes: filters.mes,
					ano: filters.ano,
				});
			}).addClass("btn-primary");
		},
	};
})();
