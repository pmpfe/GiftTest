"""
Parser simples para ficheiros GIFT.
Extrai perguntas, categorias e opções de resposta.
"""

import re
from typing import List, Dict, Optional


class Question:
    """Representa uma pergunta do ficheiro GIFT."""
    
    def __init__(self, number: str, text: str, options: List[Dict], category: str = None):
        self.number = number
        self.text = text
        self.options = options  # Lista de {'text': str, 'is_correct': bool}
        self.category = category
    
    def get_correct_answer(self) -> Optional[int]:
        """Retorna o índice da resposta correta."""
        for i, opt in enumerate(self.options):
            if opt['is_correct']:
                return i
        return None
    
    def __repr__(self):
        return f"Question({self.number}, {self.category}, {len(self.options)} options)"


class GiftParser:
    """Parser para ficheiros GIFT."""
    
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.questions = []
        self.categories = {}
        self._parse()
    
    def _unescape_gift(self, text: str) -> str:
        """Remove escapes do formato GIFT."""
        text = text.replace('\\~', '~')
        text = text.replace('\\=', '=')
        text = text.replace('\\#', '#')
        text = text.replace('\\{', '{')
        text = text.replace('\\}', '}')
        text = text.replace('\\:', ':')
        text = text.replace('\\\\', '\\')
        return text
    
    def _parse(self):
        """Faz parse do ficheiro GIFT."""
        with open(self.filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Identifica categorias
        current_category = None
        
        # Divide por linhas para processar
        lines = content.split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            
            # Identifica categoria
            if line.startswith('$CATEGORY:'):
                current_category = line.replace('$CATEGORY:', '').strip()
                if current_category not in self.categories:
                    self.categories[current_category] = []
                i += 1
                continue
            
            # Identifica início de questão
            if line.startswith('::'):
                # Extrai nome da questão e possível tag
                match = re.match(r'::(.+?)::(.*)', line)
                if match:
                    q_number_full = match.group(1).strip()
                    remainder = match.group(2).strip()
                    
                    # Verifica se há tag no q_number_full
                    tag_match = re.search(r'\[tags:\s*topico="([^"]+)"\]', q_number_full)
                    if tag_match:
                        current_category = tag_match.group(1)
                        if current_category not in self.categories:
                            self.categories[current_category] = []
                        # Remove a tag do q_number
                        q_number = re.sub(r'\s*\[tags:[^\]]+\]', '', q_number_full).strip()
                    else:
                        q_number = q_number_full
                    
                    # Coleta o texto da pergunta até {
                    if remainder and '{' in remainder:
                        # Pergunta na mesma linha
                        q_text = remainder.replace('{', '').strip()
                        # i já está na linha, não incrementa
                    else:
                        # Pergunta em linhas separadas
                        q_text_lines = [remainder] if remainder else []
                        i += 1
                        
                        while i < len(lines):
                            q_line = lines[i].strip()
                            if q_line == '{':
                                break
                            q_text_lines.append(q_line)
                            i += 1
                        
                        q_text = '\n'.join(q_text_lines).strip()
                    
                    q_text = self._unescape_gift(q_text)
                    
                    # Extrai opções
                    options = []
                    
                    while i < len(lines):
                        opt_line = lines[i].strip()
                        
                        # Fim da questão
                        if opt_line == '}':
                            break
                        
                        # Opção correta
                        if opt_line.startswith('='):
                            opt_text = self._unescape_gift(opt_line[1:].strip())
                            options.append({'text': opt_text, 'is_correct': True})
                        # Opção incorreta
                        elif opt_line.startswith('~'):
                            opt_text = self._unescape_gift(opt_line[1:].strip())
                            options.append({'text': opt_text, 'is_correct': False})
                        
                        i += 1
                    
                    # Cria a questão
                    question = Question(q_number, q_text, options, current_category)
                    self.questions.append(question)
                    
                    # Adiciona à categoria
                    if current_category:
                        self.categories[current_category].append(question)
            
            i += 1
    
    def get_categories(self) -> List[str]:
        """Retorna lista de categorias disponíveis."""
        return sorted(self.categories.keys())
    
    def get_questions_by_category(self, category: str) -> List[Question]:
        """Retorna todas as questões de uma categoria."""
        return self.categories.get(category, [])
    
    def get_all_questions(self) -> List[Question]:
        """Retorna todas as questões."""
        return self.questions
