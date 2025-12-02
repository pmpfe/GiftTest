"""
Ecrã de histórico de testes.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGroupBox
)
from PyQt6.QtCore import Qt


class HistoryScreen:
    """Gere o ecrã de histórico de testes."""

    def __init__(self, app):
        self.app = app

    def show(self):
        """Mostra o histórico de testes."""
        self.app.clear_window()

        # Widget central
        central = QWidget()
        self.app.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Título
        title = QLabel("Histórico de Testes")
        title_font = title.font()
        title_font.setPointSize(title_font.pointSize() + 6)
        title_font.setBold(True)
        title.setFont(title_font)
        main_layout.addWidget(title)
        main_layout.addSpacing(20)

        # Lista de testes
        self._show_test_list(main_layout)

        # Botões
        self._create_buttons(main_layout)

        main_layout.addStretch()

    def _show_test_list(self, layout):
        """Mostra lista de testes realizados."""
        grp = QGroupBox("Testes Realizados")
        grp_layout = QVBoxLayout()

        # Container para os itens da lista
        scroll_area = QWidget()
        scroll_layout = QVBoxLayout(scroll_area)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(5)

        # Carrega histórico
        history = self.app.logger.get_recent_tests(limit=50, gift_file=self.app.current_gift_file)

        if not history:
            no_tests_label = QLabel("Nenhum teste encontrado.")
            no_tests_label.setStyleSheet("color: gray; font-style: italic;")
            no_tests_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            scroll_layout.addWidget(no_tests_label)
        else:
            for test in history:
                # Cria um widget para cada teste
                test_widget = self._create_test_item(test)
                scroll_layout.addWidget(test_widget)

        scroll_layout.addStretch()
        grp_layout.addWidget(scroll_area)
        grp.setLayout(grp_layout)
        layout.addWidget(grp)
        layout.addSpacing(15)

    def _create_test_item(self, test_data):
        """Cria um widget para um item da lista de testes."""
        # Widget container
        item_widget = QWidget()
        item_layout = QHBoxLayout(item_widget)
        item_layout.setContentsMargins(10, 5, 10, 5)

        # Estilo alternado para melhor visualização
        item_widget.setStyleSheet("""
            QWidget {
                background-color: #f9f9f9;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
        """)

        # Texto do teste
        text = f"{test_data['date']} {test_data['time']} - {test_data['percentage']}% ({test_data['correct']}/{test_data['total_questions']})"
        label = QLabel(text)
        label.setStyleSheet("font-weight: bold;")
        item_layout.addWidget(label)

        item_layout.addStretch()

        # Botão "Ver resultados"
        view_btn = QPushButton("Ver resultados")
        view_btn.setFixedWidth(120)
        view_btn.clicked.connect(lambda: self._show_test_results(test_data))
        item_layout.addWidget(view_btn)

        return item_widget

    def _create_buttons(self, layout):
        """Cria botões de ação."""
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        button_layout.setContentsMargins(0, 0, 0, 0)

        button_layout.addStretch()

        back_btn = QPushButton("Voltar")
        back_btn.clicked.connect(self.app.show_selection_screen)
        button_layout.addWidget(back_btn)

        layout.addWidget(button_widget)

    def _show_test_results(self, test_data):
        """Mostra os resultados de um teste específico."""
        # Simula os dados necessários para o results_screen
        # Como não temos as perguntas originais, mostramos apenas as estatísticas e detalhes salvos

        self.app.clear_window()

        central = QWidget()
        self.app.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Título
        title = QLabel("Resultados do Teste")
        title_font = title.font()
        title_font.setPointSize(title_font.pointSize() + 6)
        title_font.setBold(True)
        title.setFont(title_font)
        main_layout.addWidget(title)
        main_layout.addSpacing(20)

        # Estatísticas
        stats_grp = QGroupBox("Estatísticas")
        stats_layout = QVBoxLayout()

        stats_layout.addWidget(QLabel(f"Data: {test_data['date']} {test_data['time']}"))
        stats_layout.addWidget(QLabel(f"Total de perguntas: {test_data['total_questions']}"))

        correct_label = QLabel(f"Respostas corretas: {test_data['correct']}")
        correct_label.setStyleSheet("color: green;")
        stats_layout.addWidget(correct_label)

        wrong_label = QLabel(f"Respostas erradas: {test_data['wrong']}")
        wrong_label.setStyleSheet("color: red;")
        stats_layout.addWidget(wrong_label)

        percent_label = QLabel(f"Percentagem: {test_data['percentage']}%")
        percent_font = percent_label.font()
        percent_font.setBold(True)
        percent_label.setFont(percent_font)
        stats_layout.addWidget(percent_label)

        stats_grp.setLayout(stats_layout)
        main_layout.addWidget(stats_grp)
        main_layout.addSpacing(15)

        # Detalhes das perguntas erradas, se disponíveis
        if 'details' in test_data and test_data['details']:
            errors_grp = QGroupBox("Perguntas Erradas")
            errors_layout = QVBoxLayout()

            for i, detail in enumerate(test_data['details'], 1):
                # Número e categoria
                detail_label = QLabel(f"{i}. Questão {detail['question_number']} ({detail['category']})")
                detail_label.setStyleSheet("font-weight: bold;")
                errors_layout.addWidget(detail_label)

                # Pergunta
                errors_layout.addWidget(QLabel(f"   Pergunta: {detail['question_text']}"))

                # Resposta do utilizador (vermelho)
                user_label = QLabel(f"   Sua resposta: {detail['user_answer']}")
                user_label.setStyleSheet("color: red;")
                errors_layout.addWidget(user_label)

                # Resposta correta (verde)
                correct_label = QLabel(f"   Resposta correta: {detail['correct_answer']}")
                correct_label.setStyleSheet("color: green;")
                errors_layout.addWidget(correct_label)

                # Botão para explicar
                explain_btn = QPushButton(f"Ver explicação da pergunta {detail['question_number']}")
                explain_btn.clicked.connect(lambda checked, qnum=detail['question_number']: self._explain_question(qnum))
                errors_layout.addWidget(explain_btn)

                errors_layout.addSpacing(10)

            errors_grp.setLayout(errors_layout)
            main_layout.addWidget(errors_grp)
            main_layout.addSpacing(15)

        # Botões
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        button_layout.setContentsMargins(0, 0, 0, 0)

        back_btn = QPushButton("Voltar ao Histórico")
        back_btn.clicked.connect(self.show)
        button_layout.addWidget(back_btn)

        button_layout.addStretch()

        home_btn = QPushButton("Voltar ao Início")
        home_btn.clicked.connect(self.app.show_selection_screen)
        button_layout.addWidget(home_btn)

        main_layout.addWidget(button_widget)

        main_layout.addStretch()

    def _explain_question(self, question_number):
        """Explica uma pergunta específica."""
        # Encontra a pergunta pelo número
        if self.app.parser:
            question = next(
            (q for q in self.app.parser.questions
             if str(q.number) == str(question_number)),
            None
        )
            if question:
                self.app.explain_question(question)
            else:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self.app, "Aviso", f"Pergunta {question_number} não encontrada no ficheiro atual.")
        else:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self.app, "Aviso", "Nenhum ficheiro carregado.")
