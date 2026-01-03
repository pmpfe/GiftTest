"""
Gestor de logs para registar resultados dos testes.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict


class TestLogger:
    """Regista resultados dos testes em ficheiro JSON."""

    def __init__(self, log_file: str = "data/test_history.json"):
        from .app_paths import get_test_history_path

        default_legacy = Path("data/test_history.json")
        default_new = get_test_history_path()

        if log_file == str(default_legacy):
            self.log_file = default_legacy if default_legacy.exists() else default_new
        else:
            self.log_file = Path(log_file)

        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        # Cria ficheiro se não existir
        if not self.log_file.exists():
            self.log_file.write_text('[]', encoding='utf-8')

    def log_test(self,
                 gift_file: str,
                 categories: List[str],
                 total_questions: int,
                 correct: int,
                 wrong: int,
                 wrong_question_ids: List[str],
                 details: List[Dict] = None):
        """
        Regista um teste realizado.

        Args:
            gift_file: Caminho do ficheiro GIFT usado
            categories: Lista de categorias selecionadas
            total_questions: Número total de perguntas
            correct: Número de respostas corretas
            wrong: Número de respostas erradas
            wrong_question_ids: IDs das questões erradas
            details: Detalhes opcionais (questão, resposta dada, resposta correta)
        """
        # Lê histórico existente
        history = self._read_history()

        # Cria novo registo
        record = {
            'timestamp': datetime.now().isoformat(),
            'date': datetime.now().strftime('%Y-%m-%d'),
            'time': datetime.now().strftime('%H:%M:%S'),
            'gift_file': gift_file,
            'categories': categories,
            'total_questions': total_questions,
            'correct': correct,
            'wrong': wrong,
            'percentage': round((correct / total_questions * 100) if total_questions > 0 else 0, 2),
            'wrong_question_ids': wrong_question_ids
        }

        if details:
            record['details'] = details

        # Adiciona ao histórico
        history.append(record)

        # Guarda
        self._write_history(history)

        return record

    def _read_history(self) -> List[Dict]:
        """Lê o histórico de testes."""
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _write_history(self, history: List[Dict]):
        """Guarda o histórico de testes."""
        with open(self.log_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

    def get_statistics(self, gift_file: str = None) -> Dict:
        """Retorna estatísticas gerais dos testes.

        Args:
            gift_file: Se especificado, retorna estatísticas apenas desse ficheiro
        """
        history = self._read_history()

        # Filtra por ficheiro se especificado
        if gift_file:
            history = [h for h in history if h.get('gift_file') == gift_file]

        if not history:
            return {
                'total_tests': 0,
                'total_questions': 0,
                'average_score': 0
            }

        total_tests = len(history)
        total_questions = sum(h['total_questions'] for h in history)
        total_correct = sum(h['correct'] for h in history)

        return {
            'total_tests': total_tests,
            'total_questions': total_questions,
            'total_correct': total_correct,
            'average_score': round((total_correct / total_questions * 100) if total_questions > 0 else 0, 2)
        }

    def get_recent_tests(self, limit: int = 10, gift_file: str = None) -> List[Dict]:
        """Retorna os últimos N testes.

        Args:
            limit: Número máximo de testes a retornar
            gift_file: Se especificado, retorna apenas testes desse ficheiro
        """
        history = self._read_history()

        # Filtra por ficheiro se especificado
        if gift_file:
            history = [h for h in history if h.get('gift_file') == gift_file]

        return sorted(history, key=lambda x: x['timestamp'], reverse=True)[:limit]

    def clear_history(self):
        """Limpa todo o histórico de testes."""
        self._write_history([])
