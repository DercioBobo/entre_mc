# Entre MC (entre_mc)

**Entre MicroCréditos** — aplicação de gestão de microcrédito construída sobre o Frappe Framework, instalável num bench com ERPNext.

## Instalação

```bash
bench get-app entre_mc https://github.com/<org>/entre_mc.git
bench --site <site> install-app entre_mc
```

## Módulos

Cobre o ciclo de vida completo do microcrédito: produtos, proponentes, clientes, simulações,
pedidos de crédito com aprovação em dois níveis, desembolso, garantias (com execução e
devolução) e reembolso com amortização (modelos Constante, Decrescente e Misto).

Dados da instituição e moeda vêm da **Company** do ERPNext. A numeração de cada documento
segue a série padrão do Frappe (ex.: `PC-.YY.-.##` para Pedido de Crédito), ajustável em
Setup → Naming Series. **MC Settings** guarda apenas o que é específico do microcrédito:
empresa por defeito, frequência padrão e dias de tolerância antes de multa/juros de mora.

## License

mit
