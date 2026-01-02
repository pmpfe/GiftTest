"""
Ecrã de seleção de categorias e configuração do teste.
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                               QCheckBox, QSpinBox, QScrollArea, QGroupBox, QLineEdit,
                               QTableWidget, QTableWidgetItem, QHeaderView, QFrame)
from PySide6.QtCore import Qt
import random
import re
from .history_screen import HistoryScreen
from .i18n import tr


class SelectionScreen:
    """Gere o ecrã de seleção de categorias."""

    def __init__(self, app):
        self.app = app

    def show(self):
        """Mostra tela de seleção de categorias e número de perguntas."""
        self.app.clear_window()

        # Widget central com scroll
        central = QWidget()
        self.app.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Área scrollável
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # Título centrado
        title = QLabel(tr("Sistema de Testes GIFT"))
        title_font = title.font()
        title_font.setPointSize(title_font.pointSize() + 6)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(title)
        content_layout.addSpacing(10)

        # Grupo de Configurações
        self._create_config_group(content_layout)

        # Grupo de Histórico
        self._create_history_group(content_layout)

        # Instruções (Removido a pedido)
        # instructions = QLabel("Selecione as categorias e o número de perguntas por categoria:")
        # content_layout.addWidget(instructions)
        content_layout.addSpacing(15)

        # Categorias
        self._create_categories_section(content_layout)

        # Botões
        self._create_buttons(content_layout)

        content_layout.addStretch()
        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def _create_config_group(self, layout):
        """Cria grupo de Configurações com ficheiro e modelo atual."""
        grp = QGroupBox(tr("Configurações"))
        grp_layout = QVBoxLayout()
        grp_layout.setSpacing(2)

        current_file = self.app.current_gift_file or tr("(nenhum ficheiro selecionado)")
        provider = self.app.preferences.get_llm_provider()
        model = self.app.preferences.get_llm_model(provider) or tr("(modelo não definido)")

        # Ficheiro
        grp_layout.addWidget(QLabel(tr("Ficheiro:") + f" {current_file}"))

        # Modelo
        grp_layout.addWidget(QLabel(tr("Modelo:") + f" {provider} / {model}"))

        # Botão Configurar
        config_btn = QPushButton(tr("Configurar"))
        config_btn.clicked.connect(self.app.show_settings)
        grp_layout.addWidget(config_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        grp.setLayout(grp_layout)
        layout.addWidget(grp)
        layout.addSpacing(10)

    def _create_history_group(self, layout):
        """Cria grupo de Histórico com estatísticas e botão Ver Histórico."""
        grp = QGroupBox(tr("Histórico"))
        grp_layout = QVBoxLayout()
        grp_layout.setSpacing(2)

        # Estatísticas do ficheiro atual
        stats = self.app.logger.get_statistics(self.app.current_gift_file)
        if stats and stats.get('total_tests', 0) > 0:
            stats_text = tr("Testes realizados:") + f" {stats['total_tests']} | " + tr("Média de acertos:") + f" {stats['average_score']}%"
            stats_label = QLabel(stats_text)
            stats_label.setStyleSheet("font-style: italic;")
            grp_layout.addWidget(stats_label)
        else:
            grp_layout.addWidget(QLabel(tr("Nenhum teste realizado ainda.")))

        # Botão Ver Histórico
        history_btn = QPushButton(tr("Ver Histórico"))
        history_btn.clicked.connect(self._show_history)
        grp_layout.addWidget(history_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        grp.setLayout(grp_layout)
        layout.addWidget(grp)
        layout.addSpacing(10)

    def _change_language_from_main(self, language_code: str):
        """Muda a linguagem com confirmação e reinicia a aplicação."""
        from .i18n import get_default_language
        from PySide6.QtWidgets import QMessageBox
        from PySide6.QtCore import QProcess
        import sys
        
        current_lang = self.app.preferences.get_language()
        
        # Se a língua já está configurada, não faz nada
        if current_lang == language_code:
            return
        
        # Mensagens de confirmação
        language_names = {
            'pt': 'Português',
            'en': 'English'
        }
        
        # Obter os textos na linguagem atual
        current_language_actual = current_lang
        if current_language_actual == 'system':
            current_language_actual = get_default_language()
        
        # Determinar o texto de confirmação na língua atual
        if current_language_actual == 'pt':
            question_text = f"Deseja alterar a língua para {language_names.get(language_code, language_code)} e reiniciar a aplicação?"
        else:
            question_text = f"Do you want to change the language to {language_names.get(language_code, language_code)} and restart the application?"
        
        reply = QMessageBox.question(
            self.app,
            "Language" if current_language_actual == 'en' else "Idioma",
            question_text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Guardar a nova linguagem
            self.app.preferences.set_language(language_code)
            
            # Reiniciar a aplicação usando QProcess
            QProcess.startDetached(sys.executable, sys.argv)
            
            # Fechar a aplicação atual
            from PySide6.QtWidgets import QApplication
            QApplication.quit()

    def _show_history(self):
        """Abre a tela de histórico."""
        history_screen = HistoryScreen(self.app)
        history_screen.show()

    def _create_categories_section(self, layout):
        """Cria secção de seleção de categorias (desdobrável)."""
        # Botão de toggle
        toggle_btn = QPushButton(tr("Seleção de categorias (Clique para expandir/colapsar)"))
        toggle_btn.setCheckable(True)
        toggle_btn.setChecked(False)  # Inicialmente fechado
        toggle_btn.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 8px;
                font-weight: bold;
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 4px;
            }
            QPushButton:checked {
                background-color: #e0e0e0;
            }
        """)
        layout.addWidget(toggle_btn)

        # Container para o conteúdo (tabela)
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 10, 0, 0)
        content_widget.setVisible(False) # Inicialmente invisível

        # Conecta o botão à visibilidade
        toggle_btn.toggled.connect(content_widget.setVisible)

        # Limpa variáveis
        self.app.category_vars = {}
        self.app.category_spinboxes = {}

        # Verifica se há perguntas carregadas
        has_questions = self.app.parser is not None

        if has_questions:
            self._create_category_table(content_layout)
        else:
            self._show_no_file_message(content_layout)

        layout.addWidget(content_widget)
        layout.addSpacing(15)

    def _create_category_table(self, layout):
        """Cria tabela de categorias."""
        categories = self.app.parser.get_categories()

        table = QTableWidget()
        table.setRowCount(len(categories))
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Sel.", "Categoria", "Qtd", "Total"])

        # Ajusta cabeçalhos
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        table.verticalHeader().setVisible(False)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.setAlternatingRowColors(True)

        # Altura mínima para ver algumas linhas
        table.setMinimumHeight(300)

        for i, category in enumerate(categories):
            questions_count = len(self.app.parser.get_questions_by_category(category))

            # Coluna 0: Checkbox
            chk_widget = QWidget()
            chk_layout = QHBoxLayout(chk_widget)
            chk_layout.setContentsMargins(0, 0, 0, 0)
            chk_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            checkbox = QCheckBox()
            checkbox.setChecked(False)
            chk_layout.addWidget(checkbox)
            table.setCellWidget(i, 0, chk_widget)
            self.app.category_vars[category] = checkbox

            # Coluna 1: Nome da Categoria
            item_name = QTableWidgetItem(category)
            item_name.setFlags(item_name.flags() ^ Qt.ItemFlag.ItemIsEditable)
            table.setItem(i, 1, item_name)

            # Coluna 2: Spinbox
            spinbox = QSpinBox()
            spinbox.setMinimum(1)
            spinbox.setMaximum(questions_count)
            spinbox.setValue(min(10, questions_count))
            # Estilo para ficar mais compacto
            spinbox.setFixedWidth(70)
            table.setCellWidget(i, 2, spinbox)
            self.app.category_spinboxes[category] = spinbox

            # Coluna 3: Total
            item_total = QTableWidgetItem(str(questions_count))
            item_total.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_total.setFlags(item_total.flags() ^ Qt.ItemFlag.ItemIsEditable)
            table.setItem(i, 3, item_total)

        layout.addWidget(table)

    def _show_no_file_message(self, layout):
        """Mostra mensagem quando não há ficheiro carregado."""
        label = QLabel(tr("Nenhum ficheiro GIFT carregado.") + "\n" + tr("Abra Configurações para escolher um ficheiro."))
        label.setStyleSheet("color: gray; font-style: italic;")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

    def _create_buttons(self, layout):
        """Cria botões de ação."""
        has_questions = self.app.parser is not None

        # Linha 0: Botões de seleção e teste (agora incluindo teste rápido)
        test_buttons = QWidget()
        test_layout = QHBoxLayout(test_buttons)
        test_layout.setContentsMargins(0, 0, 0, 0)

        # Adiciona stretches para centralizar
        test_layout.addStretch()

        select_all_btn = QPushButton(tr("Selecionar Todas"))
        select_all_btn.clicked.connect(self.app.select_all_categories)
        select_all_btn.setEnabled(has_questions)
        select_all_btn.setToolTip(tr("Marca todas as categorias da lista."))
        test_layout.addWidget(select_all_btn)

        deselect_all_btn = QPushButton(tr("Desmarcar Todas"))
        deselect_all_btn.clicked.connect(self.app.deselect_all_categories)
        deselect_all_btn.setEnabled(has_questions)
        deselect_all_btn.setToolTip(tr("Desmarca todas as categorias da lista."))
        test_layout.addWidget(deselect_all_btn)

        start_test_btn = QPushButton(tr("Iniciar Teste Personalizado"))
        start_test_btn.clicked.connect(self.app.start_test)
        start_test_btn.setEnabled(has_questions)
        start_test_btn.setStyleSheet("font-weight: bold; padding: 5px;")
        start_test_btn.setToolTip(tr("Inicia um teste apenas com as categorias e quantidades selecionadas acima."))
        test_layout.addWidget(start_test_btn)

        # Botão Teste Rápido
        quick_test_count = self.app.preferences.get_quick_test_questions()
        quick_test_btn = QPushButton(tr("Teste Rápido") + f" ({quick_test_count} " + tr("perguntas") + ")")
        quick_test_btn.clicked.connect(self.app.start_quick_test)
        quick_test_btn.setEnabled(has_questions)
        quick_test_btn.setStyleSheet("""
            QPushButton {
                font-weight: bold;
                font-size: 12px;
                padding: 6px;
                background-color: #4CAF50;
                color: white;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        quick_test_btn.setToolTip(
            tr("Inicia imediatamente um teste com") + f" {quick_test_count} " + tr("perguntas aleatórias de todas as categorias.")
        )
        test_layout.addWidget(quick_test_btn)

        # Adiciona stretches para centralizar
        test_layout.addStretch()
        layout.addWidget(test_buttons)
        layout.addSpacing(10)

        # Linha 1: Explicar pergunta
        self._create_extra_buttons(layout, has_questions)

        # Linha 2: Botões Sobre e Sair centrados
        bottom_buttons = QWidget()
        bottom_layout = QHBoxLayout(bottom_buttons)
        bottom_layout.setContentsMargins(0, 0, 0, 0)

        bottom_layout.addStretch()

        # Botões de bandeira para mudança rápida de idioma
        flag_pt_btn = QPushButton("\U0001F1F5\U0001F1F9")
        flag_pt_btn.setMaximumWidth(50)
        flag_pt_btn.setMaximumHeight(40)
        flag_pt_font = flag_pt_btn.font()
        flag_pt_font.setPointSize(18)
        flag_pt_btn.setFont(flag_pt_font)
        flag_pt_btn.setToolTip("Português")
        flag_pt_btn.clicked.connect(lambda: self._change_language_from_main('pt'))
        bottom_layout.addWidget(flag_pt_btn)
        
        flag_en_btn = QPushButton("\U0001F1EC\U0001F1E7")
        flag_en_btn.setMaximumWidth(50)
        flag_en_btn.setMaximumHeight(40)
        flag_en_font = flag_en_btn.font()
        flag_en_font.setPointSize(18)
        flag_en_btn.setFont(flag_en_font)
        flag_en_btn.setToolTip("English")
        flag_en_btn.clicked.connect(lambda: self._change_language_from_main('en'))
        bottom_layout.addWidget(flag_en_btn)

        about_btn = QPushButton(tr("Sobre o Programa"))
        about_btn.clicked.connect(self.app.show_about)
        about_btn.setToolTip(tr("Mostra informações sobre o autor, funcionalidades e instruções de uso."))
        bottom_layout.addWidget(about_btn)

        exit_btn = QPushButton(tr("Sair"))
        exit_btn.clicked.connect(self.app.close)
        exit_btn.setToolTip(tr("Fecha a aplicação."))
        bottom_layout.addWidget(exit_btn)

        bottom_layout.addStretch()
        layout.addWidget(bottom_buttons)

    def _create_extra_buttons(self, layout, has_questions):
        """Cria botões de explicar e reiniciar histórico."""
        extra_buttons = QWidget()
        extra_layout = QHBoxLayout(extra_buttons)
        extra_layout.setContentsMargins(0, 0, 0, 0)

        # Adiciona stretch para centralizar
        extra_layout.addStretch()

        # Botão Explorar (Novo)
        explore_btn = QPushButton(tr("Explorar / Pesquisar Perguntas"))
        explore_btn.clicked.connect(self.app.show_question_browser)
        explore_btn.setEnabled(has_questions)
        explore_btn.setStyleSheet("font-weight: bold; color: #2196F3;")
        explore_btn.setToolTip(tr("Abre uma janela para pesquisar e explorar todas as perguntas disponíveis."))
        extra_layout.addWidget(explore_btn)

        extra_layout.addSpacing(20)
        extra_layout.addWidget(QLabel("|")),
        extra_layout.addSpacing(20)

        extra_layout.addWidget(QLabel(tr("Explicar pergunta nº:")))

        explain_entry = QLineEdit()
        if has_questions and self.app.parser.questions:
            random_q = random.choice(self.app.parser.questions)
            # Extract number only (e.g., "345" from "Questão 345")
            number_only = re.search(r'\d+', str(random_q.number))
            if number_only:
                explain_entry.setText(number_only.group())
            else:
                explain_entry.setText(str(random_q.number))
        explain_entry.setEnabled(has_questions)
        self.app.explain_question_var = explain_entry
        extra_layout.addWidget(explain_entry)

        explain_btn = QPushButton(tr("Explicar"))
        explain_btn.clicked.connect(self.app.explain_question)
        explain_btn.setEnabled(has_questions)
        explain_btn.setToolTip(tr("Gera uma explicação detalhada para a pergunta com o número indicado."))
        extra_layout.addWidget(explain_btn)

        # Adiciona stretch para centralizar
        extra_layout.addStretch()
        layout.addWidget(extra_buttons)
        layout.addSpacing(15)

    def _show_statistics(self, layout):
        """(Sem uso) Estatísticas agora aparecem dentro do grupo Configurações."""
        pass
