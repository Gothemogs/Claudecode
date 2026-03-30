"""
Gera o PDF visual do Guia de Uso da Planilha de Estoque do Salão de Beleza.
"""

from fpdf import FPDF


class GuidePDF(FPDF):
    ROSA = (212, 99, 143)
    ROSA_CLARO = (245, 225, 235)
    CINZA = (100, 100, 100)
    BRANCO = (255, 255, 255)
    PRETO = (40, 40, 40)
    VERDE = (76, 175, 80)
    AMARELO = (255, 193, 7)
    VERMELHO = (244, 67, 54)
    ROXO = (142, 68, 173)
    LARANJA = (230, 126, 34)
    AZUL = (52, 152, 219)

    def header(self):
        if self.page_no() > 1:
            self.set_fill_color(*self.ROSA)
            self.rect(0, 0, 210, 8, "F")
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(*self.CINZA)
            self.set_xy(0, 10)
            self.cell(210, 5, "Guia de Uso - Planilha de Controle de Estoque do Salao", align="C")

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*self.CINZA)
        self.cell(0, 10, f"Página {self.page_no()}/{{nb}}", align="C")

    def section_title(self, icon, title, color):
        self.set_fill_color(*color)
        self.rounded_rect(10, self.get_y(), 190, 12, 3, "F")
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(*self.BRANCO)
        self.set_x(15)
        self.cell(0, 12, f"  {icon}  {title}")
        self.ln(16)

    def subtitle(self, text):
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*self.ROSA)
        self.set_x(15)
        self.cell(0, 7, text)
        self.ln(8)

    def body_text(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*self.PRETO)
        self.set_x(15)
        self.multi_cell(180, 5.5, text)
        self.ln(2)

    def bullet(self, text, indent=20):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*self.PRETO)
        self.set_x(indent)
        self.cell(5, 5.5, "-")
        self.set_x(indent + 5)
        self.multi_cell(170, 5.5, text)
        self.ln(1)

    def numbered_step(self, number, text):
        y = self.get_y()
        self.set_fill_color(*self.ROSA)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*self.BRANCO)
        self.set_xy(18, y)
        self.cell(8, 8, str(number), align="C", fill=True)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*self.PRETO)
        self.set_xy(30, y)
        self.multi_cell(165, 5.5, text)
        self.ln(3)

    def status_badge(self, label, color, description):
        y = self.get_y()
        self.set_fill_color(*color)
        self.rounded_rect(20, y, 30, 7, 2, "F")
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*self.BRANCO)
        self.set_xy(20, y)
        self.cell(30, 7, label, align="C")
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*self.PRETO)
        self.set_xy(55, y)
        self.cell(140, 7, description)
        self.ln(10)

    def info_box(self, text, color=None):
        if color is None:
            color = self.ROSA_CLARO
        self.set_fill_color(*color)
        y = self.get_y()
        self.rounded_rect(15, y, 180, 22, 3, "F")
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(*self.PRETO)
        self.set_xy(20, y + 3)
        self.multi_cell(170, 5, text)
        self.set_y(y + 25)

    def flow_box(self, title, steps, color):
        y = self.get_y()
        self.set_fill_color(*color)
        self.rounded_rect(15, y, 180, 8, 2, "F")
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*self.BRANCO)
        self.set_xy(15, y)
        self.cell(180, 8, title, align="C")
        self.ln(10)
        for s in steps:
            self.set_font("Helvetica", "", 9)
            self.set_text_color(*self.PRETO)
            self.set_x(22)
            self.multi_cell(170, 5, s)
            self.ln(1)
        self.ln(3)

    def rounded_rect(self, x, y, w, h, r, style=""):
        # Simple rounded rect approximation
        if style == "F":
            self.rect(x, y, w, h, "F")


pdf = GuidePDF()
pdf.alias_nb_pages()
pdf.set_auto_page_break(auto=True, margin=20)

