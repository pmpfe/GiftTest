#!/usr/bin/env python3
"""
Script para compilar ficheiros de tradução .ts para .qm
"""

import sys
import os
from pathlib import Path
from PySide6.QtCore import QCoreApplication, QTranslator

def compile_translations():
    """Compila os ficheiros .ts para .qm"""
    app = QCoreApplication(sys.argv)
    
    translations_dir = Path(__file__).parent / 'translations'
    
    for ts_file in translations_dir.glob('*.ts'):
        print(f"Compilando {ts_file.name}...")
        
        translator = QTranslator()
        qm_file = ts_file.with_suffix('.qm')
        
        # Para compilar, usamos o método load com um ficheiro de saída
        # Na verdade, precisamos usar a ferramenta Qt lrelease
        # Como alternativa, vamos criar os ficheiros .qm a partir dos .ts
        import subprocess
        try:
            # Tentar usar lrelease se disponível
            result = subprocess.run(['lrelease', str(ts_file), '-qm', str(qm_file)], 
                                  capture_output=True)
            if result.returncode == 0:
                print(f"✓ {qm_file.name} criado com sucesso")
            else:
                print(f"⚠ Erro ao compilar {ts_file.name}")
        except FileNotFoundError:
            print(f"⚠ lrelease não encontrado, tentando método alternativo...")
            # Método alternativo: usar Python para compilar
            try:
                from lxml import etree
                tree = etree.parse(str(ts_file))
                root = tree.getroot()
                
                # Criar ficheiro .qm (será um ficheiro de tradução vazio/básico)
                # Para agora, vamos apenas criar um placeholder
                qm_file.write_bytes(b'QT TRANSLATION FILE\x00')
                print(f"✓ {qm_file.name} criado (placeholder)")
            except Exception as e:
                print(f"✗ Erro: {e}")

if __name__ == '__main__':
    compile_translations()
