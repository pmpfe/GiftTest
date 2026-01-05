"""
Ecrã de apresentação de perguntas.
"""

import html

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QGroupBox,
    QButtonGroup,
    QMessageBox,
    QCheckBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from .i18n import tr


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
        progress_text = tr("Pergunta") + f" {self.app.current_question_index + 1} " + tr("de") + f" {len(self.app.selected_questions)}"
        progress_label = QLabel(progress_text)
        progress_font = progress_label.font()
        progress_font.setItalic(True)
        progress_label.setFont(progress_font)
        main_layout.addWidget(progress_label)

        # Categoria
        if question.category:
            category_label = QLabel(tr("Categoria:") + f" {question.category}")
            category_font = category_label.font()
            category_font.setItalic(True)
            category_label.setFont(category_font)
            main_layout.addWidget(category_label)
            main_layout.addSpacing(10)

        # Pergunta
        question_grp = QGroupBox(tr("Questão") + f" {question.number}")
        question_layout = QVBoxLayout()

        question_label = QLabel(question.text)
        question_label.setWordWrap(True)
        question_layout.addWidget(question_label)

        question_grp.setLayout(question_layout)
        main_layout.addWidget(question_grp)
        main_layout.addSpacing(15)

        # Opções de resposta
        options_grp = QGroupBox(tr("Opções"))
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

        # Opção persistente durante o teste: corrigir após erro
        if not hasattr(self.app, 'correct_me_if_wrong'):
            self.app.correct_me_if_wrong = False
        correct_me_cb = QCheckBox(tr("Corrigir-me se estiver errado"))
        correct_me_cb.setChecked(bool(self.app.correct_me_if_wrong))
        correct_me_cb.toggled.connect(lambda checked: setattr(self.app, 'correct_me_if_wrong', bool(checked)))
        main_layout.addWidget(correct_me_cb)
        main_layout.addSpacing(10)

        # Botões
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        button_layout.setContentsMargins(0, 0, 0, 0)

        if self.app.current_question_index > 0:
            prev_btn = QPushButton(tr("← Anterior"))
            prev_btn.clicked.connect(self.previous_question)
            button_layout.addWidget(prev_btn)

        next_text = tr("Próxima →") if self.app.current_question_index < len(self.app.selected_questions) - 1 else tr("Finalizar")
        next_btn = QPushButton(next_text)
        next_btn.clicked.connect(self.next_question)
        button_layout.addWidget(next_btn)

        # Botão Terminar Agora (Novo)
        finish_btn = QPushButton(tr("Terminar Agora"))
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
            tr("Terminar Teste"),
            tr("Tem a certeza que deseja terminar o teste agora?") + "\n\n" + tr("Apenas as perguntas visualizadas serão contabilizadas."),
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
                tr("Aviso"),
                tr("Não selecionou nenhuma resposta. Continuar mesmo assim?"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if response != QMessageBox.StandardButton.Yes:
                return

        question = self.app.selected_questions[self.app.current_question_index]
        self.app.user_answers[question.number] = answer

        # Se ativado e a resposta estiver errada, mostra diálogo de correção antes de avançar
        if getattr(self.app, 'correct_me_if_wrong', False):
            correct_idx = question.get_correct_answer()
            user_was_correct = (answer != -1 and correct_idx is not None and answer == correct_idx)
            if not user_was_correct:
                # Evita empilhar múltiplos diálogos se o utilizador clicar várias vezes
                existing = getattr(self.app, '_active_correction_dialog', None)
                try:
                    if existing is not None and existing.isVisible():
                        existing.raise_()
                        existing.activateWindow()
                        return
                except Exception:
                    pass

                user_answer_text = (
                    question.options[answer]['text']
                    if answer is not None and answer >= 0 and answer < len(question.options)
                    else tr('Sem resposta')
                )
                correct_answer_text = (
                    question.options[correct_idx]['text']
                    if correct_idx is not None and 0 <= correct_idx < len(question.options)
                    else 'N/A'
                )
                def _advance():
                    try:
                        dlg = getattr(self.app, '_active_correction_dialog', None)
                        if dlg is not None:
                            dlg.close()
                    except Exception:
                        pass
                    self.app.current_question_index += 1
                    self.show()

                self._show_correction_dialog_async(
                    question_obj=question,
                    user_answer_text=user_answer_text,
                    correct_answer_text=correct_answer_text,
                    on_ok=_advance,
                )
                return

        self.app.current_question_index += 1
        self.show()

    def _show_correction_dialog_async(
        self,
        question_obj,
        user_answer_text: str,
        correct_answer_text: str,
        on_ok,
    ):
        """Mostra um diálogo de correção não-modal.

        Não bloqueia a janela de explicação; o teste só prossegue quando o utilizador clicar em OK.
        """
        user_html = html.escape(user_answer_text)
        correct_html = html.escape(correct_answer_text)
        question_number = html.escape(str(getattr(question_obj, 'number', '')))

        msg = QMessageBox(self.app)
        msg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        msg.setWindowModality(Qt.WindowModality.NonModal)
        msg.setModal(False)
        msg.setWindowTitle(tr("Correção") + (f": {question_number}" if question_number else ""))
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(
            """
            <div style='font-family: sans-serif;'>
              <div style='color: red; margin-bottom: 8px;'>✖ <b>{ua_lbl}</b> {ua}</div>
              <div style='color: green;'>✔ <b>{ca_lbl}</b> {ca}</div>
            </div>
            """.format(
                ua_lbl=html.escape(tr("Sua resposta:")),
                ua=user_html,
                ca_lbl=html.escape(tr("Resposta correta:")),
                ca=correct_html,
            )
        )

        ok_btn = msg.addButton(tr("OK"), QMessageBox.ButtonRole.AcceptRole)
        explain_btn = msg.addButton(tr("Explicar"), QMessageBox.ButtonRole.ActionRole)
        msg.setDefaultButton(ok_btn)

        self.app._active_correction_dialog = msg

        def _cleanup():
            if getattr(self.app, '_active_correction_dialog', None) is msg:
                self.app._active_correction_dialog = None

        def _on_clicked(button):
            if button == explain_btn:
                self.app.explain_question(
                    question_obj=question_obj,
                    user_answer=user_answer_text,
                    user_was_correct=False,
                )
                return
            if button == ok_btn:
                _cleanup()
                on_ok()

        msg.buttonClicked.connect(_on_clicked)
        msg.finished.connect(lambda _code: _cleanup())
        msg.show()

    def previous_question(self):
        """Volta para a pergunta anterior."""
        self.app.current_question_index -= 1

        # Restaura resposta anterior se existir
        question = self.app.selected_questions[self.app.current_question_index]
        if question.number in self.app.user_answers:
            self.app.answer_var = self.app.user_answers[question.number]

        self.show()
