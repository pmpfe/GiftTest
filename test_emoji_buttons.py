#!/usr/bin/env python3
"""
Script de teste visual para os botões com emojis de bandeira
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton
from PySide6.QtCore import Qt

def test_emoji_buttons():
    """Teste visual dos botões com emojis"""
    app = QApplication(sys.argv)
    
    window = QMainWindow()
    window.setWindowTitle("Teste de Emojis de Bandeira")
    window.setGeometry(100, 100, 400, 200)
    
    central = QWidget()
    layout = QVBoxLayout(central)
    
    # Label de info
    from PySide6.QtWidgets import QLabel
    info = QLabel("Clique nos botões abaixo para testar os emojis de bandeira:")
    layout.addWidget(info)
    
    # Botão de Português com emoji
    btn_pt = QPushButton("🇵🇹 Português")
    font_pt = btn_pt.font()
    font_pt.setPointSize(14)
    btn_pt.setFont(font_pt)
    btn_pt.setMinimumHeight(50)
    btn_pt.setToolTip("Clique para mudar para Português")
    layout.addWidget(btn_pt)
    
    # Botão de English com emoji
    btn_en = QPushButton("🇬🇧 English")
    font_en = btn_en.font()
    font_en.setPointSize(14)
    btn_en.setFont(font_en)
    btn_en.setMinimumHeight(50)
    btn_en.setToolTip("Click to change to English")
    layout.addWidget(btn_en)
    
    # Info adicional
    info2 = QLabel("\n✓ Se vir as bandeiras ao lado do texto, os emojis funcionam!")
    layout.addWidget(info2)
    
    layout.addStretch()
    
    window.setCentralWidget(central)
    window.show()
    
    print("Janela de teste aberta. Se vir os emojis 🇵🇹 e 🇬🇧, está tudo bem!")
    print("Feche a janela para terminar o teste.")
    
    sys.exit(app.exec())

if __name__ == "__main__":
    test_emoji_buttons()