# ═══════════════════════════════════════════════════════════════════════════════
# CAPA
# ═══════════════════════════════════════════════════════════════════════════════
pdf.add_page()
pdf.set_fill_color(*GuidePDF.ROSA)
pdf.rect(0, 0, 210, 297, "F")

# Faixa central branca
pdf.set_fill_color(255, 255, 255)
pdf.rect(0, 80, 210, 140, "F")

pdf.set_y(95)
pdf.set_font("Helvetica", "B", 32)
pdf.set_text_color(*GuidePDF.ROSA)
pdf.cell(0, 15, "GUIA DE USO", align="C")
pdf.ln(18)

pdf.set_font("Helvetica", "", 14)
pdf.set_text_color(*GuidePDF.CINZA)
pdf.cell(0, 8, "Planilha de Controle de Estoque", align="C")
pdf.ln(10)
pdf.set_font("Helvetica", "B", 16)
pdf.set_text_color(*GuidePDF.PRETO)
pdf.cell(0, 10, "Salao de Beleza", align="C")
pdf.ln(20)

# Linha decorativa
pdf.set_fill_color(*GuidePDF.ROSA)
pdf.rect(70, pdf.get_y(), 70, 1.5, "F")
pdf.ln(15)

pdf.set_font("Helvetica", "", 10)
pdf.set_text_color(*GuidePDF.CINZA)
pdf.cell(0, 6, "Versao 1.0  |  Marco 2026", align="C")
pdf.ln(8)
pdf.cell(0, 6, "Arquivo: Estoque_Salao_de_Beleza.xlsx", align="C")

# Ícones das 5 abas na parte inferior
pdf.set_y(230)
abas = [
    ("Estoque", GuidePDF.ROSA),
    ("Movimentacoes", GuidePDF.ROXO),
    ("Fornecedores", GuidePDF.VERDE),
    ("Compras", GuidePDF.LARANJA),
    ("Dashboard", GuidePDF.AZUL),
]
x_start = 20
for i, (nome, cor) in enumerate(abas):
    x = x_start + i * 36
    pdf.set_fill_color(*cor)
    pdf.rect(x, 230, 32, 20, "F")
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(255, 255, 255)
    pdf.set_xy(x, 235)
    pdf.cell(32, 8, nome, align="C")


# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA 2  - VISÃO GERAL
# ═══════════════════════════════════════════════════════════════════════════════
pdf.add_page()
pdf.set_y(22)

pdf.section_title(">>", "VISAO GERAL DA PLANILHA", GuidePDF.ROSA)

pdf.body_text(
    "A planilha Estoque_Salao_de_Beleza.xlsx foi criada para facilitar o "
    "controle completo dos produtos do seu salao. Ela possui 5 abas que "
    "trabalham juntas para dar visibilidade total do seu estoque."
)
pdf.ln(3)

# Quadro das 5 abas
tab_info = [
    ("1. Estoque de Produtos", GuidePDF.ROSA, "Cadastro completo de todos os produtos com quantidade, preco, validade e status automatico."),
    ("2. Movimentacoes", GuidePDF.ROXO, "Historico de todas as entradas e saidas de produtos no salao."),
    ("3. Fornecedores", GuidePDF.VERDE, "Cadastro de fornecedores com contato, CNPJ e prazo de entrega."),
    ("4. Lista de Compras", GuidePDF.LARANJA, "Controle de pedidos de reposicao com acompanhamento de status."),
    ("5. Dashboard", GuidePDF.AZUL, "Painel automatico com indicadores e resumo por categoria."),
]

for nome, cor, desc in tab_info:
    y = pdf.get_y()
    pdf.set_fill_color(*cor)
    pdf.rect(15, y, 4, 14, "F")
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*cor)
    pdf.set_xy(22, y)
    pdf.cell(60, 7, nome)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*GuidePDF.PRETO)
    pdf.set_xy(22, y + 7)
    pdf.cell(170, 7, desc)
    pdf.ln(18)


# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA 3  - ABA ESTOQUE DE PRODUTOS
# ═══════════════════════════════════════════════════════════════════════════════
pdf.add_page()
pdf.set_y(22)

pdf.section_title("01", "ABA: ESTOQUE DE PRODUTOS", GuidePDF.ROSA)

pdf.subtitle("O que contem:")
pdf.body_text(
    "Cada linha representa um produto do salao com: codigo, nome, categoria, "
    "marca, unidade de medida, quantidade atual, quantidade minima, status "
    "automatico, preco de custo, preco de venda, fornecedor, validade e localizacao."
)

pdf.subtitle("Como cadastrar um novo produto:")
pdf.numbered_step(1, "Va ate a ultima linha preenchida e adicione uma nova linha abaixo.")
pdf.numbered_step(2, "Preencha o codigo seguindo o padrao (P001, P002, P003...).")
pdf.numbered_step(3, "Preencha todas as colunas. A coluna STATUS (H) nao precisa ser preenchida  - ela calcula automaticamente.")
pdf.numbered_step(4, "Defina a Qtd. Minima conforme o consumo medio do seu salao.")

pdf.ln(3)
pdf.subtitle("Como funciona o Status Automatico:")
pdf.body_text("A coluna Status muda de cor automaticamente conforme a quantidade:")
pdf.ln(2)

pdf.status_badge("OK", GuidePDF.VERDE, "Estoque acima de 1,5x a quantidade minima. Tudo certo!")
pdf.status_badge("ATENCAO", GuidePDF.AMARELO, "Estoque entre 1x e 1,5x o minimo. Fique atenta.")
pdf.status_badge("REPOR", GuidePDF.VERMELHO, "Estoque igual ou abaixo do minimo. Compre ja!")

pdf.ln(2)
pdf.info_box(
    "DICA: Use os filtros no cabecalho para visualizar apenas uma categoria, "
    "marca ou status especifico. Clique na setinha ao lado do nome da coluna."
)


# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA 4  - ABA MOVIMENTAÇÕES
# ═══════════════════════════════════════════════════════════════════════════════
pdf.add_page()
pdf.set_y(22)

pdf.section_title("02", "ABA: MOVIMENTACOES", GuidePDF.ROXO)

pdf.body_text(
    "Esta aba e o historico completo de tudo que entra e sai do estoque. "
    "E essencial para rastrear o consumo e identificar perdas."
)

pdf.ln(2)
pdf.subtitle("Como registrar uma movimentacao:")
pdf.numbered_step(1, "Preencha a DATA da movimentacao.")
pdf.numbered_step(2, "Informe o CODIGO e o NOME do produto (mesmo codigo da aba Estoque).")
pdf.numbered_step(3, "Selecione o TIPO na lista suspensa: Entrada ou Saida.")
pdf.numbered_step(4, "Informe a QUANTIDADE movimentada.")
pdf.numbered_step(5, "Selecione o MOTIVO: Compra, Uso interno, Venda direta, Devolucao, Perda/Avaria ou Amostra.")
pdf.numbered_step(6, "Preencha o RESPONSAVEL (quem fez a movimentacao).")
pdf.numbered_step(7, "IMPORTANTE: Apos registrar aqui, atualize a Qtd. Atual na aba Estoque de Produtos.")

pdf.ln(3)

# Tabela visual de tipos
pdf.subtitle("Tipos de Movimentacao:")
y = pdf.get_y()
pdf.set_fill_color(198, 239, 206)  # verde claro
pdf.rect(20, y, 80, 10, "F")
pdf.set_font("Helvetica", "B", 10)
pdf.set_text_color(*GuidePDF.PRETO)
pdf.set_xy(20, y)
pdf.cell(80, 10, "  ENTRADA  =  produto chegou", align="L")

