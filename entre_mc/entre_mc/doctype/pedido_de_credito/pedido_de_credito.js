// Copyright (c) 2026, Dércio Bobo and contributors
// For license information, please see license.txt

frappe.ui.form.on("Pedido De Credito", {
	setup(frm) {
		frm.set_query("simulacao_de_credito", () => {
			if (!frm.doc.cliente) return {};
			return {
				query: "entre_mc.entre_mc.doctype.pedido_de_credito.pedido_de_credito.simulacoes_do_cliente",
				filters: { cliente: frm.doc.cliente },
			};
		});

		frm.set_query("promotor", () => ({
			query: "entre_mc.entre_mc.doctype.pedido_de_credito.pedido_de_credito.promotores",
		}));

		frm.set_query("garantias", () => {
			if (!frm.doc.cliente) return {};
			return {
				query: "entre_mc.entre_mc.doctype.pedido_de_credito.pedido_de_credito.garantias_do_cliente",
				filters: { cliente: frm.doc.cliente },
			};
		});
	},

	onload(frm) {
		if (frm.is_new() && !frm.doc.promotor) {
			frm.set_value("promotor", frappe.session.user);
		}
	},

	refresh(frm) {
		render_plano(frm);
		toggle_documentos(frm);

		if (frm.is_new()) return;

		adicionar_botoes_ver(frm);
		render_historico(frm);

		frm.add_custom_button(__("Criar Garantia"), () => {
			frappe.new_doc("Garantia", null, (doc) => {
				doc.cliente = frm.doc.cliente;
			});
			frappe.msgprint(
				__(
					"Depois de gravar a Garantia, volte a este Pedido e adicione-a ao campo Garantias."
				)
			);
		}, __("Criar"));

		if (frm.doc.workflow_state === "Aprovado" && !frm.doc.status) {
			frm.add_custom_button(__("Criar Desembolso"), () => {
				frappe.new_doc("Desembolso", null, (doc) => {
					doc.pedido_de_credito = frm.doc.name;
					// valor_desembolsado é pré-preenchido pelo próprio Desembolso
					// (com o Valor a Desembolsar, já líquido da Taxa Administrativa)
					// quando pedido_de_credito é definido - ver desembolso.js.
					if (frm.doc.data_de_inicio_prevista) {
						doc.data_de_desembolso = frm.doc.data_de_inicio_prevista;
					}
				});
			}, __("Criar"));
		}

		if (frm.doc.status === "Em Curso") {
			frm.add_custom_button(__("Criar Reembolso"), () => {
				frappe.new_doc("Reembolso", null, (doc) => {
					doc.pedido_de_credito = frm.doc.name;
				});
			}, __("Criar"));
		}

		if (["Em Curso", "Incumprimento"].includes(frm.doc.status)) {
			const criar = (doctype) => () => {
				frappe.new_doc(doctype, null, (doc) => {
					doc.pedido_de_credito = frm.doc.name;
					doc.cliente = frm.doc.cliente;
				});
			};
			frm.add_custom_button(__("Perdão de Multa"), criar("Perdao De Multa"), __("Criar"));
			if (!frm.doc.congelado) {
				frm.add_custom_button(__("Congelamento de Dívida"), criar("Congelamento De Divida"), __("Criar"));
			}
			frm.add_custom_button(__("Reestruturação"), criar("Reestruturacao De Credito"), __("Criar"));
			frm.add_custom_button(__("Substituição de Garantia"), criar("Substituicao De Garantia"), __("Criar"));
		}

		if (frm.doc.congelado) {
			frm.dashboard.add_indicator(__("Dívida Congelada"), "blue");
		}
		if (frm.doc.reestruturado) {
			frm.dashboard.add_indicator(__("Reestruturado"), "orange");
		}

		frm.page.set_inner_btn_group_as_primary(__("Criar"));
	},

	produto(frm) {
		render_plano(frm);
		if (!frm.doc.produto) return;
		// taxa_de_juros stays editable (unlike multa/mora), so it can't use
		// fetch_from - the framework forces fetch_from fields read-only.
		frappe.db.get_value("Produto", frm.doc.produto, "taxa_de_juros").then((r) => {
			if (r.message && r.message.taxa_de_juros != null) {
				frm.set_value("taxa_de_juros", r.message.taxa_de_juros);
			}
		});
	},
	capital_solicitado(frm) {
		render_plano(frm);
	},
	taxa_de_juros(frm) {
		render_plano(frm);
	},
	prazo(frm) {
		render_plano(frm);
	},
	frequencia(frm) {
		render_plano(frm);
	},

	simulacao_de_credito(frm) {
		if (!frm.doc.simulacao_de_credito) return;
		frappe.db.get_doc("Simulacao De Credito", frm.doc.simulacao_de_credito).then((sim) => {
			// Assigned directly on frm.doc (not via frm.set_value) so that setting
			// `produto` doesn't trigger its own fetch_from/onchange and overwrite
			// taxa_diaria_de_multa/juros_de_mora with the *current* Produto rates -
			// every field here must come from the simulation as it was saved, not
			// be re-derived from produto.
			Object.assign(frm.doc, {
				produto: sim.produto,
				capital_solicitado: sim.capital_solicitado,
				taxa_de_juros: sim.taxa_de_juros,
				taxa_diaria_de_multa: sim.taxa_diaria_de_multa,
				juros_de_mora: sim.juros_de_mora,
				prazo: sim.prazo,
				finalidade: sim.finalidade,
				frequencia: sim.frequencia,
				promotor: sim.promotor,
			});
			frm.dirty();
			frm.refresh_fields();
			render_plano(frm);
		});
	},
});

