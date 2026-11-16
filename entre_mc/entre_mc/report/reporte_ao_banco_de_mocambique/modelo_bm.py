# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

"""Preenche o modelo Excel do Banco de Moçambique ("Reporte Periódico de
Informações de Microfinanças") com os dados de um mês.

O ficheiro `modelo_bm.xlsx` ao lado deste módulo é o modelo fornecido pela
instituição, tal e qual. Em vez de o redesenhar, este módulo altera só o XML
da folha dentro do próprio ficheiro: tudo o resto (tipos de letra, limites,
larguras, emblema, configuração de impressão) fica exatamente como no modelo.

Só três coisas mudam:

- os textos do cabeçalho (período e identificação da instituição);
- as linhas da tabela (o modelo traz `LINHAS_NO_MODELO` linhas em branco - com
  mais operações do que isso, são acrescentadas linhas iguais e o rodapé,
  assinatura e notas explicativas descem na mesma medida);
- o nome da folha (o mês).

Não depende do Frappe, para poder ser testado isoladamente.
"""

import datetime
import io
import os
import re
import zipfile
from xml.sax.saxutils import escape

MODELO = os.path.join(os.path.dirname(__file__), "modelo_bm.xlsx")
FOLHA = "xl/worksheets/sheet1.xml"
LIVRO = "xl/workbook.xml"

PRIMEIRA_LINHA = 36
LINHAS_NO_MODELO = 8  # linhas 36 a 43 do modelo
ALTURA_DA_LINHA = "28.5"

# Estilo (índice em styles.xml do modelo) de cada coluna da tabela, e o tipo
# de valor que leva. Os estilos são os das linhas em branco do modelo, exceto
# K, que usa o mesmo formato numérico de J em vez de "Geral".
COLUNAS = (
	("A", 13, "texto"),  # Nº da Operação
	("B", 14, "texto"),  # Nome do Cliente
	("C", 15, "data"),  # Data de Desembolso
	("D", 16, "numero"),  # Montante do Desembolso
	("E", 17, "texto"),  # Finalidade do Crédito
	("F", 16, "numero"),  # Valor da Prestação
	("G", 17, "texto"),  # Periodicidade dos Pagamentos
	("H", 18, "data"),  # Prazo de Reembolso
	("I", 19, "percentagem"),  # Taxa de Juro
	("J", 20, "numero"),  # Crédito em Dívida
	("K", 20, "numero"),  # Crédito em Atraso
	("L", 17, "numero"),  # Dias em Atraso
	("M", 17, "texto"),  # PPEs
)

MESES = (
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
)

EPOCA_EXCEL = datetime.date(1899, 12, 30)


def data_por_extenso(data):
	"""17 de Abril de 2026"""
	if not data:
		return ""
	data = _data(data)
	return f"{data.day} de {MESES[data.month - 1]} de {data.year}"


def textos_do_cabecalho(inicio, fim, instituicao):
	"""Texto de cada célula do cabeçalho, no formato exato do modelo."""
	i = instituicao
	return {
		"A11": f"DATA: {_data(inicio):%d-%m-%Y} á  {_data(fim):%d-%m-%Y}",
		"A15": f"Denominação: {i.get('denominacao') or ''}",
		"A16": f"Endereço : {i.get('endereco') or ''}",
		"A17": f"Provincia: {i.get('provincia') or ''}, Distrito {i.get('distrito') or ''}",
		"A18": f"Telefone: {i.get('telefone') or ''}",
		"A19": f"Fax: {(i.get('fax') or '').ljust(102)} E-mail: {i.get('email') or ''}",
		"A20": f"Nº de Trabalhadores: {i.get('numero_de_trabalhadores') or ''}",
		"A21": f"Data de Início das Actividades: {data_por_extenso(i.get('data_de_inicio_das_actividades'))}",
		"A22": f"Nome do Responsável pela Gestão da Instituição: {i.get('responsavel') or ''}",
		"A23": f"Instituição Representada:  {i.get('instituicao_representada') or ''}",
	}


def gerar(inicio, fim, instituicao, linhas):
	"""Devolve os bytes do .xlsx preenchido.

	`linhas`: lista de listas com os 13 valores de cada operação, pela ordem de
	`COLUNAS`. Datas como `date`/ISO, taxa de juro em percentagem (ex.: 10 para
	10%)."""
	with zipfile.ZipFile(MODELO) as origem:
		partes = {info: origem.read(info.filename) for info in origem.infolist()}

	saida = io.BytesIO()
	with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as destino:
		for info, conteudo in partes.items():
			if info.filename == FOLHA:
				conteudo = _preencher_folha(
					conteudo.decode("utf-8"), textos_do_cabecalho(inicio, fim, instituicao), linhas
				).encode("utf-8")
			elif info.filename == LIVRO:
				conteudo = _renomear_folha(conteudo.decode("utf-8"), MESES[_data(fim).month - 1]).encode("utf-8")
			destino.writestr(info.filename, conteudo)
	return saida.getvalue()


