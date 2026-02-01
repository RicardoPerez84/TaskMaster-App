import flet as ft
import sqlite3
from datetime import datetime, timedelta
import calendar

# --- 1. BANCO DE DADOS ---
class Database:
    def __init__(self):
        self.conn = sqlite3.connect("banco_tarefas_v8.db", check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.criar_tabela()

    def criar_tabela(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS tarefas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT,
                status TEXT,
                responsavel TEXT,
                data_limite TEXT,
                data_criacao TEXT,
                data_conclusao TEXT,
                recorrencia TEXT
            )
        """)
        self.conn.commit()

    def adicionar(self, titulo, responsavel, data_limite, recorrencia):
        agora = datetime.now().strftime("%d/%m/%Y %H:%M")
        self.cursor.execute("""
            INSERT INTO tarefas (titulo, status, responsavel, data_limite, data_criacao, data_conclusao, recorrencia) 
            VALUES (?, ?, ?, ?, ?, ?, ?)""", 
            (titulo, "pendente", responsavel, data_limite, agora, "", recorrencia)
        )
        self.conn.commit()

    def listar_por_status(self, status):
        self.cursor.execute("SELECT * FROM tarefas WHERE status = ?", (status,))
        return self.cursor.fetchall()
    
    def listar_todas(self):
        self.cursor.execute("SELECT * FROM tarefas")
        return self.cursor.fetchall()

    def buscar_tudo(self, termo):
        termo = f"%{termo.lower()}%"
        query = """
            SELECT * FROM tarefas 
            WHERE LOWER(responsavel) LIKE ? OR LOWER(titulo) LIKE ?
            ORDER BY 
                CASE WHEN status = 'pendente' THEN 0 ELSE 1 END ASC,
                id DESC
        """
        self.cursor.execute(query, (termo, termo))
        return self.cursor.fetchall()
    
    def listar_nomes_usados(self):
        self.cursor.execute("SELECT DISTINCT responsavel FROM tarefas")
        return [row[0] for row in self.cursor.fetchall() if row[0]]

    def buscar_alertas_reais(self):
        self.cursor.execute("SELECT * FROM tarefas WHERE status = 'pendente'")
        todas_pendentes = self.cursor.fetchall()
        
        alertas = []
        hoje = datetime.now().date()
        amanha = hoje + timedelta(days=1)
        
        for t in todas_pendentes:
            data_str = t[4] 
            if data_str:
                try:
                    dt_tarefa = datetime.strptime(data_str, "%d/%m/%Y").date()
                    if dt_tarefa <= amanha:
                        alertas.append(t)
                except:
                    pass 
        return alertas

    def atualizar_status(self, id_tarefa, novo_status):
        data_fim = datetime.now().strftime("%d/%m/%Y %H:%M") if novo_status == "concluida" else ""
        self.cursor.execute("""
            UPDATE tarefas SET status = ?, data_conclusao = ? WHERE id = ?""", 
            (novo_status, data_fim, id_tarefa)
        )
        self.conn.commit()

        if novo_status == "concluida":
            self.cursor.execute("SELECT * FROM tarefas WHERE id = ?", (id_tarefa,))
            tarefa = self.cursor.fetchone()
            recorrencia = tarefa[7]
            data_limite_str = tarefa[4]

            if recorrencia and recorrencia != "Não repete" and data_limite_str:
                try:
                    dt_atual = datetime.strptime(data_limite_str, "%d/%m/%Y")
                    nova_data = None
                    if recorrencia == "Diária": nova_data = dt_atual + timedelta(days=1)
                    elif recorrencia == "Semanal": nova_data = dt_atual + timedelta(weeks=1)
                    elif recorrencia == "Mensal":
                        mes = dt_atual.month % 12 + 1
                        ano = dt_atual.year + (dt_atual.month // 12)
                        dia = min(dt_atual.day, calendar.monthrange(ano, mes)[1])
                        nova_data = dt_atual.replace(year=ano, month=mes, day=dia)
                    elif recorrencia == "Anual": nova_data = dt_atual.replace(year=dt_atual.year + 1)

                    if nova_data:
                        self.adicionar(tarefa[1], tarefa[3], nova_data.strftime("%d/%m/%Y"), recorrencia)
                except: pass

    def excluir(self, id_tarefa):
        self.cursor.execute("DELETE FROM tarefas WHERE id = ?", (id_tarefa,))
        self.conn.commit()

db = Database()

# --- 2. FRONTEND ---
def main(page: ft.Page):
    page.title = "Tarefas do dia a dia"
    page.bgcolor = "white"
    page.window_full_screen = True 
    page.window_width = 450
    page.window_height = 800
    page.padding = 0
    page.vertical_alignment = "start"

    data_selecionada_temp = [None] 

    coluna_abas = ft.Column()
    lista_pendentes = ft.Column()
    lista_concluidas = ft.Column(visible=False)
    area_estatisticas = ft.Column(visible=False)
    area_graficos = ft.Column(visible=False)
    coluna_busca = ft.Column(visible=False)
    lista_resultado_busca = ft.Column()
    titulo_busca = ft.Text("Resultado da Pesquisa", weight="bold", size=18, color="blue")
    linha_sugestoes = ft.Row(wrap=True, spacing=5) 

    # --- POP-UP MANUAL (OVERLAY) ---
    conteudo_alerta = ft.Column(spacing=10)
    
    fundo_escuro = ft.Container(
        bgcolor="#99000000",
        expand=True,
        alignment=ft.Alignment(0, 0), 
        visible=False,
        on_click=lambda e: fechar_alerta_manual(None)
    )

    def fechar_alerta_manual(e):
        fundo_escuro.visible = False
        page.update()

    janela_alerta = ft.Container(
        bgcolor="white",
        padding=20,
        border_radius=15,
        width=300,
        content=ft.Column([
            ft.Row([
                ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color="red", size=40),
                ft.Text("Atenção!", color="red", size=20, weight="bold")
            ], alignment="center"),
            ft.Divider(),
            conteudo_alerta,
            ft.Divider(),
            ft.ElevatedButton("Entendido", bgcolor="red", color="white", on_click=fechar_alerta_manual, width=260)
        ], horizontal_alignment="center", tight=True)
    )
    
    fundo_escuro.content = janela_alerta

    def verificar_urgencia():
        urgentes = db.buscar_alertas_reais()
        if urgentes:
            conteudo_alerta.controls.clear()
            qtd = len(urgentes)
            
            conteudo_alerta.controls.append(
                ft.Text(f"Você tem {qtd} tarefa(s) vencendo hoje, amanhã ou atrasadas!", text_align="center")
            )
            
            for t in urgentes[:4]: 
                conteudo_alerta.controls.append(
                    ft.Container(
                        padding=5, 
                        bgcolor="#FFEBEE", 
                        border_radius=5,
                        content=ft.Text(f"• {t[1]} ({t[4]})", color="black", weight="bold")
                    )
                )
            
            if qtd > 4:
                conteudo_alerta.controls.append(ft.Text(f"... e mais {qtd-4}.", italic=True))

            fundo_escuro.visible = True
            page.update()

    # --- CALENDÁRIO ---
    def data_mudou(e):
        if date_picker.value:
            data_formatada = date_picker.value.strftime("%d/%m/%Y")
            data_selecionada_temp[0] = data_formatada
            btn_calendario.text = data_formatada
            btn_calendario.bgcolor = "#E3F2FD"
            btn_calendario.icon = ft.Icons.CHECK_CIRCLE
            page.update()

    date_picker = ft.DatePicker(on_change=data_mudou, cancel_text="Cancelar", confirm_text="OK", help_text="Selecione a data limite")
    page.overlay.append(date_picker)
    def abrir_calendario(e):
        date_picker.open = True
        page.update()

    # --- GRÁFICOS & RELATÓRIOS ---
    def gerar_relatorio():
        area_estatisticas.controls.clear()
        todas = db.listar_todas()
        placar = {}
        for t in todas:
            resp = t[3]
            status = t[2]
            if resp not in placar: placar[resp] = {"total": 0, "concluidas": 0}
            placar[resp]["total"] += 1
            if status == "concluida": placar[resp]["concluidas"] += 1
        area_estatisticas.controls.append(ft.Text("Resumo Geral:", size=20, weight="bold", color="black"))
        if not placar: area_estatisticas.controls.append(ft.Text("Nenhuma tarefa criada.", color="grey"))
        for nome, dados in placar.items():
            area_estatisticas.controls.append(ft.Container(padding=10, bgcolor="#F0F0F0", border_radius=10, margin=ft.margin.only(bottom=5), content=ft.Row([ft.Text(f"👤 {nome}", weight="bold", size=16, color="black"), ft.Text(f"Total: {dados['total']} | ✅ {dados['concluidas']}", color="grey")], alignment="spaceBetween")))
        page.update()

    def gerar_graficos():
        area_graficos.controls.clear()
        if not hasattr(ft, 'BarChartGroup'):
            area_graficos.controls.append(ft.Container(padding=20, bgcolor="#FFEBEE", border_radius=10, content=ft.Column([ft.Text("⚠️ Aviso", weight="bold", color="red"), ft.Text("Versão PC antiga. No celular funcionará!")])))
            page.update()
            return
        todas = db.listar_todas()
        if not todas:
            area_graficos.controls.append(ft.Text("Sem dados.", italic=True))
            page.update()
            return
        
        dados_pessoa = {}
        for t in todas:
            status, resp = t[2], t[3]
            if resp not in dados_pessoa: dados_pessoa[resp] = {"pend": 0, "conc": 0}
            if status == "pendente": dados_pessoa[resp]["pend"] += 1
            else: dados_pessoa[resp]["conc"] += 1
        grupos, eixo_x, i, max_y = [], [], 0, 0
        for nome, qtds in dados_pessoa.items():
            if (qtds["pend"]+qtds["conc"]) > max_y: max_y = qtds["pend"]+qtds["conc"]
            grupos.append(ft.BarChartGroup(x=i, bar_rods=[ft.BarChartRod(from_y=0, to_y=qtds["pend"], width=15, color="red"), ft.BarChartRod(from_y=0, to_y=qtds["conc"], width=15, color="green")]))
            eixo_x.append(ft.ChartAxisLabel(value=i, label=ft.Text(nome[:4], size=10)))
            i+=1
        grafico = ft.BarChart(bar_groups=grupos, bottom_axis=ft.ChartAxis(labels=eixo_x), left_axis=ft.ChartAxis(labels_size=40), border=ft.border.all(1, "grey"), height=200, max_y=max_y + 2)
        area_graficos.controls.append(ft.Text("Tarefas por Pessoa", size=16, weight="bold", color="blue"))
        area_graficos.controls.append(grafico)
        page.update()

    # --- NAVEGAÇÃO ---
    def navegar(e):
        if isinstance(e, str): tela = e
        else: tela = e.control.data 
        lista_pendentes.visible = False
        lista_concluidas.visible = False
        area_estatisticas.visible = False
        area_graficos.visible = False 
        btn_pendentes.bgcolor = "white"
        btn_concluidas.bgcolor = "white"
        btn_stats.bgcolor = "white"
        btn_graficos.bgcolor = "white"
        if tela == "pendente":
            lista_pendentes.visible = True
            btn_pendentes.bgcolor = "#BBDEFB"
        elif tela == "concluida":
            lista_concluidas.visible = True
            btn_concluidas.bgcolor = "#C8E6C9"
        elif tela == "stats":
            gerar_relatorio() 
            area_estatisticas.visible = True
            btn_stats.bgcolor = "#FFECB3"
        elif tela == "graficos":
            gerar_graficos()
            area_graficos.visible = True
            btn_graficos.bgcolor = "#E1BEE7"
        page.update()

    # --- LÓGICA PRINCIPAL ---
    def clicar_sugestao(nome_clicado):
        if campo_tarefa.value and campo_tarefa.value.strip() != "":
            campo_responsavel.value = nome_clicado
            coluna_abas.visible = True
            coluna_busca.visible = False
        else:
            campo_busca.value = nome_clicado
            campo_responsavel.value = nome_clicado
            executar_busca(None) 
        page.update()

    def carregar_sugestoes():
        linha_sugestoes.controls.clear()
        nomes = db.listar_nomes_usados()
        for nome in nomes:
            if nome.strip():
                linha_sugestoes.controls.append(ft.ElevatedButton(nome, height=30, bgcolor="#E3F2FD", color="#1565C0", on_click=lambda e, n=nome: clicar_sugestao(n)))
        page.update()

    def criar_card(dados, feito):
        id_t, titulo, status, resp, data_limite_str, criacao, conclusao, recorrencia = dados
        cor_fundo, texto_extra, cor_texto_prazo, cor_destaque = "#F5F5F5", "", "grey", "grey"
        try:
            dt_criacao = datetime.strptime(criacao, "%d/%m/%Y %H:%M")
            texto_info = f"👤 {resp} | Criado: {dt_criacao.strftime('%d/%m/%Y')}"
            if recorrencia and recorrencia != "Não repete": texto_info += f" | 🔄 {recorrencia}"
            if data_limite_str:
                texto_info += f" | 🎯 {data_limite_str}"
                dt_limite = datetime.strptime(data_limite_str, "%d/%m/%Y").replace(hour=23, minute=59)
                hoje = datetime.now()
                if feito and conclusao:
                    dt_conclusao = datetime.strptime(conclusao, "%d/%m/%Y %H:%M")
                    texto_info += f" | ✅ Em: {dt_conclusao.strftime('%d/%m/%Y')}"
                    if dt_conclusao > dt_limite:
                        texto_extra = f"⚠️ Atrasou {(dt_conclusao.date() - dt_limite.date()).days} dias"
                        cor_destaque = "red"
                    else: texto_extra, cor_destaque = "👏 Em dia", "green"
                elif not feito and hoje > dt_limite:
                    cor_fundo, cor_texto_prazo, cor_destaque = "#FFCDD2", "red", "red"
                    texto_extra = f"⚠️ { (hoje.date() - dt_limite.date()).days } dias de atraso"
        except: texto_info = f"👤 {resp}"

        painel_card = ft.Container(padding=10, bgcolor=cor_fundo, border_radius=8, margin=ft.margin.only(bottom=10))
        def check_changed(e):
            db.atualizar_status(id_t, "concluida" if e.control.value else "pendente")
            if campo_busca.value: executar_busca(None)
            else: carregar_listas_normais()
        def cancelar_exclusao(e):
            painel_card.content = layout_normal
            painel_card.bgcolor = cor_fundo
            page.update()
        def confirmar_exclusao(e):
            db.excluir(id_t)
            if campo_busca.value: executar_busca(None)
            else: carregar_listas_normais()
        
        layout_confirmacao = ft.Column([ft.Text("Apagar tarefa?", color="red", weight="bold", size=12), ft.Row([ft.ElevatedButton("Não", on_click=cancelar_exclusao, height=30), ft.ElevatedButton("Sim", on_click=confirmar_exclusao, bgcolor="red", color="white", height=30)], alignment="end")])
        layout_normal = ft.Column([ft.Row([ft.Checkbox(label=titulo, value=feito, on_change=check_changed), ft.TextButton("X", on_click=lambda e: setattr(painel_card, 'content', layout_confirmacao) or setattr(painel_card, 'bgcolor', '#FFEBEE') or page.update(), style=ft.ButtonStyle(color="red"))], alignment="spaceBetween"), ft.Row([ft.Text(texto_info, size=11, color=cor_texto_prazo), ft.Text(texto_extra, size=11, weight="bold", color=cor_destaque)], alignment="spaceBetween")])
        painel_card.content = layout_normal
        return painel_card

    def carregar_listas_normais():
        coluna_abas.visible, coluna_busca.visible = True, False
        lista_pendentes.controls.clear()
        lista_concluidas.controls.clear()
        for t in db.listar_por_status("pendente"): lista_pendentes.controls.append(criar_card(t, False))
        for t in db.listar_por_status("concluida"): lista_concluidas.controls.append(criar_card(t, True))
        page.update()

    def executar_busca(e):
        termo = campo_busca.value
        if not termo: return carregar_listas_normais()
        coluna_abas.visible, coluna_busca.visible = False, True
        lista_resultado_busca.controls.clear()
        resultados = db.buscar_tudo(termo)
        if not resultados: lista_resultado_busca.controls.append(ft.Text("Nada encontrado.", italic=True))
        else: 
            for t in resultados: lista_resultado_busca.controls.append(criar_card(t, t[2] == "concluida"))
        page.update()

    def adicionar_click(e):
        if not campo_tarefa.value: return
        db.adicionar(campo_tarefa.value, campo_responsavel.value if campo_responsavel.value else "Geral", data_selecionada_temp[0] if data_selecionada_temp[0] else "", dropdown_recorrencia.value)
        campo_tarefa.value, campo_responsavel.value = "", ""
        data_selecionada_temp[0] = None
        btn_calendario.text, btn_calendario.icon, btn_calendario.bgcolor = "Prazo", ft.Icons.CALENDAR_MONTH_OUTLINED, "white"
        dropdown_recorrencia.value = "Não repete"
        if campo_busca.value: executar_busca(None)
        else: carregar_listas_normais()
        carregar_sugestoes()

    # --- UI ---
    campo_busca = ft.TextField(hint_text="🔍 Buscar...", expand=True, on_change=executar_busca, height=40)
    btn_limpar_busca = ft.IconButton(icon=ft.Icons.CLOSE, on_click=lambda e: setattr(campo_busca, 'value', "") or carregar_listas_normais(), tooltip="Limpar")
    campo_tarefa = ft.TextField(label="O que fazer?", border_color="blue", expand=True)
    campo_responsavel = ft.TextField(label="Quem?", hint_text="Nome", expand=True, height=50)
    dropdown_recorrencia = ft.Dropdown(options=[ft.dropdown.Option(x) for x in ["Não repete", "Diária", "Semanal", "Mensal", "Anual"]], value="Não repete", label="Repetição", height=48, content_padding=10, expand=True)
    btn_calendario = ft.ElevatedButton("Prazo", icon=ft.Icons.CALENDAR_MONTH_OUTLINED, on_click=abrir_calendario, height=48, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)), bgcolor="white", color="#1565C0", expand=True)
    btn_add = ft.ElevatedButton("+", on_click=adicionar_click, bgcolor="#1565C0", color="white", width=60, height=48, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)))
    
    linha_botoes = ft.Row(controls=[dropdown_recorrencia, btn_calendario, btn_add], spacing=10)
    painel_criacao = ft.Container(padding=15, bgcolor="#F9F9F9", border_radius=15, border=ft.border.all(1, "#E0E0E0"), content=ft.Column([ft.Text("Nova Tarefa", weight="bold", size=16, color="#1565C0"), campo_tarefa, campo_responsavel, linha_botoes, ft.Text("Filtrar por nome:", size=12, color="grey"), linha_sugestoes]))
    
    btn_pendentes = ft.ElevatedButton("A Fazer", data="pendente", on_click=navegar, bgcolor="#BBDEFB", expand=True)
    btn_concluidas = ft.ElevatedButton("Feitas", data="concluida", on_click=navegar, bgcolor="white", expand=True)
    btn_stats = ft.ElevatedButton("Resumo", data="stats", on_click=navegar, bgcolor="white", expand=True)
    btn_graficos = ft.ElevatedButton("Gráficos", data="graficos", on_click=navegar, bgcolor="white", expand=True)

    coluna_abas.controls = [ft.Row([btn_pendentes, btn_concluidas, btn_stats, btn_graficos]), ft.Column([lista_pendentes, lista_concluidas, area_estatisticas, area_graficos], expand=True)]
    coluna_busca.controls = [titulo_busca, ft.Divider(), lista_resultado_busca]

    # --- MONTAGEM DO LAYOUT PRINCIPAL (STACK) ---
    
    # Conteúdo principal (Camada de Baixo)
    conteudo_principal = ft.Column([
        ft.Row([ft.Text("Tarefas do dia a dia", size=24, weight="bold", color="#1565C0"), ft.Container(expand=True), ft.Image(src="https://flagcdn.com/w40/cu.png", width=30), ft.Container(width=5), ft.Image(src="https://flagcdn.com/w40/br.png", width=30)]),
        ft.Row([campo_busca, btn_limpar_busca]),
        ft.Divider(height=10, color="transparent"), painel_criacao, ft.Divider(height=10, color="transparent"), coluna_abas, coluna_busca,
        ft.Divider(), 
        ft.Container(
            content=ft.Text("Desenvolvido por Ricardo Perez", size=12, color="grey", italic=True), 
            alignment=ft.Alignment(0, 0), # CORREÇÃO AQUI
            padding=10
        )
    ], scroll="auto", expand=True)

    # Container Pai (para dar o padding da tela sem usar na Column)
    layout_principal = ft.Container(
        content=conteudo_principal,
        padding=15, # Padding movido para cá
        expand=True
    )

    # --- ADICIONA A STACK (CAMADAS) ---
    page.add(
        ft.Stack(
            [
                layout_principal, # Embaixo
                fundo_escuro      # Em cima (O Pop-up manual)
            ],
            expand=True
        )
    )
    
    carregar_listas_normais()
    carregar_sugestoes()
    verificar_urgencia()

ft.app(target=main)