function adicionar_botoes_ver(frm) {
	const ver = __("Ver");
	const ativo = ["Em Curso", "Incumprimento"].includes(frm.doc.status);

	if (ativo) {
		frm.add_custom_button(__("Prestações a Receber"), () => {
			frappe.set_route("query-report", "Prestacoes a Receber", {
				pedido_de_credito: frm.doc.name,
			});
		}, ver);
	}

	if (frm.doc.status) {
		frm.add_custom_button(__("Ficha do Crédito"), () => {
			frappe.set_route("ficha-do-credito", frm.doc.name);
		}, ver);
		frm.add_custom_button(__("Reembolsos"), () => {
			frappe.set_route("List", "Reembolso", { pedido_de_credito: frm.doc.name });
		}, ver);
		if (frm.doc.reestruturado) {
			frm.add_custom_button(__("Reestruturações (planos anteriores)"), () => {
				frappe.set_route("List", "Reestruturacao De Credito", { pedido_de_credito: frm.doc.name });
			}, ver);
		}
		frm.add_custom_button(__("Substituições de Garantia"), () => {
			frappe.set_route("List", "Substituicao De Garantia", { pedido_de_credito: frm.doc.name });
		}, ver);
	}

	if (frm.doc.cliente) {
		frm.add_custom_button(__("Extrato do Cliente"), () => {
			frappe.set_route("query-report", "Extrato de Cliente", { cliente: frm.doc.cliente });
		}, ver);
		frm.add_custom_button(__("Ver Cliente"), () => {
			frappe.set_route("Form", "Cliente", frm.doc.cliente);
		}, ver);
	}
}

