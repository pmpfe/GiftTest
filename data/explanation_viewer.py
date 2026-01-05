"""
Displays LLM explanations in a rich viewer using QTextBrowser for HTML rendering.
"""

import re
import urllib.request
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QWidget, QSizePolicy, QComboBox, QTextBrowser, QPlainTextEdit, QSplitter, QProgressBar
)
from PySide6.QtCore import Qt, QUrl, QByteArray, Slot
from PySide6.QtGui import QKeyEvent, QDesktopServices, QTextDocument
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PySide6.QtCore import QTimer

from .llm_client import LLMClient
from .i18n import tr
from .constants import (
    LLM_PROVIDERS, DEFAULT_WINDOW_PERCENT,
    MIN_ZOOM, MAX_ZOOM, ZOOM_STEP, DEFAULT_ZOOM, DEFAULT_FONT_SIZE
)


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
        self._zoom = DEFAULT_ZOOM
        self._base_font_size = self.font().pointSize()
        self._last_html: str = ""
        self._net = QNetworkAccessManager(self)
        self._inflight: dict[str, QNetworkReply] = {}
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self._refresh_after_resource_update)

        # Corner loading overlay (animated, non-blocking)
        self._loading_overlay = QWidget(self.viewport())
        self._loading_overlay.setObjectName('loadingOverlay')
        self._loading_overlay.setStyleSheet(
            "#loadingOverlay { background: rgba(255,255,255,200); border: 1px solid #ccc; border-radius: 4px; }"
        )
        overlay_layout = QHBoxLayout(self._loading_overlay)
        overlay_layout.setContentsMargins(6, 4, 6, 4)
        overlay_layout.setSpacing(6)

        self._loading_bar = QProgressBar(self._loading_overlay)
        self._loading_bar.setRange(0, 0)  # indeterminate
        self._loading_bar.setTextVisible(False)
        self._loading_bar.setFixedSize(48, 10)
        overlay_layout.addWidget(self._loading_bar)

        self._loading_label = QLabel(tr("A carregar"), self._loading_overlay)
        self._loading_label.setStyleSheet("color:#444;")
        overlay_layout.addWidget(self._loading_label)

        self._loading_overlay.hide()
        if self._base_font_size <= 0:
            self._base_font_size = DEFAULT_FONT_SIZE
        self.setOpenExternalLinks(False)
        self.setOpenLinks(False)
        self.anchorClicked.connect(self._handle_link)

    def setHtml(self, text: str) -> None:
        self._last_html = text or ""
        super().setHtml(text)

    def set_loading(self, visible: bool, text: str | None = None) -> None:
        if text is not None:
            self._loading_label.setText(text)
        self._loading_overlay.setVisible(bool(visible))
        if visible:
            self._position_loading_overlay()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._loading_overlay.isVisible():
            self._position_loading_overlay()

    def _position_loading_overlay(self) -> None:
        try:
            self._loading_overlay.adjustSize()
            margin = 6
            x = max(margin, self.viewport().width() - self._loading_overlay.width() - margin)
            y = margin
            self._loading_overlay.move(x, y)
        except Exception:
            pass

    def _show_source_dialog(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Código fonte"))
        dlg.setMinimumSize(700, 500)

        layout = QVBoxLayout(dlg)

        editor = QPlainTextEdit()
        editor.setReadOnly(True)
        editor.setPlainText(self._last_html or "")
        layout.addWidget(editor)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton(tr("Fechar"))
        close_btn.clicked.connect(dlg.close)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        dlg.show()

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        menu.addSeparator()
        action = menu.addAction(tr("Ver código fonte"))
        action.triggered.connect(self._show_source_dialog)
        menu.exec(event.globalPos())

    def loadResource(self, type, name):
        """Load external resources like images from HTTP URLs."""
        import os
        debug_enabled = os.environ.get('GIFTTEST_DEBUG_IMAGES') == '1'
        debug_file = Path.home() / '.local' / 'share' / 'main.py' / 'qtbrowser_debug.txt'
        
        if debug_enabled:
            try:
                debug_file.parent.mkdir(parents=True, exist_ok=True)
                with debug_file.open('a', encoding='utf-8') as f:
                    f.write(f"\n🔍 loadResource called: type={type}, name={name}\n")
                    if isinstance(name, QUrl):
                        f.write(f"   URL string: {name.toString()}\n")
            except Exception:
                pass
        
        # QTextDocument.ImageResource = 2
        if type == 2 and isinstance(name, QUrl):
            url_str = name.toString()

            # Serve prefetched bytes if available
            try:
                from .image_enrichment import get_prefetched_image_bytes
                prefetched = get_prefetched_image_bytes(url_str)
                if prefetched:
                    return QByteArray(prefetched)
            except Exception:
                pass
            
            if debug_enabled:
                try:
                    with debug_file.open('a', encoding='utf-8') as f:
                        f.write(f"   Checking if HTTP/HTTPS...\n")
                except Exception:
                    pass
            
            # Only load HTTP/HTTPS images
            if url_str.startswith(('http://', 'https://')):
                # Async fetch to avoid UI freezes.
                if url_str not in self._inflight:
                    try:
                        req = QNetworkRequest(QUrl(url_str))
                        req.setRawHeader(b'User-Agent', b'GiftTest/1.0 (educational app)')
                        # Follow redirects where supported (Qt6 uses RedirectPolicyAttribute)
                        try:
                            req.setAttribute(
                                QNetworkRequest.Attribute.RedirectPolicyAttribute,
                                QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy,
                            )
                        except Exception:
                            pass

                        reply = self._net.get(req)
                        self._inflight[url_str] = reply
                        reply.finished.connect(lambda u=url_str, r=reply: self._on_image_reply_finished(u, r))
                    except Exception as e:
                        if debug_enabled:
                            try:
                                with debug_file.open('a', encoding='utf-8') as f:
                                    f.write(f"   ❌ Async request failed: {e}\n")
                            except Exception:
                                pass
                return QByteArray()
        
        # Fallback to default
        return super().loadResource(type, name)

    def _on_image_reply_finished(self, url_str: str, reply: QNetworkReply) -> None:
        import os
        debug_enabled = os.environ.get('GIFTTEST_DEBUG_IMAGES') == '1'
        debug_file = Path.home() / '.local' / 'share' / 'main.py' / 'qtbrowser_debug.txt'

        try:
            self._inflight.pop(url_str, None)
        except Exception:
            pass

        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                if debug_enabled:
                    try:
                        with debug_file.open('a', encoding='utf-8') as f:
                            f.write(f"   ❌ Network error for {url_str}: {reply.errorString()}\n")
                    except Exception:
                        pass
                reply.deleteLater()
                return

            data = bytes(reply.readAll())
            reply.deleteLater()
            if not data:
                return

            # Store in shared prefetch cache
            try:
                from .image_enrichment import _put_prefetched_image_bytes
                _put_prefetched_image_bytes(url_str, data)
            except Exception:
                pass

            # Add to this document resources
            try:
                self.document().addResource(
                    QTextDocument.ResourceType.ImageResource,
                    QUrl(url_str),
                    QByteArray(data),
                )
            except Exception:
                pass

            # Debounce refresh to avoid re-rendering once per image.
            if not self._refresh_timer.isActive():
                self._refresh_timer.start(50)
        except Exception:
            try:
                reply.deleteLater()
            except Exception:
                pass

    def _refresh_after_resource_update(self) -> None:
        # Re-apply HTML so QTextBrowser requests the now-cached resources.
        try:
            sb = self.verticalScrollBar()
            pos = sb.value() if sb else 0
        except Exception:
            pos = 0

        try:
            html = self._last_html
            if html:
                super().setHtml(html)
        except Exception:
            pass

        try:
            sb = self.verticalScrollBar()
            if sb:
                sb.setValue(pos)
        except Exception:
            pass

    def _handle_link(self, url: QUrl):
        """Open links in external browser."""
        QDesktopServices.openUrl(url)

    def setSource(self, url, type=None):
        """Override to prevent internal navigation - open in browser instead."""
        if url.scheme() in ('http', 'https', 'ftp'):
            QDesktopServices.openUrl(url)
        # Don't call super() - this prevents clearing the content

    def _apply_zoom(self):
        """Apply current zoom factor to font size."""
        font = self.font()
        font.setPointSize(int(self._base_font_size * self._zoom))
        self.setFont(font)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self._zoom = min(self._zoom + ZOOM_STEP, MAX_ZOOM)
            else:
                self._zoom = max(self._zoom - ZOOM_STEP, MIN_ZOOM)
            self._apply_zoom()
            event.accept()
        else:
            super().wheelEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.key() in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
                self._zoom = min(self._zoom + ZOOM_STEP, MAX_ZOOM)
                self._apply_zoom()
                return
            if event.key() == Qt.Key.Key_Minus:
                self._zoom = max(self._zoom - ZOOM_STEP, MIN_ZOOM)
                self._apply_zoom()
                return
            if event.key() == Qt.Key.Key_0:
                self._zoom = DEFAULT_ZOOM
                self._apply_zoom()
                return
        super().keyPressEvent(event)


def show_explanation(
        parent, title: str, html_content: str,
        question_text: str | None = None,
        question_options: list | None = None,
        metadata: dict | None = None,
        on_reexplain_callback=None,
        user_answer: str | None = None,
        user_was_correct: bool | None = None):
    """Shows explanation in a dialog with HTML rendering support.

    Args:
        metadata: Dict with 'provider', 'model', 'time' keys for display.
        user_answer: The answer text given by the user (optional).
        user_was_correct: Whether the user's answer was correct (optional).
    """
    # Obtém preferências do parent (app)
    if hasattr(parent, 'preferences'):
        prefs = parent.preferences
        width_percent, height_percent = prefs.get_explanation_window_size_percent()
    else:
        width_percent, height_percent = DEFAULT_WINDOW_PERCENT, DEFAULT_WINDOW_PERCENT

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
    initial_provider = metadata.get('provider', 'groq') if metadata else 'groq'
    initial_model = metadata.get('model', '') if metadata else ''

    # Provider combo
    provider_layout = QHBoxLayout()
    provider_label = QLabel(tr("Provedor:"))
    provider_combo = QComboBox()
    provider_combo.addItems(LLM_PROVIDERS)
    provider_combo.setCurrentText(initial_provider)
    provider_layout.addWidget(provider_label)
    provider_layout.addWidget(provider_combo)
    left_layout.addLayout(provider_layout)

    # Model combo
    model_layout = QHBoxLayout()
    model_label = QLabel(tr("Modelo:"))
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

    # Image source combo (non-persistent)
    image_source_layout = QHBoxLayout()
    image_source_label = QLabel(tr("Fonte de imagens:"))
    image_source_combo = QComboBox()
    try:
        from .image_enrichment import IMAGE_PROVIDERS
        for key, info in IMAGE_PROVIDERS.items():
            image_source_combo.addItem(info.get('name', key), key)
    except Exception:
        image_source_combo.addItem('none', 'none')

    # Default selection comes from preferences, but changes here do not persist.
    try:
        if hasattr(parent, 'preferences'):
            pref_key = parent.preferences.get_image_provider()
            idx = image_source_combo.findData(pref_key)
            if idx >= 0:
                image_source_combo.setCurrentIndex(idx)
    except Exception:
        pass

    image_source_layout.addWidget(image_source_label)
    image_source_layout.addWidget(image_source_combo)
    left_layout.addLayout(image_source_layout)

    # Explain button
    explain_btn = QPushButton(tr("Obter explicação"))
    explain_btn.setEnabled(True)  # Always enabled
    left_layout.addWidget(explain_btn)

    # Time labels
    time_row = QHBoxLayout()
    time_label = QLabel()
    time_label.setStyleSheet("color: #666;")
    if metadata and 'time' in metadata:
        time_label.setText(f"Tempo (resposta): {metadata['time']:.2f}s")
    else:
        time_label.setText("")

    images_time_label = QLabel("")
    images_time_label.setStyleSheet("color: #666;")

    time_row.addWidget(time_label)
    time_row.addWidget(images_time_label)
    time_row.addStretch()
    left_layout.addLayout(time_row)

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

    # Display user's answer if provided
    if user_answer is not None:
        if user_was_correct:
            answer_color = "#28a745"  # green
            answer_symbol = "✔"
            answer_status = "Correto!"
        else:
            answer_color = "#dc3545"  # red
            answer_symbol = "✖"
            answer_status = "Incorreto"

        user_answer_widget = QLabel(
            f"<div style='padding: 8px; margin: 4px 0; background-color: #f8f9fa; "
            f"border-left: 4px solid {answer_color}; border-radius: 4px;'>"
            f"<span style='color: {answer_color}; font-weight: bold;'>{answer_symbol} {answer_status}</span><br/>"
            f"<b>A sua resposta foi:</b> {user_answer}"
            f"</div>"
        )
        user_answer_widget.setTextFormat(Qt.TextFormat.RichText)
        user_answer_widget.setWordWrap(True)
        layout.addWidget(user_answer_widget)

    # Use QTextBrowser for HTML rendering
    viewer = ZoomableTextBrowser()
    images_viewer = ZoomableTextBrowser()
    images_viewer.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    images_viewer.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    try:
        images_viewer.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
    except Exception:
        pass
    images_viewer.hide()
    
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

    content_splitter = QSplitter(Qt.Orientation.Horizontal)
    content_splitter.setChildrenCollapsible(False)
    content_splitter.addWidget(viewer)
    content_splitter.addWidget(images_viewer)
    content_splitter.setStretchFactor(0, 3)
    content_splitter.setStretchFactor(1, 1)
    try:
        content_splitter.setSizes([int(dialog.width() * 0.75), int(dialog.width() * 0.25)])
    except Exception:
        pass
    layout.addWidget(content_splitter)
    layout.setStretchFactor(header, 0)
    layout.setStretchFactor(content_splitter, 1)

    # Close button
    btn_layout = QHBoxLayout()
    btn_layout.addStretch()
    close_btn = QPushButton(tr("Fechar"))
    close_btn.clicked.connect(dialog.close)
    btn_layout.addWidget(close_btn)
    layout.addLayout(btn_layout)

    # Keep reference to avoid GC closing the window
    try:
        parent._last_explanation_dialog = dialog
    except Exception:
        pass
    dialog.show()

    # Return dialog and widgets to allow updates
    return dialog, viewer, images_viewer, content_splitter, time_label, images_time_label, explain_btn, image_source_combo
