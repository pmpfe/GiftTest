"""
Displays LLM explanations in a rich viewer using QWebEngineView for HTML rendering.
Falls back to plain text if QtWebEngine is unavailable.
"""

import re
import subprocess
import sys

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QWidget, QSizePolicy, QComboBox, QTextBrowser
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QKeyEvent, QDesktopServices, QFont


def simplify_html_for_textbrowser(html: str) -> str:
    """Convert complex HTML to QTextBrowser-compatible format."""
    # Remove unsupported CSS properties
    html = re.sub(r'background:\s*linear-gradient\([^)]+\);?', '', html)
    html = re.sub(r'border-radius:\s*[^;]+;?', '', html)
    html = re.sub(r'box-shadow:\s*[^;]+;?', '', html)
    html = re.sub(r'display:\s*flex[^;]*;?', '', html)
    html = re.sub(r'flex[^:]*:\s*[^;]+;?', '', html)
    return html


class ZoomableTextBrowser(QTextBrowser):
    """QTextBrowser with zoom support via Ctrl+wheel and keyboard."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._zoom = 1.0
        self._base_font_size = self.font().pointSize()
        if self._base_font_size <= 0:
            self._base_font_size = 12
        self.setOpenExternalLinks(False)
        self.anchorClicked.connect(self._handle_link)

    def _handle_link(self, url: QUrl):
        """Open links in external browser."""
        QDesktopServices.openUrl(url)

    def _apply_zoom(self):
        """Apply current zoom factor to font size."""
        font = self.font()
        font.setPointSize(int(self._base_font_size * self._zoom))
        self.setFont(font)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self._zoom = min(self._zoom + 0.1, 3.0)
            else:
                self._zoom = max(self._zoom - 0.1, 0.3)
            self._apply_zoom()
            event.accept()
        else:
            super().wheelEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.key() in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
                self._zoom = min(self._zoom + 0.1, 3.0)
                self._apply_zoom()
                return
            if event.key() == Qt.Key.Key_Minus:
                self._zoom = max(self._zoom - 0.1, 0.3)
                self._apply_zoom()
                return
            if event.key() in (Qt.Key.Key_0, Qt.Key.Key_Zero):
                self._zoom = 1.0
                self._apply_zoom()
                return
        super().keyPressEvent(event)

from .llm_client import LLMClient

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings

    class ExplanationPage(QWebEnginePage):
        """Custom page que controla como links são abertos."""

        def __init__(self, parent):
            super().__init__(parent)
            self._stored_html = ""

        def store_html(self, html: str):
            """Store HTML to restore after accidental navigation."""
            self._stored_html = html

        def acceptNavigationRequest(self, url, nav_type, is_main_frame):
            """Intercepta cliques em links."""
            # Allow initial content load (about:blank or data URLs)
            if url.scheme() in ('about', 'data', ''):
                return True
            
            # For any other navigation (link clicks, etc.), open externally
            if nav_type == QWebEnginePage.NavigationType.NavigationTypeLinkClicked:
                QDesktopServices.openUrl(url)
                return False
            
            # Reject other navigations that would replace content
            if is_main_frame and url.scheme() in ('http', 'https'):
                QDesktopServices.openUrl(url)
                return False
            
            return True

        def createWindow(self, window_type):
            """Handle target=_blank links - open in external browser."""
            # Return None to prevent new window, but we need to capture the URL
            # This is handled via acceptNavigationRequest instead
            return None

    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False


def show_explanation(
        parent, title: str, html_content: str,
        question_text: str | None = None,
        question_options: list | None = None,
        metadata: dict | None = None,
        on_reexplain_callback=None):
    """Shows explanation in a dialog with HTML rendering support.

    Args:
        metadata: Dict with 'provider', 'model', 'time' keys for display.
    """
    # Obtém preferências do parent (app)
    if hasattr(parent, 'preferences'):
        prefs = parent.preferences
        width_percent, height_percent = prefs.get_explanation_window_size_percent()
        links_behavior = prefs.get_explanation_links_behavior()
        html_renderer = prefs.get_html_renderer()
    else:
        width_percent, height_percent = 66, 66
        links_behavior = 'browser'
        html_renderer = 'webengine'

    # Create as independent, non-modal dialog
    dialog = QDialog(None)
    dialog.setWindowTitle(title)
    dialog.setWindowModality(Qt.WindowModality.NonModal)
    dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

    # Global stylesheet for borders (if not inherited)
    dialog.setStyleSheet("QDialog { border: 1px solid #ccc; }")

    # Aplica tamanho configurável
    if parent:
        w = int(parent.width() * width_percent / 100)
        h = int(parent.height() * height_percent / 100)
        dialog.resize(w, h)
        # center near parent
        parent_geo = parent.frameGeometry()
        center = parent_geo.center()
        dialog_geo = dialog.frameGeometry()
        dialog_geo.moveCenter(center)
        dialog.move(dialog_geo.topLeft())

    layout = QVBoxLayout(dialog)

    # Header: title left, question right
    header = QWidget()
    header_layout = QHBoxLayout(header)
    header_layout.setContentsMargins(0, 0, 0, 4)
    header_layout.setSpacing(12)

    # Left side: Title + Controls
    left_col = QWidget()
    left_layout = QVBoxLayout(left_col)
    left_layout.setContentsMargins(0, 0, 0, 0)
    left_layout.setSpacing(2)

    title_label = QLabel(title)
    title_font = title_label.font()
    title_font.setPointSize(title_font.pointSize() + 4)
    title_font.setBold(True)
    title_label.setFont(title_font)
    left_layout.addWidget(title_label)

    # Provider and Model controls
    providers = ['groq', 'huggingface', 'gemini', 'mistral', 'perplexity', 'openrouter', 'cloudflare']
    initial_provider = metadata.get('provider', 'groq') if metadata else 'groq'
    initial_model = metadata.get('model', '') if metadata else ''

    # Provider combo
    provider_layout = QHBoxLayout()
    provider_label = QLabel("Provider:")
    provider_combo = QComboBox()
    provider_combo.addItems(providers)
    provider_combo.setCurrentText(initial_provider)
    provider_layout.addWidget(provider_label)
    provider_layout.addWidget(provider_combo)
    left_layout.addLayout(provider_layout)

    # Model combo
    model_layout = QHBoxLayout()
    model_label = QLabel("Modelo:")
    model_combo = QComboBox()
    # Populate initial models
    if hasattr(parent, 'preferences'):
        prefs = parent.preferences
        key = prefs.get_llm_api_key(initial_provider)
        try:
            client = LLMClient(initial_provider, key, system_prompt=prefs.get_llm_system_prompt())
            models = client.list_models()
            model_ids = sorted([m['id'] for m in models if isinstance(m, dict) and m.get('id')], key=str.lower)
            if model_ids:
                model_combo.addItems(model_ids)
                if initial_model and initial_model in model_ids:
                    model_combo.setCurrentText(initial_model)
            else:
                raise RuntimeError("empty model list")
        except Exception:
            # Fallback to default
            default_model = prefs.get_llm_model(initial_provider)
            if default_model:
                model_combo.addItem(default_model)
                model_combo.setCurrentText(default_model)
    model_layout.addWidget(model_label)
    model_layout.addWidget(model_combo)
    left_layout.addLayout(model_layout)

    # Explain button
    explain_btn = QPushButton("Obter explicação")
    explain_btn.setEnabled(True)  # Always enabled
    left_layout.addWidget(explain_btn)

    # Time label
    time_label = QLabel()
    time_label.setStyleSheet("color: #666; font-size: 11px;")
    if metadata and 'time' in metadata:
        time_label.setText(f"Tempo: {metadata['time']:.2f}s")
    else:
        time_label.setText("")
    left_layout.addWidget(time_label)

    def update_model_combo():
        current_provider = provider_combo.currentText()
        model_combo.clear()
        if hasattr(parent, 'preferences'):
            prefs = parent.preferences
            key = prefs.get_llm_api_key(current_provider)
            try:
                # Perplexity does not require an API key to list models (curated list).
                client = LLMClient(current_provider, key, system_prompt=prefs.get_llm_system_prompt())
                models = client.list_models()
                model_ids = sorted([m['id'] for m in models if isinstance(m, dict) and m.get('id')], key=str.lower)
                if model_ids:
                    model_combo.addItems(model_ids)
                    default_model = prefs.get_llm_model(current_provider)
                    if default_model and default_model in model_ids:
                        model_combo.setCurrentText(default_model)
                    return
                raise RuntimeError("empty model list")
            except Exception:
                default_model = prefs.get_llm_model(current_provider)
                if default_model:
                    model_combo.addItem(default_model)

    # Connect signals
    provider_combo.currentTextChanged.connect(update_model_combo)

    # Callback for explain button
    def on_explain():
        if on_reexplain_callback:
            new_provider = provider_combo.currentText()
            new_model = model_combo.currentText()
            explain_btn.setEnabled(False)  # Disable while processing
            on_reexplain_callback(new_provider, new_model)

    explain_btn.clicked.connect(on_explain)

    header_layout.addWidget(left_col, 35)

    if question_text:
        question_label = QLabel(question_text)
        question_label.setWordWrap(True)
        question_label.setStyleSheet("font-style: italic;")
        question_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # allow up to 5 lines visible
        fm = question_label.fontMetrics()
        max_h = fm.lineSpacing() * 5
        question_label.setMaximumHeight(max_h)
        question_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        header_layout.addWidget(question_label, 30)

    # Answers list compact rendering (right side under question)
    if question_options:
        answers_widget = QWidget()
        answers_layout = QVBoxLayout(answers_widget)
        answers_layout.setContentsMargins(0, 0, 0, 0)
        answers_layout.setSpacing(2)
        for opt in question_options:
            text = opt.get('text', '')
            is_correct = bool(opt.get('is_correct', False))
            # Use Unicode symbols for check and cross
            symbol = '✔' if is_correct else '✖'
            color = 'green' if is_correct else 'red'
            lbl = QLabel(f"<span style='color:{color};font-weight:bold'>{symbol}</span> {text}")
            lbl.setTextFormat(Qt.TextFormat.RichText)
            lbl.setWordWrap(True)
            answers_layout.addWidget(lbl)
        header_layout.addWidget(answers_widget, 35)

    layout.addWidget(header)

    # Initialize viewer variable
    viewer = None

    # Decide which renderer to use
    use_webengine = HAS_WEBENGINE and html_renderer == 'webengine'

    if use_webengine:
        # Use QWebEngineView for full HTML/CSS/JS support
        class ZoomableWebView(QWebEngineView):
            def __init__(self):
                super().__init__()
                self._zoom = 1.0
                self.setZoomFactor(self._zoom)

            def wheelEvent(self, event):
                if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                    delta = event.angleDelta().y()
                    if delta > 0:
                        self._zoom = min(self._zoom + 0.1, 3.0)
                    else:
                        self._zoom = max(self._zoom - 0.1, 0.3)
                    self.setZoomFactor(self._zoom)
                    event.accept()
                else:
                    super().wheelEvent(event)

            def keyPressEvent(self, event: QKeyEvent):
                if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                    if event.key() in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
                        self._zoom = min(self._zoom + 0.1, 3.0)
                        self.setZoomFactor(self._zoom)
                        return
                    if event.key() == Qt.Key.Key_Minus:
                        self._zoom = max(self._zoom - 0.1, 0.3)
                        self.setZoomFactor(self._zoom)
                        return
                    if event.key() in (Qt.Key.Key_0, Qt.Key.Key_Zero):
                        self._zoom = 1.0
                        self.setZoomFactor(self._zoom)
                        return
                super().keyPressEvent(event)

        viewer = ZoomableWebView()

        # Define custom page para controlar links
        custom_page = ExplanationPage(viewer)
        viewer.setPage(custom_page)

        # HTML com fonte sans-serif
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
                a {{
                    color: #569cd6;
                }}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """
        viewer.setHtml(html_with_style)
        layout.addWidget(viewer)
        layout.setStretchFactor(header, 0)
        layout.setStretchFactor(viewer, 1)

    elif html_renderer == 'textbrowser' or (not HAS_WEBENGINE and html_renderer == 'webengine'):
        # Use QTextBrowser for lightweight HTML rendering
        if not HAS_WEBENGINE and html_renderer == 'webengine':
            info = QLabel("QtWebEngine não instalado. A usar QTextBrowser.")
            info.setStyleSheet("color: gray; font-size: 10px;")
            layout.addWidget(info)

        viewer = ZoomableTextBrowser()
        # Simplify HTML for QTextBrowser compatibility
        simplified_html = simplify_html_for_textbrowser(html_content)
        # Wrap with basic styling
        html_with_style = f"""
        <html>
        <head><meta charset="UTF-8"></head>
        <body style="font-family: Arial, sans-serif; line-height: 1.5; padding: 8px;">
            {simplified_html}
        </body>
        </html>
        """
        viewer.setHtml(html_with_style)
        layout.addWidget(viewer)
        layout.setStretchFactor(header, 0)
        layout.setStretchFactor(viewer, 1)

    else:
        # Fallback to plain text
        info = QLabel("A mostrar como texto simples.")
        info.setStyleSheet("color: gray;")
        layout.addWidget(info)

        viewer = QTextEdit()
        viewer.setReadOnly(True)
        viewer.setPlainText(re.sub(r"<[^>]+>", "", html_content))
        layout.addWidget(viewer)
        layout.setStretchFactor(header, 0)
        layout.setStretchFactor(viewer, 1)

    # Close button
    btn_layout = QHBoxLayout()
    btn_layout.addStretch()
    close_btn = QPushButton("Fechar")
    close_btn.clicked.connect(dialog.close)
    btn_layout.addWidget(close_btn)
    layout.addLayout(btn_layout)

    # Keep reference to avoid GC closing the window
    try:
        parent._last_explanation_dialog = dialog
    except Exception:
        pass
    dialog.show()

    # Return dialog and viewer to allow updates
    return dialog, viewer, time_label, explain_btn