def _preencher_folha(xml, cabecalho, linhas):
	for celula, texto in cabecalho.items():
		xml, n = re.subn(
			rf'<c r="{celula}" s="(\d+)" t="s"><v>\d+</v></c>',
			lambda m: _celula(celula, m.group(1), texto, "texto"),
			xml,
		)
		if n != 1:
			raise ValueError(f"Célula {celula} não encontrada no modelo")

	total = max(len(linhas), LINHAS_NO_MODELO)
	deslocamento = total - LINHAS_NO_MODELO
	ultima_do_modelo = PRIMEIRA_LINHA + LINHAS_NO_MODELO - 1

	inicio = xml.index(f'<row r="{PRIMEIRA_LINHA}" ')
	fim = xml.index(f'<row r="{ultima_do_modelo + 1}" ')
	fim_dos_dados = xml.index("</sheetData>")

	novas = "".join(
		_linha(PRIMEIRA_LINHA + n, linhas[n] if n < len(linhas) else None) for n in range(total)
	)
	rodape = _deslocar_linhas(xml[fim:fim_dos_dados], deslocamento)
	resto = _deslocar_merges(xml[fim_dos_dados:], ultima_do_modelo, deslocamento)
	return xml[:inicio] + novas + rodape + resto


def _linha(numero, valores):
	celulas = "".join(
		_celula(f"{coluna}{numero}", estilo, valores[n] if valores else None, tipo)
		for n, (coluna, estilo, tipo) in enumerate(COLUNAS)
	)
	return (
		f'<row r="{numero}" spans="1:13" s="10" customFormat="1" ht="{ALTURA_DA_LINHA}">' f"{celulas}</row>"
	)


def _celula(ref, estilo, valor, tipo):
	if valor is None or valor == "":
		return f'<c r="{ref}" s="{estilo}"/>'
	if tipo == "data":
		return f'<c r="{ref}" s="{estilo}"><v>{(_data(valor) - EPOCA_EXCEL).days}</v></c>'
	if tipo == "percentagem":
		# O modelo formata a taxa como "0%": uma taxa com casas decimais
		# (ex.: 12,5%) seria arredondada, por isso vai como texto.
		valor = float(valor)
		if valor == int(valor):
			return f'<c r="{ref}" s="{estilo}"><v>{valor / 100!r}</v></c>'
		valor, tipo = f"{valor:g}%".replace(".", ","), "texto"
	if tipo == "numero":
		return f'<c r="{ref}" s="{estilo}"><v>{float(valor)!r}</v></c>'
	return (
		f'<c r="{ref}" s="{estilo}" t="inlineStr"><is><t xml:space="preserve">'
		f"{escape(_sem_caracteres_invalidos(str(valor)))}</t></is></c>"
	)


def _deslocar_linhas(xml, deslocamento):
	"""Soma `deslocamento` ao número de cada linha (e das suas células)."""
	if not deslocamento:
		return xml
	xml = re.sub(r'<row r="(\d+)"', lambda m: f'<row r="{int(m.group(1)) + deslocamento}"', xml)
	return re.sub(
		r'<c r="([A-Z]+)(\d+)"', lambda m: f'<c r="{m.group(1)}{int(m.group(2)) + deslocamento}"', xml
	)


def _deslocar_merges(xml, a_partir_de, deslocamento):
	"""Desce as células unidas que ficam abaixo da tabela (a linha da assinatura)."""
	if not deslocamento:
		return xml

	def mover(m):
		c1, l1, c2, l2 = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
		if l1 > a_partir_de:
			l1, l2 = l1 + deslocamento, l2 + deslocamento
		return f'<mergeCell ref="{c1}{l1}:{c2}{l2}"/>'

	return re.sub(r'<mergeCell ref="([A-Z]+)(\d+):([A-Z]+)(\d+)"/>', mover, xml)


def _renomear_folha(xml, nome):
	xml, n = re.subn(r'(<sheet name=")[^"]*(")', lambda m: m.group(1) + escape(nome) + m.group(2), xml, count=1)
	if n != 1:
		raise ValueError("Folha não encontrada no modelo")
	return xml


def _data(valor):
	if isinstance(valor, datetime.datetime):
		return valor.date()
	if isinstance(valor, datetime.date):
		return valor
	return datetime.date.fromisoformat(str(valor)[:10])


def _sem_caracteres_invalidos(texto):
	"""O XML não aceita caracteres de controlo (um nome colado de outro sítio
	pode trazê-los) - o Excel recusaria abrir o ficheiro."""
	return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", texto)
