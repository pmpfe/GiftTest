"""Ecrã de resultados do teste."""

import html

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QGroupBox,
)
from PySide6.QtCore import QUrl
from PySide6.QtGui import QFont
from .i18n import tr


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
        title = QLabel(tr("Resultados do Teste"))
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
                    'user_answer': question.options[user_answer]['text'] if user_answer >= 0 else tr('Sem resposta'),
                    'correct_answer': question.options[correct_answer]['text'] if correct_answer is not None else tr('N/A'),
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
        stats_grp = QGroupBox(tr("Estatísticas"))
        stats_layout = QVBoxLayout()

        stats_layout.addWidget(QLabel(tr("Total de perguntas:") + f" {total}"))

        correct_label = QLabel(tr("Respostas corretas:") + f" {correct}")
        correct_label.setStyleSheet("color: green;")
        stats_layout.addWidget(correct_label)

        wrong_label = QLabel(tr("Respostas erradas:") + f" {wrong}")
        wrong_label.setStyleSheet("color: red;")
        stats_layout.addWidget(wrong_label)

        percent_label = QLabel(tr("Percentagem:") + f" {percentage:.1f}%")
        percent_font = percent_label.font()
        percent_font.setBold(True)
        percent_label.setFont(percent_font)
        stats_layout.addWidget(percent_label)

        stats_grp.setLayout(stats_layout)
        layout.addWidget(stats_grp)
        layout.addSpacing(15)

    def _show_wrong_answers(self, layout, wrong_details):
        """Mostra lista de perguntas erradas."""
        errors_grp = QGroupBox(tr("Perguntas Erradas"))
        errors_layout = QVBoxLayout()

        # Mostra os detalhes num viewer clicável: '*' abre explicação da pergunta
        text_widget = QTextBrowser()
        text_widget.setOpenLinks(False)
        text_widget.setReadOnly(True)
        text_widget.anchorClicked.connect(self._on_wrong_detail_link_clicked)

        blocks: list[str] = []
        for i, detail in enumerate(wrong_details, 1):
            qnum = html.escape(str(detail.get('question_number', '')))
            category = html.escape(str(detail.get('category', '')))
            question_text = html.escape(str(detail.get('question_text', '')))
            user_answer = html.escape(str(detail.get('user_answer', '')))
            correct_answer = html.escape(str(detail.get('correct_answer', '')))

            blocks.append(
                """
                <div style='margin-bottom: 12px;'>
                  <div>
                    <a href='explain:{qnum}' style='text-decoration:none; font-weight:bold;'>*</a>
                    <b>{idx}. {question_lbl} {qnum}</b> ({category})
                  </div>
                  <div style='margin-left: 12px; margin-top: 6px;'>
                    <div><b>{q_lbl}</b> {q_text}</div>
                    <div style='color: red;'><b>{ua_lbl}</b> {ua}</div>
                    <div style='color: green;'><b>{ca_lbl}</b> {ca}</div>
                  </div>
                </div>
                """.format(
                    qnum=qnum,
                    idx=i,
                    question_lbl=html.escape(tr("Questão")),
                    category=category,
                    q_lbl=html.escape(tr("Pergunta:")),
                    q_text=question_text,
                    ua_lbl=html.escape(tr("Sua resposta:")),
                    ua=user_answer,
                    ca_lbl=html.escape(tr("Resposta correta:")),
                    ca=correct_answer,
                )
            )

        text_widget.setHtml("""<div style='font-family: sans-serif;'>{}</div>""".format("".join(blocks)))
        errors_layout.addWidget(text_widget)
        errors_grp.setLayout(errors_layout)
        layout.addWidget(errors_grp)
        layout.addSpacing(15)

    def _on_wrong_detail_link_clicked(self, url: QUrl):
        """Abre explicação ao clicar no '*' em cada resultado."""
        raw = url.toString()
        if raw.startswith('explain:'):
            qnum = raw.split(':', 1)[1]
            if qnum:
                self._explain_question(qnum)

    def _explain_question(self, question_number):
        """Explica uma pergunta específica."""
        # Encontra a pergunta pelo número
        if self.app.parser:
            question = next((q for q in self.app.parser.questions if str(q.number) == str(question_number)), None)
            if question:
                self.app.explain_question(question)
            else:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(self.app, tr("Aviso"), tr("Pergunta") + f" {question_number} " + tr("não encontrada."))
        else:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self.app, tr("Aviso"), tr("Nenhum ficheiro carregado."))

    def _create_buttons(self, layout):
        """Cria botões de ação."""
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        button_layout.setContentsMargins(0, 0, 0, 0)

        back_btn = QPushButton(tr("Voltar ao início"))
        back_btn.clicked.connect(self.app.show_selection_screen)
        button_layout.addWidget(back_btn)

        button_layout.addStretch()
        layout.addWidget(button_widget)