pdf.set_fill_color(255, 199, 206)  # rosa claro
pdf.rect(105, y, 80, 10, "F")
pdf.set_xy(105, y)
pdf.cell(80, 10, "  SAIDA  =  produto saiu", align="L")
pdf.ln(15)

pdf.info_box(
    "IMPORTANTE: Nunca delete linhas desta aba! Ela serve como comprovante. "
    "Se houver diferenca entre o estoque fisico e a planilha, consulte aqui."
)


# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA 5  - FORNECEDORES + LISTA DE COMPRAS
# ═══════════════════════════════════════════════════════════════════════════════
pdf.add_page()
pdf.set_y(22)

pdf.section_title("03", "ABA: FORNECEDORES", GuidePDF.VERDE)

pdf.body_text(
    "Cadastro centralizado de todos os fornecedores do salao. "
    "Mantenha sempre atualizado para agilizar pedidos de reposicao."
)

pdf.subtitle("Colunas disponiveis:")
pdf.bullet("Codigo (F001, F002...), Nome, CNPJ, Contato, Telefone, E-mail")
pdf.bullet("Categorias que fornece (ex: Cabelo, Unha, Descartaveis)")
pdf.bullet("Prazo de Entrega em dias  - ajuda a planejar quando pedir")

pdf.ln(8)

pdf.section_title("04", "ABA: LISTA DE COMPRAS", GuidePDF.LARANJA)

pdf.body_text(
    "Controle os pedidos de reposicao do salao. Sempre que um produto "
    "estiver marcado como 'REPOR' no estoque, adicione-o aqui."
)

pdf.subtitle("Fluxo de uso:")
pdf.numbered_step(1, "Adicione o produto com data, quantidade desejada, fornecedor e preco estimado.")
pdf.numbered_step(2, "Marque o Status como PENDENTE.")
pdf.numbered_step(3, "Ao fazer o pedido ao fornecedor, mude para PEDIDO FEITO.")
pdf.numbered_step(4, "Quando a mercadoria chegar, mude para RECEBIDO e preencha a data.")
pdf.numbered_step(5, "Registre a entrada na aba Movimentacoes e atualize o Estoque.")

pdf.ln(3)

# Status visual
y = pdf.get_y()
status_flow = [
    ("Pendente", (255, 235, 130)),
    ("Pedido Feito", (173, 216, 255)),
    ("Recebido", (180, 235, 180)),
]
x = 25
for label, cor in status_flow:
    pdf.set_fill_color(*cor)
    pdf.rect(x, y, 42, 10, "F")
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*GuidePDF.PRETO)
    pdf.set_xy(x, y)
    pdf.cell(42, 10, label, align="C")
    if label != "Recebido":
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_xy(x + 42, y)
        pdf.cell(12, 10, "->", align="C")
    x += 54
pdf.ln(18)


# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA 6  - DASHBOARD + FLUXO DIÁRIO
# ═══════════════════════════════════════════════════════════════════════════════
pdf.add_page()
pdf.set_y(22)

pdf.section_title("05", "ABA: DASHBOARD", GuidePDF.AZUL)

pdf.body_text(
    "Painel automatico que consolida todas as informacoes do estoque. "
    "NAO EDITE esta aba  - todos os valores sao formulas automaticas."
)

pdf.subtitle("Indicadores exibidos:")
pdf.bullet("Total de produtos cadastrados")
pdf.bullet("Quantidade de produtos OK, em Atencao e para Repor")
pdf.bullet("Valor total do estoque (custo e venda)")
pdf.bullet("Numero de entradas e saidas registradas")
pdf.bullet("Resumo por categoria: Cabelo, Unha, Pele/Estetica, Descartaveis")

pdf.ln(6)

# ── FLUXO DIÁRIO ──
pdf.section_title(">>", "FLUXO DO DIA A DIA", GuidePDF.ROSA)
pdf.ln(2)

