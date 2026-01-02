"""
Settings screen for configuring LLM provider, API keys, model selection,
prompt template, theme, and GIFT file path.
"""

import webbrowser

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                               QLineEdit, QComboBox, QTextEdit, QTabWidget, QGroupBox,
                               QFileDialog, QMessageBox, QSpinBox)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from .llm_client import LLMClient, LLMError
from .constants import (
    MIN_WINDOW_PERCENT, MAX_WINDOW_PERCENT,
    MIN_QUICK_TEST_QUESTIONS, MAX_QUICK_TEST_QUESTIONS,
    LLM_PROVIDERS
)
from .i18n import tr, get_current_language, change_language


class SettingsScreen:
    def __init__(self, app):
        self.app = app

    def show(self):
        self.app.clear_window()

        central = QWidget()
        self.app.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel(tr("Settings"))
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
        tabs.addTab(tab_general, tr("Settings"))
        tabs.addTab(tab_llm, tr("LLM"))

        self._build_general(tab_general)
        self._build_llm(tab_llm)

        main_layout.addWidget(tabs)

        # Bottom buttons
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.addStretch()

        back_btn = QPushButton(tr("Back"))
        back_btn.clicked.connect(self.app.show_selection_screen)
        button_layout.addWidget(back_btn)

        save_btn = QPushButton(tr("Save"))
        save_btn.clicked.connect(self._save)
        button_layout.addWidget(save_btn)

        main_layout.addWidget(button_widget)

    # ---- General ----
    def _build_general(self, parent):
        layout = QVBoxLayout(parent)

        # Language selection
        lang_grp = QGroupBox(tr("Language"))
        lang_layout = QHBoxLayout()

        lang_layout.addWidget(QLabel(tr("Language") + ":"))
        self.language_combo = QComboBox()
        self.language_combo.addItem(tr("System Language"), 'system')
        self.language_combo.addItem(tr("Portuguese"), 'pt')
        self.language_combo.addItem(tr("English"), 'en')
        
        current_lang = self.app.preferences.get_language()
        if current_lang == 'system':
            from .i18n import get_default_language
            current_lang = get_default_language()
        
        index = self.language_combo.findData(self.app.preferences.get_language())
        if index >= 0:
            self.language_combo.setCurrentIndex(index)
        
        lang_layout.addWidget(self.language_combo)
        
        # Language flag buttons
        flag_pt_btn = QPushButton("🇵🇹")
        flag_pt_btn.setMaximumWidth(60)
        flag_pt_btn.setMinimumHeight(40)
        # Aumentar o tamanho da fonte para os emojis serem visíveis
        flag_pt_font = flag_pt_btn.font()
        flag_pt_font.setPointSize(16)
        flag_pt_font.setStyleStrategy(flag_pt_font.StyleStrategy.PreferAntialias)
        flag_pt_btn.setFont(flag_pt_font)
        flag_pt_btn.setToolTip("Português (PT)")
        flag_pt_btn.clicked.connect(lambda: self._change_language_with_restart('pt'))
        lang_layout.addWidget(flag_pt_btn)
        
        flag_en_btn = QPushButton("🇬🇧")
        flag_en_btn.setMaximumWidth(60)
        flag_en_btn.setMinimumHeight(40)
        # Aumentar o tamanho da fonte para os emojis serem visíveis
        flag_en_font = flag_en_btn.font()
        flag_en_font.setPointSize(16)
        flag_en_font.setStyleStrategy(flag_en_font.StyleStrategy.PreferAntialias)
        flag_en_btn.setFont(flag_en_font)
        flag_en_btn.setToolTip("English (EN)")
        flag_en_btn.clicked.connect(lambda: self._change_language_with_restart('en'))
        lang_layout.addWidget(flag_en_btn)
        
        lang_layout.addStretch()
        lang_grp.setLayout(lang_layout)
        layout.addWidget(lang_grp)
        layout.addSpacing(15)

        # File selection
        file_grp = QGroupBox(tr("Ficheiro GIFT"))
        file_layout = QHBoxLayout()

        file_layout.addWidget(QLabel(tr("Caminho:")))

        self.file_path_entry = QLineEdit()
        self.file_path_entry.setText(self.app.current_gift_file or "")
        self.file_path_entry.setReadOnly(True)
        file_layout.addWidget(self.file_path_entry)

        choose_btn = QPushButton(tr("Escolher..."))
        choose_btn.clicked.connect(self._choose_file)
        file_layout.addWidget(choose_btn)

        file_grp.setLayout(file_layout)
        layout.addWidget(file_grp)
        layout.addSpacing(15)

        # Window sizes
        ui_grp = QGroupBox(tr("Tamanhos de Janela"))
        ui_layout = QVBoxLayout()

        # Main window size
        main_win_layout = QHBoxLayout()
        main_win_layout.addWidget(QLabel(tr("Janela principal (% do ecrã):")))
        main_win_layout.addWidget(QLabel(tr("Largura:")))

        main_w_pct, main_h_pct = self.app.preferences.get_main_window_size_percent()
        self.main_width_spin = QSpinBox()
        self.main_width_spin.setRange(MIN_WINDOW_PERCENT, MAX_WINDOW_PERCENT)
        self.main_width_spin.setSuffix("%")
        self.main_width_spin.setValue(main_w_pct)
        main_win_layout.addWidget(self.main_width_spin)

        main_win_layout.addWidget(QLabel(tr("Altura:")))
        self.main_height_spin = QSpinBox()
        self.main_height_spin.setRange(MIN_WINDOW_PERCENT, MAX_WINDOW_PERCENT)
        self.main_height_spin.setSuffix("%")
        self.main_height_spin.setValue(main_h_pct)
        main_win_layout.addWidget(self.main_height_spin)
        main_win_layout.addStretch()
        ui_layout.addLayout(main_win_layout)

        # Explanation window size
        expl_win_layout = QHBoxLayout()
        expl_win_layout.addWidget(QLabel(tr("Janela de explicação (% da janela principal):")))
        expl_win_layout.addWidget(QLabel(tr("Largura:")))

        expl_w_pct, expl_h_pct = self.app.preferences.get_explanation_window_size_percent()
        self.expl_width_spin = QSpinBox()
        self.expl_width_spin.setRange(MIN_WINDOW_PERCENT, MAX_WINDOW_PERCENT)
        self.expl_width_spin.setSuffix("%")
        self.expl_width_spin.setValue(expl_w_pct)
        expl_win_layout.addWidget(self.expl_width_spin)

        expl_win_layout.addWidget(QLabel(tr("Altura:")))
        self.expl_height_spin = QSpinBox()
        self.expl_height_spin.setRange(MIN_WINDOW_PERCENT, MAX_WINDOW_PERCENT)
        self.expl_height_spin.setSuffix("%")
        self.expl_height_spin.setValue(expl_h_pct)
        expl_win_layout.addWidget(self.expl_height_spin)
        expl_win_layout.addStretch()
        ui_layout.addLayout(expl_win_layout)

        ui_grp.setLayout(ui_layout)
        layout.addWidget(ui_grp)
        layout.addSpacing(15)

        # Teste rápido
        quick_test_grp = QGroupBox(tr("Teste Rápido"))
        quick_layout = QHBoxLayout()

        quick_layout.addWidget(QLabel(tr("Número de perguntas:")))

        self.quick_test_spin = QSpinBox()
        self.quick_test_spin.setRange(MIN_QUICK_TEST_QUESTIONS, MAX_QUICK_TEST_QUESTIONS)
        self.quick_test_spin.setValue(self.app.preferences.get_quick_test_questions())
        quick_layout.addWidget(self.quick_test_spin)
        quick_layout.addStretch()

        quick_test_grp.setLayout(quick_layout)
        layout.addWidget(quick_test_grp)
        layout.addSpacing(15)

        # Histórico
        history_grp = QGroupBox("Histórico")
        hist_layout = QHBoxLayout()
        reset_btn = QPushButton(tr("Reiniciar Histórico de Testes"))
        reset_btn.clicked.connect(self.app.clear_history)
        hist_layout.addWidget(reset_btn)
        hist_layout.addStretch()
        history_grp.setLayout(hist_layout)
        layout.addWidget(history_grp)
        layout.addSpacing(15)

        # Nota: Qt usa o tema do sistema automaticamente
        layout.addStretch()

    def _change_language_with_restart(self, language_code: str):
        """Muda a linguagem com confirmação e reinicia a aplicação."""
        current_lang = self.app.preferences.get_language()
        
        # Se a língua já está configurada, não faz nada
        if current_lang == language_code:
            return
        
        # Mensagens de confirmação em português (a aplicação está em português por padrão)
        language_names = {
            'pt': 'Português',
            'en': 'English'
        }
        
        # Obter os textos na linguagem atual
        current_language_actual = current_lang
        if current_language_actual == 'system':
            from .i18n import get_default_language
            current_language_actual = get_default_language()
        
        # Determinar o texto de confirmação na língua atual
        if current_language_actual == 'pt':
            question_text = f"Deseja alterar a língua para {language_names.get(language_code, language_code)} e reiniciar a aplicação?"
            restart_button = "Alterar e Reiniciar"
            cancel_button = "Cancelar"
        else:
            question_text = f"Do you want to change the language to {language_names.get(language_code, language_code)} and restart the application?"
            restart_button = "Change and Restart"
            cancel_button = "Cancel"
        
        reply = QMessageBox.question(
            self.app,
            "Language" if current_language_actual == 'en' else "Idioma",
            question_text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Guardar a nova linguagem
            self.app.preferences.set_language(language_code)
            
            # Reiniciar a aplicação usando QProcess para ser mais elegante
            from PySide6.QtCore import QProcess
            import sys
            
            # Iniciar nova instância
            QProcess.startDetached(sys.executable, sys.argv)
            
            # Fechar a aplicação atual
            from PySide6.QtWidgets import QApplication
            QApplication.quit()

    def _choose_file(self):
        filename, _ = QFileDialog.getOpenFileName(
            self.app,
            tr("Escolher ficheiro GIFT"),
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

        top_layout.addWidget(QLabel(tr("Provedor:")))

        self.provider_combo = QComboBox()
        self.provider_combo.addItems(LLM_PROVIDERS)
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

        instructions_btn = QPushButton(tr("Instruções para obter API KEY"))
        instructions_btn.clicked.connect(self._open_api_key_instructions)
        top_layout.addWidget(instructions_btn)

        top_layout.addStretch()
        layout.addWidget(top_widget)
        layout.addSpacing(10)

        # Model selection
        model_grp = QGroupBox("Modelo")
        model_layout = QHBoxLayout()

        model_layout.addWidget(QLabel(tr("Modelo:")))

        self.models_combo = QComboBox()
        self.models_combo.setEditable(True)
        self.models_combo.setCurrentText(prefs.get_llm_model(self.provider_combo.currentText()))
        model_layout.addWidget(self.models_combo)

        fetch_btn = QPushButton(tr("Obter Modelos"))
        fetch_btn.clicked.connect(self._fetch_models)
        model_layout.addWidget(fetch_btn)

        model_grp.setLayout(model_layout)
        layout.addWidget(model_grp)
        layout.addSpacing(10)

        # Prompt template
        prompt_grp = QGroupBox("Prompt")
        prompt_layout = QVBoxLayout()

        prompt_layout.addWidget(QLabel(tr("Template usado antes da pergunta:")))

        self.prompt_text = QTextEdit()
        self.prompt_text.setPlainText(prefs.get_llm_prompt_template())
        prompt_layout.addWidget(self.prompt_text)

        prompt_grp.setLayout(prompt_layout)
        layout.addWidget(prompt_grp)
        layout.addSpacing(8)

        # System prompt
        system_grp = QGroupBox(tr("System Prompt") + " " + tr("(apenas para modelos que o suportam)"))
        system_layout = QVBoxLayout()

        system_layout.addWidget(QLabel(tr("Prompt de sistema para definir o papel do modelo:")))

        self.system_prompt_text = QTextEdit()
        self.system_prompt_text.setPlainText(prefs.get_llm_system_prompt())
        system_layout.addWidget(self.system_prompt_text)

        system_grp.setLayout(system_layout)
        layout.addWidget(system_grp)
        layout.addSpacing(8)

        # Test area
        test_btn = QPushButton(tr("Guardar e Testar LLM"))
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
        
        # Language
        if hasattr(self, 'language_combo'):
            new_language = self.language_combo.currentData()
            old_language = prefs.get_language()
            
            if new_language == 'system':
                from .i18n import get_default_language
                new_language_resolved = get_default_language()
            else:
                new_language_resolved = new_language
            
            if old_language != new_language:
                prefs.set_language(new_language)
                if old_language != 'system':
                    from .i18n import get_default_language
                    old_language_resolved = get_default_language() if old_language == 'system' else old_language
                else:
                    old_language_resolved = get_default_language()
                
                if old_language_resolved != new_language_resolved:
                    change_language(self.app, new_language_resolved)
                    QMessageBox.information(
                        self.app, 
                        tr("Settings"),
                        tr("Language changed. Restart to apply.")
                    )
        
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
