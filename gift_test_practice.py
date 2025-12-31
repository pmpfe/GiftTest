#!/usr/bin/env python3
"""
Sistema de Prática de Testes GIFT - Interface Gráfica
Permite selecionar categorias, responder perguntas e ver resultados.
"""

import random
import re
import sys
import time
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox
from PyQt6.QtCore import QThread, pyqtSignal

sys.path.insert(0, str(Path(__file__).parent))
# pylint: disable=wrong-import-position
from data.gift_parser import GiftParser
from data.test_logger import TestLogger
from data.preferences import Preferences
from data.selection_screen import SelectionScreen
from data.settings_screen import SettingsScreen
from data.llm_client import LLMClient
from data.explanation_viewer import show_explanation
from data.question_screen import QuestionScreen
from data.results_screen import ResultsScreen
from data.question_browser import QuestionBrowser
# pylint: enable=wrong-import-position


class LLMWorker(QThread):
    """Worker thread for LLM generation to avoid blocking UI."""
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, client, prompt):
        super().__init__()
        self.client = client
        self.prompt = prompt

    def run(self):
        try:
            result = self.client.generate(self.prompt)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class GIFT_TestApp(QMainWindow):
    """Aplicação de Prática de Testes GIFT"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sistema de Testes GIFT")

        # Global stylesheet for borders
        self.setStyleSheet("""
            QMainWindow, QDialog {
                border: 1px solid #ccc;
            }
        """)

        # Dados
        self.parser = None
        self.logger = TestLogger()
        self.preferences = Preferences()
        self.selected_questions = []
        self.current_question_index = 0
        self.user_answers = {}  # {question_number: answer_index}
        self.current_gift_file = None
        self._llm_worker = None  # Keep reference to thread

        # Variáveis de UI que serão criadas pelos screens
        self.category_vars = {}
        self.category_spinboxes = {}
        self.answer_var = None
        self.explain_question_var = None

        # Tenta carregar último ficheiro usado
        last_file = self.preferences.get_last_gift_file()
        if last_file:
            self.load_questions(last_file)

        # Inicia na tela de seleção
        self.show_selection_screen()

    def showEvent(self, event):
        """Aplica tamanho configurável na primeira vez que a janela é mostrada."""
        super().showEvent(event)
        if not hasattr(self, '_geometry_applied'):
            self._geometry_applied = True
            self._apply_configured_geometry()

    def _apply_configured_geometry(self):
        """Aplica tamanho da janela baseado nas preferências."""
        width_percent, height_percent = self.preferences.get_main_window_size_percent()
        primary_screen = QApplication.primaryScreen()
        if primary_screen is None:
            # Fallback if no screen is available (headless or display issues)
            self.resize(800, 600)
            return
        screen = primary_screen.geometry()
        w = int(screen.width() * width_percent / 100)
        h = int(screen.height() * height_percent / 100)
        self.resize(w, h)

    def load_questions(self, gift_file: str = None):
        """Carrega perguntas do ficheiro GIFT.

        Args:
            gift_file: Caminho do ficheiro GIFT. Se None, não carrega nada.
        """
        if not gift_file:
            return

        if not Path(gift_file).exists():
            QMessageBox.critical(self, "Erro", f"Ficheiro {gift_file} não encontrado!")
            return

        try:
            self.parser = GiftParser(gift_file)
            self.current_gift_file = gift_file
            self.preferences.set_last_gift_file(gift_file)
            print(f"Carregadas {len(self.parser.questions)} perguntas de {gift_file}")

            # Atualiza a tela se já estiver na tela de seleção
            if hasattr(self, 'category_vars') and self.category_vars:
                self.show_selection_screen()

        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao carregar perguntas: {e}")
            self.parser = None
            self.current_gift_file = None

    def clear_window(self):
        """Limpa o widget central da janela."""
        widget = self.centralWidget()
        if widget:
            widget.deleteLater()

    def show_selection_screen(self):
        """Mostra tela de seleção de categorias e número de perguntas."""
        self.selection_screen = SelectionScreen(self)
        self.selection_screen.show()

    def show_about(self):
        """Mostra diálogo 'Sobre o Programa'."""
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QLabel, QPushButton,
            QScrollArea, QWidget, QGroupBox
        )
        from PyQt6.QtCore import Qt
        dlg = QDialog(self)
        dlg.setWindowTitle("Sobre o Programa")
        layout = QVBoxLayout(dlg)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        c_layout = QVBoxLayout(container)

        apptitle_html = (
            "<div style='text-align:center;'><b>Sistema de Testes GIFT</b></div>"
            "<div style='text-align:center; font-size: small;'><a href='https://github.com/pmpfe/GiftTest'>github.com/pmpfe/GiftTest</a></div>"
            )
        apptitle_label = QLabel(apptitle_html)
        apptitle_label.setTextFormat(Qt.TextFormat.RichText)
        apptitle_label.setOpenExternalLinks(True)
        c_layout.addWidget(apptitle_label)
        c_layout.addSpacing(8)


        # Grupo: O que este programa faz
        what_grp = QGroupBox("O que o programa faz")
        what_layout = QVBoxLayout()
        what_html = (

            "<p>- Praticar testes (a partir de bancos de perguntas)</p>"
            "<p>- Explorar perguntas e respostas com serviços de IA públicos (função explicar)</p>"

        )
        what_lbl = QLabel(what_html)
        what_lbl.setWordWrap(True)
        what_lbl.setTextFormat(Qt.TextFormat.RichText)
        what_layout.addWidget(what_lbl)
        what_grp.setLayout(what_layout)
        c_layout.addWidget(what_grp)

        # Grupo: Como usar
        how_grp = QGroupBox("Como usar")
        how_layout = QVBoxLayout()
        how_html = (
            "<ol>"
            "<li>Cria ou transpõe perguntas para um ficheiro GIFT.</li>"
            "<li>Carrega o ficheiro na aplicação em Configurações.</li>"
            "<li>(Opcional) Configura uma API KEY e escolhe um modelo disponível.</li>"
            "</ol>"
        )
        how_lbl = QLabel(how_html)
        how_lbl.setWordWrap(True)
        how_lbl.setTextFormat(Qt.TextFormat.RichText)
        how_layout.addWidget(how_lbl)
        how_grp.setLayout(how_layout)
        c_layout.addWidget(how_grp)

                # Grupo: Notas do Autor
        author_title = QLabel("Notas do autor (<a href='mailto:pferreira@gmail.com'>pferreira@gmail.com</a>)")
        author_title.setTextFormat(Qt.TextFormat.RichText)
        author_title.setOpenExternalLinks(True)
        # author_title.setStyleSheet("font-weight: bold; font-size: 14px;")
        c_layout.addWidget(author_title)

        author_grp = QGroupBox()
        author_layout = QVBoxLayout()
        author_html = (
            "<p>- A avaliação deve estar ao serviço da aprendizagem, "
            "mais do que o contrário.</p>"
            "<p>- Os modelos de IA, como em diferente medida as enciclopédias, "
            "os professores ou a percepção sensorial, são mediadores do acesso "
            "ao real. São úteis, mas limitados. Usa-os todos, mas questiona. "
            "Imagina, explora, experimenta.</p>"
            "<p>- Este software é teu. Podes fazer com ele tudo o que quiseres "
            "e conseguires.</p>"
        )
        author_lbl = QLabel(author_html)
        author_lbl.setWordWrap(True)
        author_lbl.setTextFormat(Qt.TextFormat.RichText)
        author_layout.addWidget(author_lbl)
        author_grp.setLayout(author_layout)
        c_layout.addWidget(author_grp)

        c_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)
        btn = QPushButton("Fechar")
        btn.clicked.connect(dlg.close)
        layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignRight)
        dlg.resize(600, 600)
        dlg.exec()

    def select_all_categories(self):
        """Seleciona todas as categorias."""
        for checkbox in self.category_vars.values():
            checkbox.setChecked(True)

    def deselect_all_categories(self):
        """Desmarca todas as categorias."""
        for checkbox in self.category_vars.values():
            checkbox.setChecked(False)

    def show_settings(self):
        """Abre o ecrã de configurações."""
        self.settings_screen = SettingsScreen(self)
        self.settings_screen.show()

    def show_question_browser(self):
        """Abre o explorador de perguntas."""
        if not self.parser or not self.parser.questions:
            QMessageBox.warning(self, "Aviso", "Nenhuma pergunta carregada.")
            return
        self.browser = QuestionBrowser(self, self.parser.questions)
        self.browser.show()

    def start_quick_test(self):
        """Inicia um teste rápido com perguntas aleatórias de todas as categorias."""
        if not self.parser or not self.parser.questions:
            QMessageBox.warning(self, "Aviso", "Nenhuma pergunta carregada.")
            return

        all_questions = self.parser.questions
        count = min(self.preferences.get_quick_test_questions(), len(all_questions))
        self.selected_questions = random.sample(all_questions, count)

        # Reset
        self.current_question_index = 0
        self.user_answers = {}

        # Mostra primeira pergunta
        self.show_question()

    def explain_question(self, question_obj=None):
        """Gera e mostra a explicação via LLM para a pergunta indicada.

        Args:
            question_obj: Objeto da pergunta (opcional). Se não fornecido, lê do campo de texto.
        """
        if not self.parser or not self.parser.questions:
            QMessageBox.warning(self, "Aviso", "Nenhuma pergunta carregada.")
            return

        if question_obj:
            question = question_obj
            qnum = str(question.number)
        else:
            qnum_input = (self.explain_question_var.text() or "").strip()
            if not qnum_input:
                QMessageBox.warning(self, "Aviso", "Insira um número de pergunta válido.")
                return

            # Try to match both "345" and "Questão 345" formats
            # First, extract just the number from input
            num_match = re.search(r'\d+', qnum_input)
            if not num_match:
                QMessageBox.warning(self, "Aviso", "Insira um número de pergunta válido.")
                return

            search_num = num_match.group()

            # Search for question - try exact match first, then by number only
            question = None
            for q in self.parser.questions:
                if str(q.number) == qnum_input or str(q.number) == f"Questão {search_num}":
                    question = q
                    break

            # Fallback: search by number only (e.g., "345" in "Questão 345")
            if not question:
                for q in self.parser.questions:
                    q_num_match = re.search(r'\d+', str(q.number))
                    if q_num_match and q_num_match.group() == search_num:
                        question = q
                        break

            if not question:
                QMessageBox.warning(self, "Aviso", f"Pergunta {qnum_input} não encontrada.")
                return

            qnum = str(question.number)

        # Monta prompt a partir do template + pergunta e opções
        template = self.preferences.get_llm_prompt_template()
        prompt = template.strip()
        prompt += "\n\nPergunta:"\
                  f"\n{question.text}\n\nRespostas possíveis:"\
                  + "\n".join([f"- {opt['text']}" for opt in question.options])

        provider = self.preferences.get_llm_provider()
        key = self.preferences.get_llm_api_key(provider)
        model = self.preferences.get_llm_model(provider)

        # Show viewer immediately with loading state
        loading_html = """
        <div style='text-align:center; padding-top:50px; font-family:sans-serif; color:#666;'>
            <h2>A gerar explicação...</h2>
            <p>Aguarde enquanto o modelo processa a sua pergunta.</p>
            <p><i>Isto pode demorar alguns segundos.</i></p>
        </div>
        """

        # Open dialog and keep references
        dialog, viewer_widget, time_label, explain_btn = show_explanation(
            self,
            f"Explicação: {qnum}",
            loading_html,
            question_text=question.text,
            question_options=question.options,
            metadata={'provider': provider, 'model': model},
            on_reexplain_callback=lambda p, m: generate_explanation(p, m)
        )

        # Keep references
        dialog_ref = [dialog]
        viewer_ref = [viewer_widget]
        time_label_ref = [time_label]
        explain_btn_ref = [explain_btn]

        start_time = time.time()

        def on_success(result):
            # Check if dialog still exists and is visible
            try:
                if not dialog_ref[0]:
                    return
                if not dialog_ref[0].isVisible():
                    return
            except (RuntimeError, AttributeError):
                # Dialog was deleted or no longer valid
                return

            end_time = time.time()
            duration = end_time - start_time

            # Update time label
            time_text = f"Tempo: {duration:.2f}s"
            try:
                if time_label_ref[0]:
                    time_label_ref[0].setText(time_text)
            except (RuntimeError, AttributeError):
                # Dialog was closed or widget destroyed
                pass

            # Wrap plaintext in monospace HTML if no HTML tags detected
            if not ("<p>" in result or "<div" in result or "<html" in result or "<ul" in result):
                escaped = result.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                html = f"<html><body><pre style='white-space:pre-wrap;font-family:monospace;'>{escaped}</pre></body></html>"
            else:
                html = result

            # Update viewer content
            try:
                if viewer_ref[0] and hasattr(viewer_ref[0], 'setHtml'):  # QWebEngineView
                    # Re-apply style
                    html_with_style = f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <meta charset="UTF-8">
                        <style>
                            body {{
                                font-family: Arial, Helvetica, sans-serif;
                                line-height: 1.6;
                                padding: 10px;
                            }}
                        </style>
                    </head>
                    <body>
                        {html}
                    </body>
                    </html>
                    """
                    viewer_ref[0].setHtml(html_with_style)
                elif viewer_ref[0]:  # QTextEdit fallback
                    viewer_ref[0].setPlainText(re.sub(r"<[^>]+>", "", html))
            except (RuntimeError, AttributeError):
                # Dialog was closed or widget destroyed, ignore
                pass

            # Re-enable button
            try:
                if explain_btn_ref[0]:
                    explain_btn_ref[0].setEnabled(True)
            except:
                pass

        def on_error(err_msg):
            # Check if dialog still exists
            if not dialog_ref[0] or not dialog_ref[0].isVisible():
                return

            error_html = f"""
            <div style='color:red; padding:20px; font-family:sans-serif;'>
                <h3>Erro na geração</h3>
                <p>{err_msg}</p>
            </div>
            """
            try:
                if viewer_ref[0] and hasattr(viewer_ref[0], 'setHtml'):
                    viewer_ref[0].setHtml(error_html)
                elif viewer_ref[0]:
                    viewer_ref[0].setPlainText(err_msg)
            except (RuntimeError, AttributeError):
                pass

            # Re-enable button
            try:
                if explain_btn_ref[0]:
                    explain_btn_ref[0].setEnabled(True)
            except:
                pass

        # Function to generate explanation
        def generate_explanation(new_provider=None, new_model=None):
            nonlocal provider, model, start_time
            if new_provider:
                provider = new_provider
            if new_model:
                model = new_model
            start_time = time.time()
            key = self.preferences.get_llm_api_key(provider)
            client = LLMClient(provider, key, model, self.preferences.get_llm_system_prompt())
            self._llm_worker = LLMWorker(client, prompt)
            # Update time_label to loading
            try:
                if time_label_ref[0]:
                    time_label_ref[0].setText("A gerar...")
            except:
                pass
            self._llm_worker.finished.connect(on_success)
            self._llm_worker.error.connect(on_error)
            self._llm_worker.start()

        # Start initial worker
        generate_explanation()

    def clear_history(self):
        """Limpa todo o histórico de testes."""
        response = QMessageBox.question(
            self,
            "Confirmar",
            "Tem a certeza que deseja limpar todo o histórico de testes?\n\nEsta ação não pode ser desfeita.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if response == QMessageBox.StandardButton.Yes:
            self.logger.clear_history()
            QMessageBox.information(self, "Sucesso", "Histórico limpo com sucesso!")
            # Atualiza a tela
            self.show_selection_screen()

    def start_test(self):
        """Inicia o teste com as categorias selecionadas."""
        # Verifica quais categorias foram selecionadas
        selected_categories = [cat for cat, checkbox in self.category_vars.items() if checkbox.isChecked()]

        if not selected_categories:
            QMessageBox.warning(self, "Aviso", "Por favor, selecione pelo menos uma categoria!")
            return

        # Seleciona perguntas aleatórias de cada categoria
        self.selected_questions = []

        for category in selected_categories:
            try:
                num_questions = int(self.category_spinboxes[category].value())
            except (ValueError, AttributeError):
                num_questions = 1

            available_questions = self.parser.get_questions_by_category(category)

            # Seleciona aleatoriamente
            num_questions =min(num_questions, len(available_questions))
            

            selected = random.sample(available_questions, num_questions)
            self.selected_questions.extend(selected)

        # Embaralha a ordem das perguntas
        random.shuffle(self.selected_questions)

        # Reset
        self.current_question_index = 0
        self.user_answers = {}

        # Mostra primeira pergunta
        self.show_question()

    def show_question(self):
        """Mostra a pergunta atual."""
        if self.current_question_index >= len(self.selected_questions):
            self.show_results()
            return

        self.question_screen = QuestionScreen(self)
        self.question_screen.show()

    def next_question(self):
        """Vai para a próxima pergunta."""
        # Guarda resposta
        answer = self.answer_var if self.answer_var is not None else -1

        if answer == -1:
            response = QMessageBox.question(
                self,
                "Aviso",
                "Não selecionou nenhuma resposta. Continuar mesmo assim?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if response != QMessageBox.StandardButton.Yes:
                return

        question = self.selected_questions[self.current_question_index]
        self.user_answers[question.number] = answer

        self.current_question_index += 1
        self.show_question()

    def previous_question(self):
        """Volta para a pergunta anterior."""
        self.current_question_index -= 1

        # Restaura resposta anterior se existir
        question = self.selected_questions[self.current_question_index]
        if question.number in self.user_answers:
            self.answer_var = self.user_answers[question.number]

        self.show_question()

    def show_results(self):
        """Mostra os resultados do teste."""
        self.results_screen = ResultsScreen(self)
        self.results_screen.show()


def main():
    """Função principal."""
    app = QApplication(sys.argv)
    window = GIFT_TestApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
