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

from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox
from PySide6.QtCore import QThread, Signal

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
from data.i18n import initialize_translator, change_language, get_current_language, tr
# pylint: enable=wrong-import-position


class LLMWorker(QThread):
    """Worker thread for LLM generation to avoid blocking UI."""
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, client, prompt):
        super().__init__()
        self.client = client
        self.prompt = prompt
        self._cancelled = False
        # Ensure thread is deleted when finished
        self.finished.connect(self.deleteLater)
        self.error.connect(self.deleteLater)

    def cancel(self):
        self._cancelled = True
        # Disconnect auto-delete to handle manually
        self.finished.disconnect(self.deleteLater)
        self.error.disconnect(self.deleteLater)
        if self.isRunning():
            if not self.wait(1000):  # Wait max 1 second
                # If still running, terminate (last resort)
                self.terminate()
                self.wait()
        # Ensure deletion
        self.deleteLater()

    def run(self):
        try:
            if self._cancelled:
                return
            result = self.client.generate(self.prompt)
            if not self._cancelled:
                self.finished.emit(result)
        except Exception as e:
            if not self._cancelled:
                self.error.emit(str(e))


class ImagesWorker(QThread):
    """Worker thread for image search to avoid blocking UI."""
    finished = Signal(int, object, float, str)  # job_id, groups, seconds, provider

    def __init__(self, job_id: int, keywords_list: tuple[str, ...], provider: str):
        super().__init__()
        self.job_id = job_id
        self.keywords_list = keywords_list
        self.provider = provider
        self._cancelled = False
        self.finished.connect(self.deleteLater)

    def cancel(self):
        self._cancelled = True
        # Disconnect auto-delete to handle manually
        self.finished.disconnect(self.deleteLater)
        if self.isRunning():
            self.wait(200)
        # Ensure deletion
        self.deleteLater()

    def run(self):
        try:
            if self._cancelled:
                return
            from data.image_enrichment import fetch_image_groups
            groups, seconds = fetch_image_groups(self.keywords_list, provider=self.provider)
            if not self._cancelled:
                self.finished.emit(self.job_id, groups, float(seconds), self.provider)
        except Exception:
            # Treat unexpected exceptions as an empty result set
            if not self._cancelled:
                self.finished.emit(self.job_id, tuple((tuple(), 'worker_exception') for _ in self.keywords_list), 0.0, self.provider)


