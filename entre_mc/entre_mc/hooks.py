app_name = "entre_mc"
app_title = "Entre MC"
app_publisher = "Dércio Bobo"
app_description = "Entre MicroCréditos - Gestão de Microcrédito para Frappe/ERPNext"
app_email = "derciobob@gmail.com"
app_license = "mit"
app_icon = "octicon octicon-credit-card"
app_color = "#2c7a4b"

# Apps
# ------------------

# required_apps = []
# entre_mc has no hard dependency on ERPNext doctypes - it installs on a
# plain Frappe bench, but is designed to sit alongside ERPNext.

# Fixtures
# ------------------
# Exported so `bench get-app` + `bench migrate` reproduces roles and the
# Pedido de Crédito approval workflow out of the box. All are safely
# editable afterwards from the UI (Role / Workflow / Workflow State lists).

fixtures = [
	{
		"dt": "Role",
		"filters": [
			[
				"name",
				"in",
				[
					"Analista de Crédito",
					"Gestor de Crédito",
					"Oficial de Crédito",
					"Tesoureiro",
				],
			]
		],
	},
	{
		"dt": "Workflow Action Master",
		"filters": [
			["name", "in", ["Enviar para Aprovação", "Aprovar", "Rejeitar"]]
		],
	},
	{
		"dt": "Workflow State",
		"filters": [
			[
				"name",
				"in",
				[
					"Rascunho",
					"Pendente Aprovação 1",
					"Pendente Aprovação 2",
					"Aprovado",
					"Rejeitado",
				],
			]
		],
	},
	{
		"dt": "Workflow",
		"filters": [["name", "in", ["Pedido de Crédito Workflow"]]],
	},
	{
		"dt": "Print Format",
		"filters": [
			[
				"name",
				"in",
				[
					"Ficha de Cadastro e Avaliação de Risco",
					"Pedido de Crédito - Declaração",
					"Simulação de Crédito",
					"Auto de Entrega e Termo de Fiel Depositário",
					"Recibo de Quitação e Devolução da Garantia",
				],
			]
		],
	},
]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
app_include_css = "/assets/entre_mc/css/entre_mc.css"
app_include_js = [
	"/assets/entre_mc/js/amortizacao_view.js",
	"/assets/entre_mc/js/garantia_view.js",
]

# Document Events
# ---------------
# All lifecycle logic (validate/on_submit/on_update/...) lives directly on
# each doctype's own controller class (entre_mc/entre_mc/doctype/*/*.py) -
# no cross-doctype doc_events are needed since every doctype here belongs
# to this app.

# Scheduled Tasks
# ---------------

scheduler_events = {
	"daily": [
		"entre_mc.entre_mc.tasks.atualizar_atrasos",
	],
}

# Naming series follow the standard Frappe pattern per doctype (autoname:
# "naming_series:") and are editable via Setup -> Naming Series. Proponente
# and Cliente are named after the person instead (autoname: "field:...").