pdf.flow_box("USOU UM PRODUTO NO ATENDIMENTO?", [
    "1. Registre a SAIDA na aba Movimentacoes (tipo: Saida, motivo: Uso interno)",
    "2. Atualize a Qtd. Atual na aba Estoque de Produtos (diminua a quantidade)",
], GuidePDF.ROXO)

pdf.flow_box("PRECISA REPOR O ESTOQUE?", [
    "1. Consulte o Dashboard  - veja quais itens estao em vermelho",
    "2. Adicione esses itens na aba Lista de Compras com status Pendente",
    "3. Entre em contato com o fornecedor (consulte a aba Fornecedores)",
], GuidePDF.LARANJA)

pdf.flow_box("RECEBEU MERCADORIA?", [
    "1. Registre a ENTRADA na aba Movimentacoes (tipo: Entrada, motivo: Compra)",
    "2. Atualize a Qtd. Atual na aba Estoque de Produtos (aumente a quantidade)",
    "3. Na Lista de Compras, mude o status para Recebido e preencha a data",
], GuidePDF.VERDE)


# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA 7  - DICAS E BOAS PRÁTICAS
# ═══════════════════════════════════════════════════════════════════════════════
pdf.add_page()
pdf.set_y(22)

pdf.section_title("!!", "DICAS E BOAS PRATICAS", GuidePDF.ROSA)
pdf.ln(2)

dicas = [
    ("Faca backup semanalmente",
     "Salve uma copia da planilha com a data no nome do arquivo. "
     "Ex: Estoque_Salao_2026-03-30.xlsx"),
    ("Inventario fisico mensal",
     "Pelo menos 1x por mes, conte os produtos fisicamente e compare "
     "com a planilha. Ajuste as diferencas."),
    ("Nunca delete movimentacoes",
     "A aba Movimentacoes e seu historico e comprovante. Se errou um "
     "lancamento, faca um novo lancamento de ajuste."),
    ("Atencao a validade",
     "Verifique regularmente a coluna Validade na aba Estoque. "
     "Produtos vencidos devem ser descartados e registrados como Perda/Avaria."),
    ("Use os filtros",
     "Todas as abas possuem filtros automaticos no cabecalho. "
     "Use para visualizar apenas o que precisa (ex: so produtos para repor)."),
    ("Defina responsaveis",
     "Escolha uma pessoa fixa para registrar as movimentacoes. "
     "Isso evita esquecimentos e duplicidades."),
    ("Revise os precos periodicamente",
     "Atualize os precos de custo e venda conforme as notas fiscais "
     "dos fornecedores para manter a margem correta."),
]

for titulo, desc in dicas:
    y = pdf.get_y()
    pdf.set_fill_color(*GuidePDF.ROSA_CLARO)
    pdf.rect(15, y, 180, 18, "F")
    pdf.set_fill_color(*GuidePDF.ROSA)
    pdf.rect(15, y, 4, 18, "F")
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*GuidePDF.ROSA)
    pdf.set_xy(22, y + 1)
    pdf.cell(170, 6, titulo)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*GuidePDF.PRETO)
    pdf.set_xy(22, y + 8)
    pdf.multi_cell(168, 4.5, desc)
    pdf.set_y(y + 22)

pdf.ln(8)

# Rodapé final
y = pdf.get_y()
pdf.set_fill_color(*GuidePDF.ROSA)
pdf.rect(15, y, 180, 1, "F")
pdf.ln(5)
pdf.set_font("Helvetica", "I", 9)
pdf.set_text_color(*GuidePDF.CINZA)
pdf.cell(0, 5, "Documento gerado automaticamente  |  Estoque_Salao_de_Beleza.xlsx  |  Marco 2026", align="C")


# ═══════════════════════════════════════════════════════════════════════════════
# SALVAR
# ═══════════════════════════════════════════════════════════════════════════════
filename = "Guia_de_Uso_Estoque_Salao.pdf"
pdf.output(filename)
print(f"PDF '{filename}' gerado com sucesso!")
