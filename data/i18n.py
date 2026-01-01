"""
Internacionalização (i18n) para a aplicação Gift Test Practice.
Suporta Português e Inglês.
"""

import json
from pathlib import Path
from PySide6.QtCore import QLocale

_current_language = None
_translations = {}
_pt_to_en_mapping = None


def _load_pt_to_en_mapping():
    """Carrega o mapeamento reverso PT->EN para traduzir strings hardcoded."""
    global _pt_to_en_mapping
    
    if _pt_to_en_mapping is not None:
        return _pt_to_en_mapping
    
    translations_dir = Path(__file__).parent.parent / 'translations'
    mapping_file = translations_dir / 'pt_to_en.json'
    
    if mapping_file.exists():
        try:
            with open(mapping_file, 'r', encoding='utf-8') as f:
                _pt_to_en_mapping = json.load(f)
        except Exception:
            _pt_to_en_mapping = {}
    else:
        _pt_to_en_mapping = {}
    
    return _pt_to_en_mapping


def get_default_language():
    """Detecta a língua do sistema e retorna 'pt' ou 'en'."""
    system_locale = QLocale.system()
    
    # Usar o locale name (ex: "pt_PT", "en_GB") como forma mais robusta
    locale_name = system_locale.name()
    
    # Se começa com 'pt', é português
    if locale_name.startswith('pt'):
        return 'pt'
    else:
        # Qualquer outra língua retorna 'en'
        return 'en'


def _load_translations(language):
    """Carrega o dicionário de traduções de um ficheiro JSON."""
    translations_dir = Path(__file__).parent.parent / 'translations'
    json_file = translations_dir / f'gift_test_{language}.qm'  # Armazenado como JSON
    
    if json_file.exists():
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def initialize_translator(app, language=None):
    """Inicializa o tradutor para a aplicação.
    
    Args:
        app: Instância de QApplication
        language: Código da língua ('pt' ou 'en'). Se None, detecta automaticamente.
    """
    global _current_language, _translations
    
    if language is None:
        language = get_default_language()
    
    _current_language = language
    _translations = _load_translations(language)
    
    return language


def change_language(app, language):
    """Muda a língua da aplicação.
    
    Args:
        app: Instância de QApplication
        language: Código da língua ('pt' ou 'en')
    """
    global _current_language, _translations
    
    if _current_language == language:
        return
    
    _current_language = language
    _translations = _load_translations(language)


def get_current_language():
    """Retorna a língua actual."""
    return _current_language or get_default_language()


def translate(context, message):
    """Traduz uma mensagem.
    
    Args:
        context: Contexto da tradução (nome da classe/arquivo)
        message: Mensagem a traduzir
    
    Returns:
        A mensagem traduzida, ou a mensagem original se tradução não existir.
    """
    # Se estamos em inglês, verificar se a mensagem é um string português hardcoded
    if _current_language == 'en':
        pt_to_en = _load_pt_to_en_mapping()
        if message in pt_to_en:
            return pt_to_en[message]
    
    # Caso normal: procurar na tabela de traduções
    if message in _translations:
        return _translations[message]
    
    return message


def tr(message):
    """Atalho para traduzir uma mensagem."""
    return translate(None, message)


def translate_qt_object(obj):
    """Traduz automaticamente um objeto Qt (QLabel, QPushButton, etc.)."""
    if obj is None:
        return
    
    # Se tem texto, tenta traduzir
    if hasattr(obj, 'text'):
        text = obj.text()
        if text:
            translated = translate(None, text)
            if translated != text:
                obj.setText(translated)
    
    # Se tem placeholder text (QLineEdit)
    if hasattr(obj, 'placeholderText'):
        placeholder = obj.placeholderText()
        if placeholder:
            translated = translate(None, placeholder)
            if translated != placeholder:
                obj.setPlaceholderText(translated)
    
    # Se é um QGroupBox, traduzir o title
    if hasattr(obj, 'title'):
        title = obj.title()
        if title:
            translated = translate(None, title)
            if translated != title:
                obj.setTitle(translated)

