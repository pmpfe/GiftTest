"""
Displays LLM explanations in a rich viewer using QWebEngineView for HTML rendering.
Falls back to plain text if QtWebEngine is unavailable.
"""

import re
import subprocess
import sys

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QWidget, QSizePolicy
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QKeyEvent, QDesktopServices

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEnginePage

    class ExplanationPage(QWebEnginePage):
        """Custom page que controla como links são abertos."""

        def __init__(self, parent, open_links_external):
            super().__init__(parent)
            self.open_links_external = open_links_external

        def acceptNavigationRequest(self, url, nav_type, is_main_frame):
            """Intercepta cliques em links."""
            if nav_type == QWebEnginePage.NavigationType.NavigationTypeLinkClicked:
                if self.open_links_external:
                    # Abre no browser externo
                    # Ensure url is a QUrl object
                    if isinstance(url, str):
                        url = QUrl(url)
                    QDesktopServices.openUrl(url)
                    return False
                # Deixa abrir internamente (default)
            return super().acceptNavigationRequest(url, nav_type, is_main_frame)

    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False


def show_explanation(
        parent, title: str, html_content: str,
        question_text: str | None = None,
        question_options: list | None = None,
        metadata: dict | None = None):
    """Shows explanation in a dialog with HTML rendering support.

    Args:
        metadata: Dict with 'provider', 'model', 'time' keys for display.
    """
    # Obtém preferências do parent (app)
    if hasattr(parent, 'preferences'):
        prefs = parent.preferences
        width_percent, height_percent = prefs.get_explanation_window_size_percent()
        links_behavior = prefs.get_explanation_links_behavior()
    else:
        width_percent, height_percent = 66, 66
        links_behavior = 'browser'

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

    # Left side: Title + Metadata
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

    # Metadata label (initially empty or loading)
    meta_label = QLabel()
    meta_label.setStyleSheet("color: #666; font-size: 11px;")
    if metadata:
        meta_text = f"Provider: {metadata.get('provider', '?')} | Modelo: {metadata.get('model', '?')}"
        if 'time' in metadata:
            meta_text += f" | Tempo: {metadata['time']:.2f}s"
        meta_label.setText(meta_text)
    else:
        meta_label.setText("A carregar...")
    left_layout.addWidget(meta_label)

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

    if HAS_WEBENGINE:
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
        custom_page = ExplanationPage(viewer, links_behavior == 'browser')
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
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """
        viewer.setHtml(html_with_style)
        layout.addWidget(viewer)
        # Make viewer take available space when resizing
        layout.setStretchFactor(header, 0)
        layout.setStretchFactor(viewer, 1)
    else:
        info = QLabel("QtWebEngine não instalado. A mostrar como texto simples.")
        info.setStyleSheet("color: gray;")
        layout.addWidget(info)

        hint_btn = QPushButton("Instalar QtWebEngine (pacman -S python-pyqt6-webengine)")
        hint_btn.clicked.connect(
            lambda: subprocess.run(
                [sys.executable, "-m", "pip", "install", "PyQt6-WebEngine"],
                check=False
            )
        )
        layout.addWidget(hint_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addSpacing(10)

        txt = QTextEdit()
        txt.setReadOnly(True)
        txt.setPlainText(re.sub(r"<[^>]+>", "", html_content))
        layout.addWidget(txt)
        layout.setStretchFactor(header, 0)
        layout.setStretchFactor(txt, 1)

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
    return dialog, viewer if HAS_WEBENGINE else txt, meta_label