// Histórico do crédito (mesma cronologia da Ficha do Crédito) e, se foi
// reestruturado, os planos que cada Reestruturação substituiu.
function render_historico(frm) {
	const $historico = frm.fields_dict.historico_html?.$wrapper;
	const $anterior = frm.fields_dict.plano_anterior_html?.$wrapper;
	if (!frm.doc.status || !$historico) return;

	$historico.html(`<div class="text-muted">${__("A carregar...")}</div>`);
	// Garante o renderer partilhado mesmo que o hooks.py/assets ainda não
	// tenham sido recarregados (frappe.require não volta a carregar se já existe).
	const carregar = entre_mc.render_cronologia_html
		? Promise.resolve()
		: new Promise((resolve) => frappe.require("/assets/entre_mc/js/cronologia_view.js", resolve));
	carregar.then(() => frappe.call({
		method: "entre_mc.entre_mc.page.ficha_do_credito.ficha_do_credito.obter_historico",
		args: { pedido_de_credito: frm.doc.name },
		callback: (r) => {
			const dados = r.message || {};
			const desenhar = () => {
				const mostrar = $historico.find(".emc-hist-vencimentos").prop("checked") || false;
				$historico.find(".emc-hist-lista").html(
					entre_mc.render_cronologia_html(dados.cronologia, frm.doc.currency, mostrar)
				);
			};
			$historico.html(`
				<label class="small text-muted" style="font-weight: 500;">
					<input type="checkbox" class="emc-hist-vencimentos"> ${__("Mostrar vencimentos")}
				</label>
				<div class="emc-hist-lista"></div>`);
			$historico.find(".emc-hist-vencimentos").on("change", desenhar);
			desenhar();

			if (!$anterior) return;
			const planos = dados.planos_anteriores || [];
			if (!planos.length) {
				$anterior.html("");
				return;
			}
			const esc = frappe.utils.escape_html;
			$anterior.html(
				planos
					.map(
						(p) => `
						<div style="margin-bottom: 16px;">
							<div style="margin-bottom: 6px;">
								<strong>${__("Plano substituído por")}
									<a href="/app/reestruturacao-de-credito/${encodeURIComponent(p.name)}">${esc(p.name)}</a>
								</strong>
								<span class="text-muted"> - ${frappe.datetime.str_to_user(p.data)}</span>
								${p.motivo ? `<div class="small text-muted">${esc(p.motivo)}</div>` : ""}
							</div>
							${entre_mc.render_plano_html(p.rows, frm.doc.currency)}
						</div>`
					)
					.join("")
			);
		},
	}));
}

function toggle_documentos(frm) {
	const is_new = frm.is_new();

	frm.set_df_property("documentos", "read_only", is_new ? 1 : 0);
	frm.set_df_property(
		"documentos",
		"description",
		is_new ? __("Grave o Pedido de Crédito antes de anexar documentos.") : ""
	);

	const grid = frm.fields_dict.documentos?.grid;
	if (grid) {
		grid.cannot_add_rows = is_new;
		grid.refresh();
	}
}

let preview_timeout = null;

function render_plano(frm) {
	const wrapper = frm.fields_dict.pre_visualizacao_html?.$wrapper;
	if (!wrapper) return;

	if (!frm.is_new() && frm.doc.status === "Em Curso") {
		// Multa/Juros de Mora gravados só ficam atualizados após a tarefa diária
		// ou um Reembolso submetido - aqui recalculamos em memória para que uma
		// prestação que ficou em atraso hoje já apareça correta sem esperar por isso.
		frappe.call({
			method: "entre_mc.entre_mc.doctype.pedido_de_credito.pedido_de_credito.plano_com_encargos_atuais",
			args: { pedido_de_credito: frm.doc.name },
			callback: (r) => {
				wrapper.html(entre_mc.render_plano_html(r.message || frm.doc.plano_de_amortizacao, frm.doc.currency));
			},
		});
		return;
	}

	// Antes da Aprovação (ou antes do Desembolso, sem alterações por gravar) o
	// plano gravado já reflete os dados atuais - mostra-o diretamente. Caso
	// contrário (Rascunho ainda sem plano, ou campos alterados por gravar),
	// recalcula em memória para o utilizador ver o efeito antes de gravar,
	// tal como a pré-visualização de Simulacao De Credito.
	if (!frm.is_dirty() && frm.doc.plano_de_amortizacao?.length) {
		wrapper.html(entre_mc.render_plano_html(frm.doc.plano_de_amortizacao, frm.doc.currency));
		return;
	}

	const { produto, capital_solicitado, taxa_de_juros, prazo, frequencia } = frm.doc;
	if (!produto || !capital_solicitado || !taxa_de_juros || !prazo || !frequencia) {
		wrapper.html(entre_mc.render_plano_html([]));
		return;
	}

	clearTimeout(preview_timeout);
	preview_timeout = setTimeout(() => {
		frappe.call({
			method: "entre_mc.entre_mc.doctype.pedido_de_credito.pedido_de_credito.preview_plano",
			args: { produto, capital_solicitado, taxa_de_juros, prazo, frequencia },
			callback: (r) => {
				wrapper.html(entre_mc.render_plano_html(r.message, frm.doc.currency));
			},
			error: () => {
				wrapper.html(
					`<div class="text-danger">${__("Não foi possível calcular o plano - verifique os limites do produto.")}</div>`
				);
			},
		});
	}, 400);
}
