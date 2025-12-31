"""
Settings screen for configuring LLM provider, API keys, model selection,
prompt template, theme, and GIFT file path.
"""

import webbrowser

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                               QLineEdit, QComboBox, QTextEdit, QTabWidget, QGroupBox,
                               QFileDialog, QMessageBox, QSpinBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from .llm_client import LLMClient, LLMError


class SettingsScreen:
    def __init__(self, app):
        self.app = app

    def show(self):
        self.app.clear_window()

        central = QWidget()
        self.app.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Configurações")
        title_font = title.font()
        title_font.setPointSize(title_font.pointSize() + 6)
        title_font.setBold(True)
        title.setFont(title_font)
        main_layout.addWidget(title)
        main_layout.addSpacing(15)

        # Tabs
        tabs = QTabWidget()

        tab_general = QWidget()
        tab_llm = QWidget()
        tabs.addTab(tab_general, "Geral")
        tabs.addTab(tab_llm, "LLM")

        self._build_general(tab_general)
        self._build_llm(tab_llm)

        main_layout.addWidget(tabs)

        # Bottom buttons
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.addStretch()

        back_btn = QPushButton("Voltar")
        back_btn.clicked.connect(self.app.show_selection_screen)
        button_layout.addWidget(back_btn)

        save_btn = QPushButton("Guardar")
        save_btn.clicked.connect(self._save)
        button_layout.addWidget(save_btn)

        main_layout.addWidget(button_widget)

    # ---- General ----
    def _build_general(self, parent):
        layout = QVBoxLayout(parent)

        # File selection
        file_grp = QGroupBox("Ficheiro GIFT")
        file_layout = QHBoxLayout()

        file_layout.addWidget(QLabel("Caminho:"))

        self.file_path_entry = QLineEdit()
        self.file_path_entry.setText(self.app.current_gift_file or "")
        self.file_path_entry.setReadOnly(True)
        file_layout.addWidget(self.file_path_entry)

        choose_btn = QPushButton("Escolher...")
        choose_btn.clicked.connect(self._choose_file)
        file_layout.addWidget(choose_btn)

        file_grp.setLayout(file_layout)
        layout.addWidget(file_grp)
        layout.addSpacing(15)

        # Window sizes
        ui_grp = QGroupBox("Tamanhos de Janela")
        ui_layout = QVBoxLayout()

        # Main window size
        main_win_layout = QHBoxLayout()
        main_win_layout.addWidget(QLabel("Janela principal (% do ecrã):"))
        main_win_layout.addWidget(QLabel("Largura:"))

        main_w_pct, main_h_pct = self.app.preferences.get_main_window_size_percent()
        self.main_width_spin = QSpinBox()
        self.main_width_spin.setRange(30, 100)
        self.main_width_spin.setSuffix("%")
        self.main_width_spin.setValue(main_w_pct)
        main_win_layout.addWidget(self.main_width_spin)

        main_win_layout.addWidget(QLabel("Altura:"))
        self.main_height_spin = QSpinBox()
        self.main_height_spin.setRange(30, 100)
        self.main_height_spin.setSuffix("%")
        self.main_height_spin.setValue(main_h_pct)
        main_win_layout.addWidget(self.main_height_spin)
        main_win_layout.addStretch()
        ui_layout.addLayout(main_win_layout)

        # Explanation window size
        expl_win_layout = QHBoxLayout()
        expl_win_layout.addWidget(QLabel("Janela de explicação (% da janela principal):"))
        expl_win_layout.addWidget(QLabel("Largura:"))

        expl_w_pct, expl_h_pct = self.app.preferences.get_explanation_window_size_percent()
        self.expl_width_spin = QSpinBox()
        self.expl_width_spin.setRange(30, 100)
        self.expl_width_spin.setSuffix("%")
        self.expl_width_spin.setValue(expl_w_pct)
        expl_win_layout.addWidget(self.expl_width_spin)

        expl_win_layout.addWidget(QLabel("Altura:"))
        self.expl_height_spin = QSpinBox()
        self.expl_height_spin.setRange(30, 100)
        self.expl_height_spin.setSuffix("%")
        self.expl_height_spin.setValue(expl_h_pct)
        expl_win_layout.addWidget(self.expl_height_spin)
        expl_win_layout.addStretch()
        ui_layout.addLayout(expl_win_layout)

        ui_grp.setLayout(ui_layout)
        layout.addWidget(ui_grp)
        layout.addSpacing(15)

        # Links behavior
        links_grp = QGroupBox("Comportamento de Links")
        links_layout = QHBoxLayout()

        links_layout.addWidget(QLabel("Abrir links da explicação:"))

        self.links_combo = QComboBox()
        self.links_combo.addItem("No browser de sistema", "browser")
        self.links_combo.addItem("Dentro da aplicação", "internal")
        current_behavior = self.app.preferences.get_explanation_links_behavior()
        index = 0 if current_behavior == 'browser' else 1
        self.links_combo.setCurrentIndex(index)
        links_layout.addWidget(self.links_combo)
        links_layout.addStretch()

        links_grp.setLayout(links_layout)
        layout.addWidget(links_grp)
        layout.addSpacing(15)

        # HTML Renderer
        renderer_grp = QGroupBox("Renderizador HTML")
        renderer_layout = QHBoxLayout()

        renderer_layout.addWidget(QLabel("Motor de renderização:"))

        self.renderer_combo = QComboBox()
        self.renderer_combo.addItem("WebEngine (completo, ~150MB)", "webengine")
        self.renderer_combo.addItem("TextBrowser (leve, ~0MB)", "textbrowser")
        current_renderer = self.app.preferences.get_html_renderer()
        index = 0 if current_renderer == 'webengine' else 1
        self.renderer_combo.setCurrentIndex(index)
        renderer_layout.addWidget(self.renderer_combo)
        renderer_layout.addStretch()

        renderer_grp.setLayout(renderer_layout)
        layout.addWidget(renderer_grp)
        layout.addSpacing(15)

        # Teste rápido
        quick_test_grp = QGroupBox("Teste Rápido")
        quick_layout = QHBoxLayout()

        quick_layout.addWidget(QLabel("Número de perguntas:"))

        self.quick_test_spin = QSpinBox()
        self.quick_test_spin.setRange(5, 100)
        self.quick_test_spin.setValue(self.app.preferences.get_quick_test_questions())
        quick_layout.addWidget(self.quick_test_spin)
        quick_layout.addStretch()

        quick_test_grp.setLayout(quick_layout)
        layout.addWidget(quick_test_grp)
        layout.addSpacing(15)

        # Histórico
        history_grp = QGroupBox("Histórico")
        hist_layout = QHBoxLayout()
        reset_btn = QPushButton("Reiniciar Histórico de Testes")
        reset_btn.clicked.connect(self.app.clear_history)
        hist_layout.addWidget(reset_btn)
        hist_layout.addStretch()
        history_grp.setLayout(hist_layout)
        layout.addWidget(history_grp)
        layout.addSpacing(15)

        # Nota: Qt usa o tema do sistema automaticamente
        layout.addStretch()

    def _choose_file(self):
        filename, _ = QFileDialog.getOpenFileName(
            self.app,
            "Escolher ficheiro GIFT",
            "",
            "GIFT files (*.gift.txt);;Text files (*.txt);;All files (*.*)"
        )
        if filename:
            self.app.load_questions(filename)
            self.file_path_entry.setText(filename)

    # ---- LLM ----
    def _build_llm(self, parent):
        layout = QVBoxLayout(parent)
        prefs = self.app.preferences

        # Provider and keys
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)

        top_layout.addWidget(QLabel("Provedor:"))

        providers = ["groq", "huggingface", "gemini", "mistral", "perplexity", "openrouter", "cloudflare"]
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(providers)
        self.provider_combo.setCurrentText(prefs.get_llm_provider())
        self.provider_combo.currentTextChanged.connect(self._on_provider_change)
        top_layout.addWidget(self.provider_combo)

        top_layout.addSpacing(15)
        self.key_label = QLabel(self._get_key_label(self.provider_combo.currentText()))
        top_layout.addWidget(self.key_label)

        self.key_entry = QLineEdit()
        self.key_entry.setText(prefs.get_llm_api_key(self.provider_combo.currentText()))
        self.key_entry.setEchoMode(QLineEdit.EchoMode.Password)
        top_layout.addWidget(self.key_entry)

        instructions_btn = QPushButton("Instruções para obter API KEY")
        instructions_btn.clicked.connect(self._open_api_key_instructions)
        top_layout.addWidget(instructions_btn)

        top_layout.addStretch()
        layout.addWidget(top_widget)
        layout.addSpacing(10)

        # Model selection
        model_grp = QGroupBox("Modelo")
        model_layout = QHBoxLayout()

        model_layout.addWidget(QLabel("Modelo:"))

        self.models_combo = QComboBox()
        self.models_combo.setEditable(True)
        self.models_combo.setCurrentText(prefs.get_llm_model(self.provider_combo.currentText()))
        model_layout.addWidget(self.models_combo)

        fetch_btn = QPushButton("Obter Modelos")
        fetch_btn.clicked.connect(self._fetch_models)
        model_layout.addWidget(fetch_btn)

        model_grp.setLayout(model_layout)
        layout.addWidget(model_grp)
        layout.addSpacing(10)

        # Prompt template
        prompt_grp = QGroupBox("Prompt")
        prompt_layout = QVBoxLayout()

        prompt_layout.addWidget(QLabel("Template usado antes da pergunta:"))

        self.prompt_text = QTextEdit()
        self.prompt_text.setPlainText(prefs.get_llm_prompt_template())
        prompt_layout.addWidget(self.prompt_text)

        prompt_grp.setLayout(prompt_layout)
        layout.addWidget(prompt_grp)
        layout.addSpacing(8)

        # System prompt
        system_grp = QGroupBox("System Prompt (apenas para modelos que o suportam)")
        system_layout = QVBoxLayout()

        system_layout.addWidget(QLabel("Prompt de sistema para definir o papel do modelo:"))

        self.system_prompt_text = QTextEdit()
        self.system_prompt_text.setPlainText(prefs.get_llm_system_prompt())
        system_layout.addWidget(self.system_prompt_text)

        system_grp.setLayout(system_layout)
        layout.addWidget(system_grp)
        layout.addSpacing(8)

        # Test area
        test_btn = QPushButton("Guardar e Testar LLM")
        test_btn.clicked.connect(self._test_llm)
        layout.addWidget(test_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        layout.addStretch()

    def _open_api_key_instructions(self):
        provider = self.provider_combo.currentText()
        query = f"Como obter API key para o {provider}"
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        webbrowser.open(url)

    def _get_key_label(self, provider):
        """Return appropriate label for API key field based on provider."""
        if provider == "cloudflare":
            return "ACCOUNT_ID:API_TOKEN:"
        return "API Key:"

    def _on_provider_change(self, provider):
        """Update key, model, label and fetch models when provider changes."""
        prefs = self.app.preferences
        self.key_label.setText(self._get_key_label(provider))
        self.key_entry.setText(prefs.get_llm_api_key(provider))

        # Fetch models for the new provider and restore saved selection
        saved_model = prefs.get_llm_model(provider)
        key = self.key_entry.text().strip()
        try:
            client = LLMClient(provider, key)
            models = client.list_models()
            self.models_combo.clear()
            if models:
                if isinstance(models[0], dict):
                    # Sort models alphabetically by id (case insensitive)
                    models = sorted(models, key=lambda m: m['id'].lower())
                    for m in models:
                        self.models_combo.addItem(m['id'])
                        if m.get('description'):
                            idx = self.models_combo.count() - 1
                            self.models_combo.setItemData(
                                idx, m['description'], Qt.ItemDataRole.ToolTipRole
                            )

                    # Check if saved model is in the list
                    model_ids = [m['id'] for m in models]
                    if saved_model and saved_model in model_ids:
                        self.models_combo.setCurrentText(saved_model)
                    else:
                        self.models_combo.setCurrentIndex(0)
                else:
                    models = sorted(models, key=str.lower)
                    self.models_combo.addItems(models)
                    # Restore previously selected model if available
                    if saved_model and saved_model in models:
                        self.models_combo.setCurrentText(saved_model)
                    else:
                        self.models_combo.setCurrentIndex(0)
            else:
                # No models found, just set the saved one
                if saved_model:
                    self.models_combo.setCurrentText(saved_model)
        except Exception:
            # On error, just set the saved model
            self.models_combo.clear()
            if saved_model:
                self.models_combo.addItem(saved_model)
                self.models_combo.setCurrentText(saved_model)

    def _fetch_models(self):
        prov = self.provider_combo.currentText()
        key = self.key_entry.text().strip()
        try:
            # Save current selection before clearing
            current = self.models_combo.currentText()
            client = LLMClient(prov, key)
            models = client.list_models()
            if not models:
                QMessageBox.warning(self.app, "Aviso", "Nenhum modelo encontrado para este provedor.")
                return
            self.models_combo.clear()

            if isinstance(models[0], dict):
                for m in models:
                    self.models_combo.addItem(m['id'])
                    if m.get('description'):
                        self.models_combo.setItemData(self.models_combo.count()-1, m['description'], Qt.ItemDataRole.ToolTipRole)

                model_ids = [m['id'] for m in models]
                if current and current in model_ids:
                    self.models_combo.setCurrentText(current)
                else:
                    self.models_combo.setCurrentIndex(0)
            else:
                self.models_combo.addItems(models)
                # Restore selection if it's still available
                if current and current in models:
                    self.models_combo.setCurrentText(current)
                else:
                    self.models_combo.setCurrentIndex(0)
        except LLMError as e:
            QMessageBox.critical(self.app, "Erro", str(e))
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self.app, "Erro", f"Erro inesperado: {e}")

    def _test_llm(self):
        # Save first then try a small generation
        self._save()
        prov = self.provider_combo.currentText()
        key = self.key_entry.text().strip()
        model = self.models_combo.currentText().strip()
        try:
            client = LLMClient(prov, key, model)
            text = client.generate("Diz 'OK' se estás a funcionar.")
            QMessageBox.information(self.app, "LLM OK", f"Resposta: {text[:300]}...")
        except Exception as e:
            QMessageBox.critical(self.app, "Erro", f"Falha ao testar LLM: {e}")

    def _save(self):
        prefs = self.app.preferences
        # File
        if hasattr(self, 'file_path_entry') and self.file_path_entry.text():
            prefs.set_last_gift_file(self.file_path_entry.text())
        # UI
        if hasattr(self, 'main_width_spin'):
            prefs.set_main_window_size_percent(
                self.main_width_spin.value(),
                self.main_height_spin.value()
            )
        if hasattr(self, 'expl_width_spin'):
            prefs.set_explanation_window_size_percent(
                self.expl_width_spin.value(),
                self.expl_height_spin.value()
            )
        if hasattr(self, 'links_combo'):
            behavior = self.links_combo.currentData()
            prefs.set_explanation_links_behavior(behavior)
        if hasattr(self, 'renderer_combo'):
            renderer = self.renderer_combo.currentData()
            prefs.set_html_renderer(renderer)
        if hasattr(self, 'quick_test_spin'):
            prefs.set_quick_test_questions(self.quick_test_spin.value())
        # LLM
        prov = self.provider_combo.currentText()
        key = self.key_entry.text().strip()
        model = self.models_combo.currentText().strip()
        prefs.set_llm_provider(prov)
        prefs.set_llm_api_key(prov, key)
        if model:
            prefs.set_llm_model(prov, model)
        # Prompt
        prompt = self.prompt_text.toPlainText().strip()
        if prompt:
            prefs.set_llm_prompt_template(prompt)
        # System prompt
        system_prompt = self.system_prompt_text.toPlainText().strip()
        if system_prompt:
            prefs.set_llm_system_prompt(system_prompt)
        QMessageBox.information(self.app, "Guardado", "Configurações guardadas com sucesso.")