class GIFT_TestApp(QMainWindow):
    """Aplicação de Prática de Testes GIFT"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(tr("Sistema de Testes GIFT"))

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
        # Estado por-teste (não persiste entre testes)
        self.correct_me_if_wrong = False
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

    def closeEvent(self, event):
        """Handle application close, ensuring threads are properly cleaned up."""
        if self._llm_worker and self._llm_worker.isRunning():
            self._llm_worker.cancel()
        super().closeEvent(event)

    def load_questions(self, gift_file: str = None):
        """Carrega perguntas do ficheiro GIFT.

        Args:
            gift_file: Caminho do ficheiro GIFT. Se None, não carrega nada.
        """
        if not gift_file:
            return

        if not Path(gift_file).exists():
            QMessageBox.critical(self, tr("Erro"), tr("Ficheiro {0} não encontrado!").format(gift_file))
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
            QMessageBox.critical(self, tr("Erro"), tr("Erro ao carregar perguntas: {0}").format(e))
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
        from PySide6.QtWidgets import (
            QDialog, QVBoxLayout, QLabel, QPushButton,
            QScrollArea, QWidget, QGroupBox
        )
        from PySide6.QtCore import Qt
        from data.i18n import tr
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Sobre o Programa"))
        layout = QVBoxLayout(dlg)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        c_layout = QVBoxLayout(container)

        apptitle_html = (
            f"<div style='text-align:center;'><b>{tr('Sistema de Testes GIFT')}</b></div>"
            "<div style='text-align:center; font-size: small;'><a href='https://github.com/pmpfe/GiftTest'>github.com/pmpfe/GiftTest</a></div>"
            )
        apptitle_label = QLabel(apptitle_html)
        apptitle_label.setTextFormat(Qt.TextFormat.RichText)
        apptitle_label.setOpenExternalLinks(True)
        c_layout.addWidget(apptitle_label)
        c_layout.addSpacing(8)


        # Grupo: O que este programa faz
        what_grp = QGroupBox(tr("O que o programa faz"))
        what_layout = QVBoxLayout()
        what_html = (

            f"<p>- {tr('Praticar testes (a partir de bancos de perguntas)')}</p>"
            f"<p>- {tr('Explorar perguntas e respostas com serviços de IA públicos (função explicar)')}</p>"

        )
        what_lbl = QLabel(what_html)
        what_lbl.setWordWrap(True)
        what_lbl.setTextFormat(Qt.TextFormat.RichText)
        what_layout.addWidget(what_lbl)
        what_grp.setLayout(what_layout)
        c_layout.addWidget(what_grp)

        # Grupo: Como usar
        how_grp = QGroupBox(tr("Como usar"))
        how_layout = QVBoxLayout()
        how_html = (
            "<ol>"
            f"<li>{tr('Cria ou transpõe perguntas para um ficheiro GIFT.')}</li>"
            f"<li>{tr('Carrega o ficheiro na aplicação em Configurações.')}</li>"
            f"<li>{tr('(Opcional) Configura uma API KEY e escolhe um modelo disponível.')}</li>"
            "</ol>"
        )
        how_lbl = QLabel(how_html)
        how_lbl.setWordWrap(True)
        how_lbl.setTextFormat(Qt.TextFormat.RichText)
        how_layout.addWidget(how_lbl)
        how_grp.setLayout(how_layout)
        c_layout.addWidget(how_grp)

                # Grupo: Notas do Autor
        author_grp = QGroupBox(tr("Notas do Autor (pferreira@gmail.com)"))
        author_layout = QVBoxLayout()
        author_html = (
            f"<p>- {tr('A avaliação deve estar ao serviço da aprendizagem, mais do que o contrário.')}</p>"
            f"<p>- {tr('Os modelos de IA, como em diferente medida as enciclopédias, os professores ou a percepção sensorial, são mediadores do acesso ao real. São úteis, mas limitados. Usa-os todos, mas questiona. Imagina, explora, experimenta.')}</p>"
            f"<p>- {tr('Este software é teu. Podes fazer com ele tudo o que quiseres e conseguires.')}</p>"
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
        btn = QPushButton(tr("Fechar"))
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
            QMessageBox.warning(self, tr("Aviso"), tr("Nenhuma pergunta carregada."))
            return
        self.browser = QuestionBrowser(self, self.parser.questions)
        self.browser.show()

    def start_quick_test(self):
        """Inicia um teste rápido com perguntas aleatórias de todas as categorias."""
        if not self.parser or not self.parser.questions:
            QMessageBox.warning(self, tr("Aviso"), tr("Nenhuma pergunta carregada."))
            return

        all_questions = self.parser.questions
        count = min(self.preferences.get_quick_test_questions(), len(all_questions))
        self.selected_questions = random.sample(all_questions, count)

        # Reset
        self.current_question_index = 0
        self.user_answers = {}
        self.correct_me_if_wrong = False

        # Mostra primeira pergunta
        self.show_question()

    def explain_question(self, question_obj=None, user_answer=None, user_was_correct=None):
        """Gera e mostra a explicação via LLM para a pergunta indicada.

        Args:
            question_obj: Objeto da pergunta (opcional). Se não fornecido, lê do campo de texto.
            user_answer: Texto da resposta dada pelo utilizador (opcional).
            user_was_correct: Se a resposta do utilizador estava correta (opcional).
        """
        if not self.parser or not self.parser.questions:
            QMessageBox.warning(self, tr("Aviso"), tr("Nenhuma pergunta carregada."))
            return

        if question_obj:
            question = question_obj
            qnum = str(question.number)
        else:
            qnum_input = (self.explain_question_var.text() or "").strip()
            if not qnum_input:
                QMessageBox.warning(self, tr("Aviso"), tr("Insira um número de pergunta válido."))
                return

            # Try to match both "345" and "Questão 345" formats
            # First, extract just the number from input
            num_match = re.search(r'\d+', qnum_input)
            if not num_match:
                QMessageBox.warning(self, tr("Aviso"), tr("Insira um número de pergunta válido."))
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
                QMessageBox.warning(self, tr("Aviso"), tr("Pergunta {0} não encontrada.").format(qnum_input))
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
        loading_html = f"""
        <div style='text-align:center; padding-top:50px; font-family:sans-serif; color:#666;'>
            <h2>{tr("A gerar explicação")}...</h2>
            <p>{tr("Aguarde enquanto o modelo processa a sua pergunta.")}.</p>
            <p><i>{tr("Isto pode demorar alguns segundos.")}.</i></p>
        </div>
        """

        # Open dialog and keep references
        dialog, viewer_widget, images_viewer_widget, content_splitter, time_label, images_time_label, explain_btn, image_source_combo = show_explanation(
            self,
            tr("Explicação") + f": {qnum}",
            loading_html,
            question_text=question.text,
            question_options=question.options,
            metadata={'provider': provider, 'model': model},
            on_reexplain_callback=lambda p, m: generate_explanation(p, m),
            user_answer=user_answer,
            user_was_correct=user_was_correct
        )

        # Keep references
        dialog_ref = [dialog]
        viewer_ref = [viewer_widget]
        images_viewer_ref = [images_viewer_widget]
        splitter_ref = [content_splitter]
        time_label_ref = [time_label]
        images_time_label_ref = [images_time_label]
        explain_btn_ref = [explain_btn]
        image_source_combo_ref = [image_source_combo]

        keywords_list_ref: list[tuple[str, ...]] = [tuple()]
        image_groups_ref: list[tuple] = [tuple()]
        has_result_ref = [False]
        splitter_last_sizes: list[list[int] | None] = [None]
        images_visible_ref = [False]
        images_job_id_ref = [0]
        images_worker_ref = [None]

        try:
            from PySide6.QtCore import QTimer
            _splitter_resize_timer = QTimer(dialog_ref[0])
            _splitter_resize_timer.setSingleShot(True)
        except Exception:
            _splitter_resize_timer = None
        def _apply_splitter_visibility(show_images: bool):
            try:
                if not splitter_ref[0]:
                    return
                if not images_viewer_ref[0]:
                    return

                # Only act on transitions (do not fight user drags)
                if show_images and not images_visible_ref[0]:
                    images_viewer_ref[0].show()
                    # Restore previous sizes if we have them, else default 75/25
                    if splitter_last_sizes[0]:
                        splitter_ref[0].setSizes(splitter_last_sizes[0])
                    else:
                        w = splitter_ref[0].width() or (dialog_ref[0].width() if dialog_ref[0] else 0)
                        if w > 0:
                            splitter_ref[0].setSizes([int(w * 0.75), int(w * 0.25)])
                    images_visible_ref[0] = True

                if (not show_images) and images_visible_ref[0]:
                    # Save current sizes so user adjustments persist
                    try:
                        splitter_last_sizes[0] = splitter_ref[0].sizes()
                    except Exception:
                        splitter_last_sizes[0] = None
                    images_viewer_ref[0].hide()
                    w = splitter_ref[0].width() or (dialog_ref[0].width() if dialog_ref[0] else 0)
                    if w > 0:
                        splitter_ref[0].setSizes([w, 0])
                    images_visible_ref[0] = False
            except Exception:
                pass


        def _render_images_column_from_cached_groups():
            if not has_result_ref[0]:
                return

            try:
                image_provider = image_source_combo_ref[0].currentData()
            except Exception:
                image_provider = self.preferences.get_image_provider()

            keywords_list = keywords_list_ref[0]

            groups = image_groups_ref[0]
            try:
                if not groups or (len(groups) != len(keywords_list)):
                    return
            except Exception:
                return

            show_images = bool(keywords_list) and image_provider != 'none'
            _apply_splitter_visibility(show_images)

            if not show_images:
                try:
                    if images_viewer_ref[0] and hasattr(images_viewer_ref[0], 'setHtml'):
                        images_viewer_ref[0].setHtml("")
                except Exception:
                    pass
                return

            # Force image width in pixels to avoid QTextBrowser clipping/ignoring % widths.
            target_w = None
            try:
                if images_viewer_ref[0]:
                    vw = images_viewer_ref[0].viewport().width()
                    if vw and vw > 30:
                        target_w = max(30, vw - 12)
            except Exception:
                target_w = None

            from data.image_enrichment import build_images_column_html_from_groups
            images_html = build_images_column_html_from_groups(
                keywords_list,
                groups,
                target_image_width_px=target_w,
            )

            try:
                if images_viewer_ref[0] and hasattr(images_viewer_ref[0], 'setHtml'):
                    if show_images:
                        images_with_style = f"""
                        <!DOCTYPE html>
                        <html>
                        <head>
                            <meta charset="UTF-8">
                            <style>
                                body {{
                                    font-family: Arial, Helvetica, sans-serif;
                                    line-height: 1.3;
                                    margin: 0;
                                    padding: 6px;
                                    overflow-x: hidden;
                                    text-align: center;
                                }}
                                img {{
                                    max-width: 100%;
                                    height: auto;
                                }}
                            </style>
                        </head>
                        <body>
                            {images_html}
                        </body>
                        </html>
                        """
                        images_viewer_ref[0].setHtml(images_with_style)
                    else:
                        images_viewer_ref[0].setHtml("")
            except Exception:
                pass


        def _start_images_fetch_for_current_source():
            """Fetches image groups in a background thread; never blocks the UI."""
            if not has_result_ref[0]:
                return

            try:
                image_provider = image_source_combo_ref[0].currentData()
            except Exception:
                image_provider = self.preferences.get_image_provider()

            keywords_list = keywords_list_ref[0]
            show_images = bool(keywords_list) and image_provider != 'none'
            _apply_splitter_visibility(show_images)

            if not show_images:
                try:
                    if images_viewer_ref[0] and hasattr(images_viewer_ref[0], 'setHtml'):
                        images_viewer_ref[0].setHtml("")
                        if hasattr(images_viewer_ref[0], 'set_loading'):
                            images_viewer_ref[0].set_loading(False)
                except Exception:
                    pass
                try:
                    if images_time_label_ref[0]:
                        images_time_label_ref[0].setText("")
                except Exception:
                    pass
                return

            # Clear old content and show per-pane loading overlay
            try:
                if images_viewer_ref[0] and hasattr(images_viewer_ref[0], 'setHtml'):
                    images_viewer_ref[0].setHtml("")
                if images_viewer_ref[0] and hasattr(images_viewer_ref[0], 'set_loading'):
                    images_viewer_ref[0].set_loading(True, tr("A carregar"))
            except Exception:
                pass

            images_job_id_ref[0] += 1
            job_id = images_job_id_ref[0]

            # Cancel any running worker
            try:
                if images_worker_ref[0] is not None and images_worker_ref[0].isRunning():
                    images_worker_ref[0].cancel()
            except Exception:
                pass

            worker = ImagesWorker(job_id, keywords_list, image_provider)
            images_worker_ref[0] = worker

            def _on_images_finished(done_job_id, groups, seconds, provider_done):
                if done_job_id != images_job_id_ref[0]:
                    return
                try:
                    current_provider = image_source_combo_ref[0].currentData()
                except Exception:
                    current_provider = self.preferences.get_image_provider()
                if provider_done != current_provider:
                    return

                image_groups_ref[0] = groups
                try:
                    if images_time_label_ref[0]:
                        images_time_label_ref[0].setText(f" | Tempo (imagens): {float(seconds):.2f}s")
                except Exception:
                    pass

                _render_images_column_from_cached_groups()

                try:
                    if images_viewer_ref[0] and hasattr(images_viewer_ref[0], 'set_loading'):
                        images_viewer_ref[0].set_loading(False)
                except Exception:
                    pass

            worker.finished.connect(_on_images_finished)
            worker.start()




        # Refresh images when the user changes the image source combo (non-persistent)
        try:
            image_source_combo_ref[0].currentIndexChanged.connect(lambda *_: _start_images_fetch_for_current_source())
        except Exception:
            pass

        # When user drags the splitter, debounce rebuild to fit the new column width (no refetch).
        try:
            if _splitter_resize_timer is not None:
                _splitter_resize_timer.timeout.connect(lambda: _render_images_column_from_cached_groups())
                splitter_ref[0].splitterMoved.connect(lambda *_: _splitter_resize_timer.start(120))
            else:
                splitter_ref[0].splitterMoved.connect(lambda *_: _render_images_column_from_cached_groups())
        except Exception:
            pass


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
            time_text = f"Tempo (resposta): {duration:.2f}s"
            try:
                if time_label_ref[0]:
                    time_label_ref[0].setText(time_text)
            except (RuntimeError, AttributeError):
                # Dialog was closed or widget destroyed
                pass

            # Parse text + IMAGE_KEYWORDS without fetching images
            from data.image_enrichment import split_explanation_text_and_keywords
            text_html, image_blocks, keywords_list = split_explanation_text_and_keywords(result)

            # Embed HTTP request/response details in an HTML comment (view-source only).
            def _safe_html_comment_text(s: str) -> str:
                if s is None:
                    return ''
                s = str(s)
                # Avoid invalid sequences in HTML comments.
                s = s.replace('--', '- -')
                s = s.replace('\x00', '')
                return s

            llm_debug_comment = ''
            try:
                import json as _json
                from data.image_enrichment import is_html_content

                client = None
                try:
                    client = getattr(self._llm_worker, 'client', None)
                except Exception:
                    client = None

                payload = {
                    'provider': provider,
                    'model': model,
                    'request': None,
                    'response': None,
                }
                if client is not None and getattr(client, 'last_http_exchange', None):
                    ex = client.last_http_exchange
                    if isinstance(ex, dict):
                        payload['request'] = (ex.get('request') or None)
                        payload['response'] = (ex.get('response') or None)

                if not is_html_content(result):
                    payload['plaintext_body'] = result

                debug_json = _safe_html_comment_text(_json.dumps(payload, ensure_ascii=False))
                llm_debug_comment = f'<!-- llm_http_debug: {debug_json} -->\n'
            except Exception:
                llm_debug_comment = ''

            keywords_list_ref[0] = keywords_list
            has_result_ref[0] = True

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
                        {llm_debug_comment}{text_html}
                    </body>
                    </html>
                    """
                    viewer_ref[0].setHtml(html_with_style)
                    try:
                        if hasattr(viewer_ref[0], 'set_loading'):
                            viewer_ref[0].set_loading(False)
                    except Exception:
                        pass
                elif viewer_ref[0]:  # QTextEdit fallback
                    viewer_ref[0].setPlainText(re.sub(r"<[^>]+>", "", text_html))
            except (RuntimeError, AttributeError):
                # Dialog was closed or widget destroyed, ignore
                pass

            # Kick off async image search after rendering the answer
            _start_images_fetch_for_current_source()

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
                <h3>{tr("Erro na geração")}</h3>
                <p>{err_msg}</p>
            </div>
            """
            try:
                if viewer_ref[0] and hasattr(viewer_ref[0], 'setHtml'):
                    viewer_ref[0].setHtml(error_html)
                    try:
                        if hasattr(viewer_ref[0], 'set_loading'):
                            viewer_ref[0].set_loading(False)
                    except Exception:
                        pass
                elif viewer_ref[0]:
                    viewer_ref[0].setPlainText(err_msg)
            except (RuntimeError, AttributeError):
                pass

            # Hide/clear images column and timing on error
            try:
                if images_viewer_ref[0] and hasattr(images_viewer_ref[0], 'setHtml'):
                    images_viewer_ref[0].setHtml("")
                    images_viewer_ref[0].hide()
                    try:
                        if hasattr(images_viewer_ref[0], 'set_loading'):
                            images_viewer_ref[0].set_loading(False)
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                if images_time_label_ref[0]:
                    images_time_label_ref[0].setText("")
            except Exception:
                pass
            _apply_splitter_visibility(False)

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
                    time_label_ref[0].setText(tr("A gerar") + "...")
            except:
                pass

            # Reset images UI while loading
            try:
                if images_viewer_ref[0] and hasattr(images_viewer_ref[0], 'setHtml'):
                    images_viewer_ref[0].setHtml("")
                    images_viewer_ref[0].hide()
            except Exception:
                pass
            try:
                if images_time_label_ref[0]:
                    images_time_label_ref[0].setText("")
            except Exception:
                pass
            keywords_list_ref[0] = tuple()
            has_result_ref[0] = False
            _apply_splitter_visibility(False)

            # Per-pane loading indicator for the answer pane
            try:
                if viewer_ref[0] and hasattr(viewer_ref[0], 'set_loading'):
                    viewer_ref[0].set_loading(True, tr("A carregar"))
            except Exception:
                pass
            self._llm_worker.finished.connect(on_success)
            self._llm_worker.error.connect(on_error)
            self._llm_worker.start()

        # Cleanup worker when dialog closes
        def on_dialog_destroyed():
            if hasattr(self, '_llm_worker') and self._llm_worker and self._llm_worker.isRunning():
                self._llm_worker.cancel()
            try:
                if images_worker_ref[0] is not None and images_worker_ref[0].isRunning():
                    images_worker_ref[0].cancel()
                    images_worker_ref[0].wait(1000)
                elif images_worker_ref[0] is not None:
                    images_worker_ref[0].wait(1000)
            except Exception:
                pass
        
        dialog.destroyed.connect(on_dialog_destroyed)

        # Start initial worker
        generate_explanation()

    def clear_history(self):
        """Limpa todo o histórico de testes."""
        response = QMessageBox.question(
            self,
            tr("Confirmar"),
            tr("Tem a certeza que deseja limpar todo o histórico de testes?\n\nEsta ação não pode ser desfeita."),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if response == QMessageBox.StandardButton.Yes:
            self.logger.clear_history()
            QMessageBox.information(self, tr("Sucesso"), tr("Histórico limpo com sucesso!"))
            # Atualiza a tela
            self.show_selection_screen()

    def start_test(self):
        """Inicia o teste com as categorias selecionadas."""
        # Verifica quais categorias foram selecionadas
        selected_categories = [cat for cat, checkbox in self.category_vars.items() if checkbox.isChecked()]

        if not selected_categories:
            QMessageBox.warning(self, tr("Aviso"), tr("Por favor, selecione pelo menos uma categoria!"))
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
        self.correct_me_if_wrong = False

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
                tr("Aviso"),
                tr("Não selecionou nenhuma resposta. Continuar mesmo assim?"),
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
    
    if QApplication.primaryScreen() is None:
        print("No display available. The application requires a graphical display to run.")
        return
    
    # Inicializar internacionalização
    from data.preferences import Preferences
    prefs = Preferences()
    language = prefs.get_language()
    
    if language == 'system':
        from data.i18n import get_default_language
        language = get_default_language()
    
    initialize_translator(app, language)
    
    window = GIFT_TestApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
