"""
Gestor de preferências da aplicação.
"""

import json
from pathlib import Path
from typing import Optional

from .constants import (
    MIN_WINDOW_PERCENT, MAX_WINDOW_PERCENT, DEFAULT_WINDOW_PERCENT,
    MIN_QUICK_TEST_QUESTIONS, MAX_QUICK_TEST_QUESTIONS, DEFAULT_QUICK_TEST_QUESTIONS,
    DEFAULT_LLM_PROVIDER, LLM_PROVIDERS
)


class Preferences:
    """Gere preferências persistentes da aplicação."""

    def __init__(self, pref_file: str = "data/preferences.json"):
        self.pref_file = Path(pref_file)
        self.pref_file.parent.mkdir(exist_ok=True)

        # Cria ficheiro com valores padrão se não existir
        if not self.pref_file.exists():
            self._write_preferences({
                'last_gift_file': '',
                'theme': 'default',
                'ui': {
                    'main_window_width_percent': 66,
                    'main_window_height_percent': 66,
                    'explanation_width_percent': 66,
                    'explanation_height_percent': 66,
                    'explanation_links_behavior': 'browser',  # 'browser' or 'internal'
                    'quick_test_questions': 20
                },
                'llm': {
                    'provider': 'groq',
                    'api_keys': {
                        'groq': '',
                        'huggingface': '',
                        'gemini': '',
                        'mistral': '',
                        'perplexity': '',
                        'openrouter': '',
                        'cloudflare': ''
                    },
                    'models': {
                        'groq': 'llama-3.3-70b-versatile',
                        'huggingface': 'meta-llama/Llama-3.1-8B-Instruct',
                        'gemini': 'gemini-1.5-flash',
                        'mistral': 'mistral-small-latest',
                        'perplexity': 'llama-3.1-sonar-small',
                        'openrouter': 'meta-llama/Meta-Llama-3.1-8B-Instruct',
                        'cloudflare': '@cf/meta/llama-3-8b-instruct'
                    },
                    'prompt_template': (
                        "Por favor explica, com rigor, a resposta certa e "
                        "as respostas erradas da pergunta em baixo.\\n"
                        "Usa formatação HTML (tags <p>, <strong>, <ul>, "
                        "<li>, <a href='...'>) para estruturar a resposta, "
                        "incluindo links clicáveis se relevante (por exemplo, "
                        "para artigos científicos ou recursos educacionais)."
                    ),
                    'system_prompt': "És um professor de nível universitário"
                }
            })

    def get_last_gift_file(self) -> Optional[str]:
        """Retorna o último ficheiro GIFT usado."""
        prefs = self._read_preferences()
        last_file = prefs.get('last_gift_file', '')

        # Verifica se o ficheiro ainda existe
        if last_file and Path(last_file).exists():
            return last_file
        return None

    def set_last_gift_file(self, filepath: str):
        """Guarda o último ficheiro GIFT usado."""
        prefs = self._read_preferences()
        prefs['last_gift_file'] = filepath
        self._write_preferences(prefs)

    def get_theme(self) -> str:
        """Retorna o tema preferido."""
        prefs = self._read_preferences()
        return prefs.get('theme', 'default')

    def set_theme(self, theme: str):
        """Guarda o tema preferido."""
        prefs = self._read_preferences()
        prefs['theme'] = theme
        self._write_preferences(prefs)

    # ---- LLM settings ----
    def get_llm_provider(self) -> str:
        prefs = self._read_preferences()
        return prefs.get('llm', {}).get('provider', 'groq')

    def set_llm_provider(self, provider: str):
        prefs = self._read_preferences()
        prefs.setdefault('llm', {})['provider'] = provider
        self._write_preferences(prefs)

    def get_llm_api_key(self, provider: str) -> str:
        prefs = self._read_preferences()
        return prefs.get('llm', {}).get('api_keys', {}).get(provider, '')

    def set_llm_api_key(self, provider: str, key: str):
        prefs = self._read_preferences()
        llm = prefs.setdefault('llm', {})
        llm.setdefault('api_keys', {})[provider] = key
        self._write_preferences(prefs)

    def get_llm_model(self, provider: str) -> str:
        prefs = self._read_preferences()
        return prefs.get('llm', {}).get('models', {}).get(provider, '')

    def set_llm_model(self, provider: str, model: str):
        prefs = self._read_preferences()
        llm = prefs.setdefault('llm', {})
        llm.setdefault('models', {})[provider] = model
        self._write_preferences(prefs)

    def get_llm_prompt_template(self) -> str:
        prefs = self._read_preferences()
        default = (
            "Por favor explica, com rigor, a resposta certa e "
            "as respostas erradas da pergunta em baixo."
        )
        return prefs.get('llm', {}).get('prompt_template', default)

    def set_llm_prompt_template(self, template: str):
        prefs = self._read_preferences()
        prefs.setdefault('llm', {})['prompt_template'] = template
        self._write_preferences(prefs)

    def get_llm_system_prompt(self) -> str:
        prefs = self._read_preferences()
        return prefs.get('llm', {}).get('system_prompt', "És um professor de nível universitário")

    def set_llm_system_prompt(self, prompt: str):
        prefs = self._read_preferences()
        prefs.setdefault('llm', {})['system_prompt'] = prompt
        self._write_preferences(prefs)

    # ---- UI settings ----
    def get_main_window_size_percent(self):
        """Retorna (width%, height%) da janela principal com validação."""
        prefs = self._read_preferences()
        ui = prefs.get('ui', {})
        width = ui.get('main_window_width_percent', DEFAULT_WINDOW_PERCENT)
        height = ui.get('main_window_height_percent', DEFAULT_WINDOW_PERCENT)
        # Validar limites
        if not isinstance(width, int) or width < MIN_WINDOW_PERCENT or width > MAX_WINDOW_PERCENT:
            width = DEFAULT_WINDOW_PERCENT
        if not isinstance(height, int) or height < MIN_WINDOW_PERCENT or height > MAX_WINDOW_PERCENT:
            height = DEFAULT_WINDOW_PERCENT
        return (width, height)

    def set_main_window_size_percent(self, width_percent: int, height_percent: int):
        """Guarda tamanho da janela principal em percentagem do ecrã."""
        prefs = self._read_preferences()
        ui = prefs.setdefault('ui', {})
        ui['main_window_width_percent'] = width_percent
        ui['main_window_height_percent'] = height_percent
        self._write_preferences(prefs)

    def get_explanation_window_size_percent(self):
        """Retorna (width%, height%) da janela de explicação com validação."""
        prefs = self._read_preferences()
        ui = prefs.get('ui', {})
        width = ui.get('explanation_width_percent', DEFAULT_WINDOW_PERCENT)
        height = ui.get('explanation_height_percent', DEFAULT_WINDOW_PERCENT)
        # Validar limites
        if not isinstance(width, int) or width < MIN_WINDOW_PERCENT or width > MAX_WINDOW_PERCENT:
            width = DEFAULT_WINDOW_PERCENT
        if not isinstance(height, int) or height < MIN_WINDOW_PERCENT or height > MAX_WINDOW_PERCENT:
            height = DEFAULT_WINDOW_PERCENT
        return (width, height)

    def set_explanation_window_size_percent(self, width_percent: int, height_percent: int):
        """Guarda tamanho da janela de explicação em percentagem do parent."""
        prefs = self._read_preferences()
        ui = prefs.setdefault('ui', {})
        ui['explanation_width_percent'] = width_percent
        ui['explanation_height_percent'] = height_percent
        self._write_preferences(prefs)

    def get_explanation_links_behavior(self) -> str:
        """Retorna 'browser' ou 'internal'."""
        prefs = self._read_preferences()
        return prefs.get('ui', {}).get('explanation_links_behavior', 'browser')

    def set_explanation_links_behavior(self, behavior: str):
        """Define comportamento de links: 'browser' ou 'internal'."""
        prefs = self._read_preferences()
        prefs.setdefault('ui', {})['explanation_links_behavior'] = behavior
        self._write_preferences(prefs)

    def get_html_renderer(self) -> str:
        """Retorna 'webengine' ou 'textbrowser'."""
        prefs = self._read_preferences()
        return prefs.get('ui', {}).get('html_renderer', 'webengine')

    def set_html_renderer(self, renderer: str):
        """Define renderizador HTML: 'webengine' ou 'textbrowser'."""
        prefs = self._read_preferences()
        prefs.setdefault('ui', {})['html_renderer'] = renderer
        self._write_preferences(prefs)

    def get_quick_test_questions(self):
        """Retorna o número de perguntas para o teste rápido com validação."""
        prefs = self._read_preferences()
        count = prefs.get('ui', {}).get('quick_test_questions', DEFAULT_QUICK_TEST_QUESTIONS)
        # Validar limites
        if not isinstance(count, int) or count < MIN_QUICK_TEST_QUESTIONS or count > MAX_QUICK_TEST_QUESTIONS:
            count = DEFAULT_QUICK_TEST_QUESTIONS
        return count

    def set_quick_test_questions(self, count: int):
        """Guarda o número de perguntas para o teste rápido."""
        prefs = self._read_preferences()
        prefs.setdefault('ui', {})['quick_test_questions'] = count
        self._write_preferences(prefs)

    def _read_preferences(self) -> dict:
        """Lê as preferências do ficheiro."""
        try:
            with open(self.pref_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def _write_preferences(self, prefs: dict):
        """Guarda as preferências no ficheiro."""
        with open(self.pref_file, 'w', encoding='utf-8') as f:
            json.dump(prefs, f, ensure_ascii=False, indent=2)
