"""
Ecrã de resultados do teste.
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPushButton, QTextEdit, QGroupBox)
from PyQt6.QtGui import QFont, QColor


class ResultsScreen:
    """Gere o ecrã de resultados."""
    
    def __init__(self, app):
        self.app = app
    
    def show(self):
        """Mostra os resultados do teste."""
        self.app.clear_window()
        
        # Calcula resultados
        correct, wrong, wrong_details = self._calculate_results()
        
        total = len(self.app.selected_questions)
        percentage = (correct / total * 100) if total > 0 else 0
        
        # Regista no log
        self._log_results(correct, wrong, wrong_details)
        
        # Widget central
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
        self._show_statistics(main_layout, total, correct, wrong, percentage)
        
        # Perguntas erradas
        if wrong_details:
            self._show_wrong_answers(main_layout, wrong_details)
        
        # Botões
        self._create_buttons(main_layout)
    
    def _calculate_results(self):
        """Calcula resultados do teste."""
        correct = 0
        wrong = 0
        wrong_details = []
        
        for question in self.app.selected_questions:
            user_answer = self.app.user_answers.get(question.number, -1)
            correct_answer = question.get_correct_answer()
            
            if user_answer == correct_answer:
                correct += 1
            else:
                wrong += 1
                wrong_details.append({
                    'question_number': question.number,
                    'question_text': question.text,
                    'user_answer': question.options[user_answer]['text'] if user_answer >= 0 else 'Sem resposta',
                    'correct_answer': question.options[correct_answer]['text'] if correct_answer is not None else 'N/A',
                    'category': question.category
                })
        
        return correct, wrong, wrong_details
    
    def _log_results(self, correct, wrong, wrong_details):
        """Regista resultados no histórico."""
        # Verifica se o utilizador respondeu pelo menos uma pergunta
        answered_questions = sum(1 for answer in self.app.user_answers.values() if answer >= 0)
        
        if answered_questions == 0:
            # Não regista testes onde o utilizador não respondeu nenhuma pergunta
            return
        
        categories = list(set(q.category for q in self.app.selected_questions if q.category))
        wrong_ids = [d['question_number'] for d in wrong_details]
        total = len(self.app.selected_questions)
        
        self.app.logger.log_test(
            self.app.current_gift_file or "unknown",
            categories, 
            total, 
            correct, 
            wrong, 
            wrong_ids, 
            wrong_details
        )
    
    def _show_statistics(self, layout, total, correct, wrong, percentage):
        """Mostra estatísticas do teste."""
        stats_grp = QGroupBox("Estatísticas")
        stats_layout = QVBoxLayout()
        
        stats_layout.addWidget(QLabel(f"Total de perguntas: {total}"))
        
        correct_label = QLabel(f"Respostas corretas: {correct}")
        correct_label.setStyleSheet("color: green;")
        stats_layout.addWidget(correct_label)
        
        wrong_label = QLabel(f"Respostas erradas: {wrong}")
        wrong_label.setStyleSheet("color: red;")
        stats_layout.addWidget(wrong_label)
        
        percent_label = QLabel(f"Percentagem: {percentage:.1f}%")
        percent_font = percent_label.font()
        percent_font.setBold(True)
        percent_label.setFont(percent_font)
        stats_layout.addWidget(percent_label)
        
        stats_grp.setLayout(stats_layout)
        layout.addWidget(stats_grp)
        layout.addSpacing(15)
    
    def _show_wrong_answers(self, layout, wrong_details):
        """Mostra lista de perguntas erradas."""
        errors_grp = QGroupBox("Perguntas Erradas")
        errors_layout = QVBoxLayout()
        
        text_widget = QTextEdit()
        text_widget.setReadOnly(True)
        
        for i, detail in enumerate(wrong_details, 1):
            # Botão para explicar antes do bloco
            explain_btn = QPushButton(f"Ver explicação da pergunta {detail['question_number']}")
            explain_btn.clicked.connect(lambda checked, qnum=detail['question_number']: self._explain_question(qnum))
            errors_layout.addWidget(explain_btn)
            
            # Número e categoria
            text_widget.setFontWeight(QFont.Weight.Bold)
            text_widget.insertPlainText(f"{i}. Questão {detail['question_number']}")
            text_widget.setFontWeight(QFont.Weight.Normal)
            text_widget.insertPlainText(f" ({detail['category']})\n")
            
            # Pergunta
            text_widget.insertPlainText(f"   Pergunta: {detail['question_text']}\n")
            
            # Resposta do utilizador (vermelho)
            text_widget.setTextColor(QColor("red"))
            text_widget.insertPlainText(f"   Sua resposta: {detail['user_answer']}\n")
            text_widget.setTextColor(QColor("black"))
            
            # Resposta correta (verde)
            text_widget.setTextColor(QColor("green"))
            text_widget.insertPlainText(f"   Resposta correta: {detail['correct_answer']}\n\n")
            text_widget.setTextColor(QColor("black"))
        
        errors_layout.addWidget(text_widget)
        errors_grp.setLayout(errors_layout)
        layout.addWidget(errors_grp)
        layout.addSpacing(15)
    
    def _explain_question(self, question_number):
        """Explica uma pergunta específica."""
        # Encontra a pergunta pelo número
        if self.app.parser:
            question = next((q for q in self.app.parser.questions if str(q.number) == str(question_number)), None)
            if question:
                self.app.explain_question(question)
            else:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self.app, "Aviso", f"Pergunta {question_number} não encontrada.")
        else:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self.app, "Aviso", "Nenhum ficheiro carregado.")
    
    def _create_buttons(self, layout):
        """Cria botões de ação."""
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        button_layout.setContentsMargins(0, 0, 0, 0)
        
        back_btn = QPushButton("Voltar ao início")
        back_btn.clicked.connect(self.app.show_selection_screen)
        button_layout.addWidget(back_btn)
        
        button_layout.addStretch()
        layout.addWidget(button_widget)
