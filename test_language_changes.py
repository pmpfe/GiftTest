#!/usr/bin/env python3
"""
Script de teste para verificar a funcionalidade de mudança de linguagem
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from data.preferences import Preferences
from data.i18n import initialize_translator, get_default_language, tr

def test_preferences():
    """Testa o sistema de preferências"""
    print("=" * 60)
    print("TESTE 1: Verificar preferências de linguagem")
    print("=" * 60)
    
    prefs = Preferences()
    
    # Teste 1: Get language
    language = prefs.get_language()
    print(f"✓ Linguagem configurada: {language}")
    assert language == 'pt', "A linguagem deve ser 'pt' por padrão"
    
    # Teste 2: Set language
    prefs.set_language('en')
    language = prefs.get_language()
    print(f"✓ Linguagem alterada para: {language}")
    assert language == 'en', "A linguagem deve ser 'en' após a alteração"
    
    # Restaurar para português
    prefs.set_language('pt')
    print(f"✓ Linguagem restaurada para: {prefs.get_language()}")
    
    print("\n✓ Todos os testes de preferências passaram!\n")


def test_i18n():
    """Testa o sistema de internacionalização"""
    print("=" * 60)
    print("TESTE 2: Verificar sistema de internacionalização")
    print("=" * 60)
    
    # Teste 1: Get default language
    default_lang = get_default_language()
    print(f"✓ Linguagem padrão do sistema: {default_lang}")
    
    # Teste 2: Initialize translator
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    
    # Inicializar com português
    lang = initialize_translator(app, 'pt')
    print(f"✓ Tradutor inicializado com: {lang}")
    
    # Teste 3: Tradução de strings
    texto_settings = tr("Settings")
    print(f"✓ Texto traduzido 'Settings': {texto_settings}")
    
    print("\n✓ Todos os testes de i18n passaram!\n")


def test_settings_screen_method():
    """Verifica se o método de mudança de linguagem existe"""
    print("=" * 60)
    print("TESTE 3: Verificar método de mudança de linguagem")
    print("=" * 60)
    
    from data.settings_screen import SettingsScreen
    
    # Verificar se o método existe
    assert hasattr(SettingsScreen, '_change_language_with_restart'), \
        "O método _change_language_with_restart não existe"
    print("✓ Método _change_language_with_restart existe")
    
    # Verificar a assinatura
    import inspect
    sig = inspect.signature(SettingsScreen._change_language_with_restart)
    params = list(sig.parameters.keys())
    print(f"✓ Parâmetros do método: {params}")
    assert 'self' in params and 'language_code' in params, \
        "O método não tem os parâmetros esperados"
    
    print("\n✓ Todos os testes de settings screen passaram!\n")


if __name__ == "__main__":
    try:
        test_preferences()
        test_i18n()
        test_settings_screen_method()
        print("=" * 60)
        print("✓ TODOS OS TESTES PASSARAM COM SUCESSO!")
        print("=" * 60)
    except Exception as e:
        print(f"\n✗ ERRO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
