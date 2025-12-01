"""
Ecrã de apresentação de perguntas.
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPushButton, QRadioButton, QGroupBox, QButtonGroup, QMessageBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


class QuestionScreen:
    """Gere o ecrã de apresentação de perguntas."""
    
    def __init__(self, app):
        self.app = app
    
    def show(self):
        """Mostra a pergunta atual."""
        if self.app.current_question_index >= len(self.app.selected_questions):
            from data.results_screen import ResultsScreen
            ResultsScreen(self.app).show()
            return
        
        self.app.clear_window()
        
        question = self.app.selected_questions[self.app.current_question_index]
        
        # Widget central
        central = QWidget()
        self.app.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Progresso
        progress_text = f"Pergunta {self.app.current_question_index + 1} de {len(self.app.selected_questions)}"
        progress_label = QLabel(progress_text)
        progress_font = progress_label.font()
        progress_font.setItalic(True)
        progress_label.setFont(progress_font)
        main_layout.addWidget(progress_label)
        
        # Categoria
        if question.category:
            category_label = QLabel(f"Categoria: {question.category}")
            category_font = category_label.font()
            category_font.setItalic(True)
            category_label.setFont(category_font)
            main_layout.addWidget(category_label)
            main_layout.addSpacing(10)
        
        # Pergunta
        question_grp = QGroupBox(f"Questão {question.number}")
        question_layout = QVBoxLayout()
        
        question_label = QLabel(question.text)
        question_label.setWordWrap(True)
        question_layout.addWidget(question_label)
        
        question_grp.setLayout(question_layout)
        main_layout.addWidget(question_grp)
        main_layout.addSpacing(15)
        
        # Opções de resposta
        options_grp = QGroupBox("Opções")
        options_layout = QVBoxLayout()
        
        button_group = QButtonGroup(central)
        self.app.answer_var = -1
        
        for i, option in enumerate(question.options):
            rb = QRadioButton(option['text'])
            rb.toggled.connect(lambda checked, idx=i: self._on_radio_toggled(checked, idx))
            button_group.addButton(rb, i)
            options_layout.addWidget(rb)
        
        options_grp.setLayout(options_layout)
        main_layout.addWidget(options_grp)
        main_layout.addSpacing(15)
        
        # Botões
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        button_layout.setContentsMargins(0, 0, 0, 0)
        
        if self.app.current_question_index > 0:
            prev_btn = QPushButton("← Anterior")
            prev_btn.clicked.connect(self.previous_question)
            button_layout.addWidget(prev_btn)
        
        next_text = "Próxima →" if self.app.current_question_index < len(self.app.selected_questions) - 1 else "Finalizar"
        next_btn = QPushButton(next_text)
        next_btn.clicked.connect(self.next_question)
        button_layout.addWidget(next_btn)
        
        # Botão Terminar Agora (Novo)
        finish_btn = QPushButton("Terminar Agora")
        finish_btn.clicked.connect(self.finish_early)
        finish_btn.setStyleSheet("color: #d32f2f;")  # Red text to indicate destructive/exit action
        button_layout.addSpacing(20)
        button_layout.addWidget(finish_btn)
        
        button_layout.addStretch()
        main_layout.addWidget(button_widget)
        main_layout.addStretch()
    
    def _on_radio_toggled(self, checked, idx):
        """Callback quando radio button é alterado."""
        if checked:
            self.app.answer_var = idx
            
    def finish_early(self):
        """Termina o teste prematuramente."""
        response = QMessageBox.question(
            self.app,
            "Terminar Teste", 
            "Tem a certeza que deseja terminar o teste agora?\n\nApenas as perguntas visualizadas serão contabilizadas.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if response == QMessageBox.StandardButton.Yes:
            # Truncate selected questions to current index + 1 (if answered) or current index
            # If current question has an answer selected, count it.
            if self.app.answer_var != -1:
                question = self.app.selected_questions[self.app.current_question_index]
                self.app.user_answers[question.number] = self.app.answer_var
                # Include current question in results
                self.app.selected_questions = self.app.selected_questions[:self.app.current_question_index + 1]
            else:
                # Exclude current question
                self.app.selected_questions = self.app.selected_questions[:self.app.current_question_index]
            
            # Show results
            from data.results_screen import ResultsScreen
            ResultsScreen(self.app).show()
    
    def next_question(self):
        """Vai para a próxima pergunta."""
        # Guarda resposta
        answer = self.app.answer_var
        
        if answer == -1:
            response = QMessageBox.question(
                self.app,
                "Aviso", 
                "Não selecionou nenhuma resposta. Continuar mesmo assim?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if response != QMessageBox.StandardButton.Yes:
                return
        
        question = self.app.selected_questions[self.app.current_question_index]
        self.app.user_answers[question.number] = answer
        
        self.app.current_question_index += 1
        self.show()
    
    def previous_question(self):
        """Volta para a pergunta anterior."""
        self.app.current_question_index -= 1
        
        # Restaura resposta anterior se existir
        question = self.app.selected_questions[self.app.current_question_index]
        if question.number in self.app.user_answers:
            self.app.answer_var = self.app.user_answers[question.number]
        
        self.show()
