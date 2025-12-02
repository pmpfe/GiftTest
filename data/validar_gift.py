#!/usr/bin/env python3
"""
Validador de ficheiro GIFT - verifica a sintaxe e gera estatísticas.
"""

import re
from collections import defaultdict


def validate_gift_file(filepath):
    """Valida um ficheiro GIFT e retorna estatísticas."""

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    stats = {
        'total_questions': 0,
        'categories': defaultdict(int),
        'questions_with_errors': [],
        'questions_with_multiple_correct': [],
        'questions_with_no_correct': [],
        'questions_needing_review': []
    }

    # Identifica categorias
    categories = re.findall(r'\$CATEGORY: (.+)', content)
    current_category = None

    # Separa as questões
    questions = re.findall(r'::(Questão \d+)::(.+?)\n\}', content, re.DOTALL)

    for title, question_body in questions:
        stats['total_questions'] += 1

        # Extrai número da questão
        q_num_match = re.search(r'Questão (\d+)', title)
        q_num = q_num_match.group(1) if q_num_match else '?'

        # Conta respostas corretas (=) e incorretas (~)
        correct_answers = len(re.findall(r'\n\s*=', question_body))
        incorrect_answers = len(re.findall(r'\n\s*~', question_body))

        # Verifica problemas
        if correct_answers == 0:
            stats['questions_with_no_correct'].append(q_num)
        elif correct_answers > 1:
            stats['questions_with_multiple_correct'].append(q_num)

        # Total de opções
        total_options = correct_answers + incorrect_answers
        if total_options < 2:
            stats['questions_with_errors'].append(q_num)

    # Identifica questões marcadas para revisão
    review_pattern = r'// ATENÇÃO: Questão (\d+) precisa de revisão'
    stats['questions_needing_review'] = re.findall(review_pattern, content)

    # Conta questões por categoria
    current_cat = None
    for line in content.split('\n'):
        if line.startswith('$CATEGORY:'):
            current_cat = line.replace('$CATEGORY:', '').strip()
        elif line.startswith('::Questão'):
            if current_cat:
                stats['categories'][current_cat] += 1

    return stats


def print_report(stats):
    """Imprime um relatório de validação."""

    print("\n" + "="*80)
    print("RELATÓRIO DE VALIDAÇÃO DO FICHEIRO GIFT")
    print("="*80 + "\n")

    print(f"📊 ESTATÍSTICAS GERAIS")
    print(f"   Total de questões: {stats['total_questions']}")
    print(f"   Total de categorias: {len(stats['categories'])}")

    print(f"\n📁 QUESTÕES POR CATEGORIA")
    for cat, count in sorted(stats['categories'].items(), key=lambda x: -x[1]):
        bar = "█" * (count // 5)
        print(f"   {cat:30s} {count:3d} {bar}")

    print(f"\n✅ VALIDAÇÃO")

    errors = len(stats['questions_with_errors'])
    if errors == 0:
        print(f"   ✓ Nenhuma questão com erros de formatação")
    else:
        print(f"   ✗ {errors} questões com erros: {stats['questions_with_errors']}")

    no_correct = len(stats['questions_with_no_correct'])
    if no_correct == 0:
        print(f"   ✓ Todas as questões têm resposta correta")
    else:
        print(f"   ⚠ {no_correct} questões SEM resposta correta: {stats['questions_with_no_correct'][:10]}")

    multiple_correct = len(stats['questions_with_multiple_correct'])
    if multiple_correct == 0:
        print(f"   ✓ Nenhuma questão com múltiplas respostas corretas")
    else:
        print(f"   ⚠ {multiple_correct} questões com MÚLTIPLAS respostas corretas: {stats['questions_with_multiple_correct'][:10]}")

    needs_review = len(stats['questions_needing_review'])
    if needs_review == 0:
        print(f"   ✓ Nenhuma questão precisa de revisão")
    else:
        print(f"   ⚠ {needs_review} questões precisam de revisão: {', '.join(stats['questions_needing_review'])}")

    print(f"\n📈 TAXA DE SUCESSO")
    if stats['total_questions'] > 0:
        valid_questions = (
            stats['total_questions'] - no_correct - multiple_correct
        )
        success_rate = (valid_questions / stats['total_questions'] * 100)
    else:
        success_rate = 0
    print(f"   {success_rate:.1f}% das questões estão corretas")

    print("\n" + "="*80)

    # Resumo final
    if no_correct == 0 and multiple_correct == 0 and errors == 0:
        print("✓ FICHEIRO VÁLIDO E PRONTO PARA IMPORTAR NO MOODLE!")
    else:
        print("⚠ FICHEIRO PRECISA DE CORREÇÕES ANTES DE IMPORTAR")
        print("\nRecomendações:")
        if needs_review > 0:
            print(f"  1. Execute: python revisar_questoes.py")
        if multiple_correct > 0:
            print(f"  2. Corrija questões com múltiplas respostas corretas")
        if no_correct > 0:
            print(f"  3. Adicione resposta correta às questões sem resposta")

    print("="*80 + "\n")


def main():
    gift_file = "data/literatura-classica-50.gift.txt"

    print("\nValidando ficheiro GIFT...\n")

    try:
        stats = validate_gift_file(gift_file)
        print_report(stats)

    except FileNotFoundError:
        print(f"❌ Erro: Ficheiro '{gift_file}' não encontrado!")

    except Exception as e:
        print(f"❌ Erro ao validar ficheiro: {e}")


if __name__ == "__main__":
    main()
