import os
import time
import re
import argparse
import sys
import json
import csv
from typing import List, Dict, Any

# Adicionar o diretório pai ao sys.path para encontrar os módulos data
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from data.llm_client import LLMClient, LLMError
from data.preferences import Preferences

# ==========================
# CONSTANTES E CONFIGURAÇÕES GLOBAIS
# ==========================
DEFAULT_BATCH_SIZE = 10
DEFAULT_SLEEP_SECONDS = 5
DEFAULT_MAX_RETRIES = 3
DEFAULT_INITIAL_SLEEP = 10

# ==========================
# PARSER GIFT (para modo "generate")
# ==========================
GIFT_CATEGORY_RE = re.compile(r'^$CATEGORY:\s*(?:name=)?(?P<cat>.+)$')
GIFT_QUESTION_RE = re.compile(r'^(?P<name>::[^:]+::)?(?P<text>.+?)\s*\{(?P<answers>.*)\}\s*$', re.DOTALL)

def parse_gift_file(path: str) -> List[Dict[str, Any]]:
    questions = []
    current_category = "default"
    question_id = 1
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"Erro: Ficheiro de entrada não encontrado em '{path}'")
        sys.exit(1)

    block_buffer = []
    for line in lines:
        stripped_line = line.strip()

        if not stripped_line:
            if block_buffer:
                block_content = "\n".join(block_buffer)
                
                cat_match = GIFT_CATEGORY_RE.match(block_content)
                if cat_match:
                    current_category = cat_match.group("cat").strip()
                else:
                    q_match = GIFT_QUESTION_RE.search(block_content)
                    if q_match:
                        q_text = q_match.group("text").strip()
                        answers_block = q_match.group("answers").strip()
                        raw_answers = re.findall(r'([=~])([^=~]*)', answers_block)
                        alternativas = []
                        for sign, text in raw_answers:
                            ans_text = text.strip().split('#')[0].strip()
                            if ans_text:
                                alternativas.append({"texto": ans_text, "correta": sign == '='})

                        if alternativas and any(a['correta'] for a in alternativas):
                            questions.append({
                                "id": question_id, "categoria": current_category,
                                "texto": q_text, "alternativas": alternativas
                            })
                            question_id += 1
                block_buffer = []
        elif not stripped_line.startswith("//"):
            block_buffer.append(stripped_line)

    if block_buffer:
        block_content = "\n".join(block_buffer)
        q_match = GIFT_QUESTION_RE.search(block_content)
        if q_match:
            q_text = q_match.group("text").strip()
            answers_block = q_match.group("answers").strip()
            raw_answers = re.findall(r'([=~])([^=~]*)', answers_block)
            alternativas = []
            for sign, text in raw_answers:
                ans_text = text.strip().split('#')[0].strip()
                if ans_text:
                    alternativas.append({"texto": ans_text, "correta": sign == '='})
            if alternativas and any(a['correta'] for a in alternativas):
                questions.append({
                    "id": question_id, "categoria": current_category,
                    "texto": q_text, "alternativas": alternativas
                })
                question_id += 1
    return questions

# ==========================
# PROCESSAMENTO DE LOTES COM RETENTATIVAS
# ==========================
def process_batch_with_retries(llm_client: LLMClient, batch_prompt: str, max_retries: int, initial_sleep: int, parse_func: callable) -> List[Dict[str, Any]]:
    """
    Tenta processar um lote, com um número de retentativas e espera exponencial em caso de falha.
    Aceita uma função de parsing para o output do LLM.
    """
    for attempt in range(max_retries):
        try:
            print(f" (Tentativa {attempt + 1}/{max_retries})...", end="", flush=True)
            output_text = llm_client.generate(batch_prompt)
            if not output_text or not output_text.strip():
                raise LLMError("Resposta do modelo estava vazia.")
            
            parsed = parse_func(output_text) # Usa a função de parsing passada como argumento

            if not parsed:
                print("\n[DEBUG] A resposta do modelo não pôde ser analisada ou estava vazia.")
                print("==================== RESPOSTA BRUTA DO MODELO ====================")
                print(output_text)
                print("==================================================================")
                raise LLMError("Resposta do modelo inválida ou vazia após parsing.")

            print(" Sucesso.")
            return parsed
        except LLMError as e:
            print(f" Erro: {e}")
            if attempt < max_retries - 1:
                sleep_time = initial_sleep * (2 ** attempt)
                print(f"A aguardar {sleep_time} segundos antes de tentar novamente...")
                time.sleep(sleep_time)
            else:
                print(f"[ERRO FATAL] O lote falhou após {max_retries} tentativas.")
                return ""
    return ""

# ==========================
# LÓGICA DO MODO "GENERATE"
# ==========================
GENERATE_SYSTEM_PROMPT = (
    "És um assistente que converte perguntas de escolha múltipla em frases do tipo verdadeiro/falso, em português de Portugal.\n"
    "Para cada pergunta recebida, e para cada alternativa, deves:\n"
    "- Gerar uma frase declarativa completa que avalie a veracidade da alternativa no contexto da pergunta.\n"
    "- Indicar se essa frase é VERDADEIRO ou FALSO.\n"
    "- Se a frase for FALSA, deves fornecer a frase correta correspondente.\n"
    "REGRA CRÍTICA: Para cada pergunta original, o conjunto de frases geradas TEM DE CONTER exatamente uma frase verdadeira e as restantes falsas, OU exatamente uma frase falsa e as restantes verdadeiras.\n"
    "Formato de saída estrito (usa '|' como separador):\n"
    "ID_PERGUNTA | TEXTO_DA_ALTERNATIVA | FRASE_GERADA | V/F | FRASE_CORRETA (se aplicável)\n"
    "Não produzas nenhum texto adicional fora deste formato."
)
GENERATE_FEW_SHOT = """
EXEMPLO 1:
PERGUNTA 1 (categoria: Anatomia):
Texto: Qual destes músculos não pertence ao manguito rotador?
Alternativas:
- Redondo Maior
- Redondo Menor
- Supra-espinhoso
- Infra-espinhoso

SAÍDA:
1 | Redondo Maior | O músculo Redondo Maior não pertence ao manguito rotador. | V |
1 | Redondo Menor | O músculo Redondo Menor não pertence ao manguito rotador. | F | O músculo Redondo Menor pertence ao manguito rotador.
1 | Supra-espinhoso | O músculo Supra-espinhoso não pertence ao manguito rotador. | F | O músculo Supra-espinhoso pertence ao manguito rotador.
1 | Infra-espinhoso | O músculo Infra-espinhoso não pertence ao manguito rotador. | F | O músculo Infra-espinhoso pertence ao manguito rotador.
"""

def build_generate_prompt(batch: List[Dict[str, Any]]) -> str:
    parts = ["EXEMPLO:", GENERATE_FEW_SHOT, "\nAGORA TRANSFORMA AS SEGUINTES PERGUNTAS:\n"]
    for q in batch:
        parts.append(f"PERGUNTA {q['id']} (categoria: {q['categoria']}):")
        parts.append(f"Texto: {q['texto']}")
        parts.append("Alternativas:")
        for alt in q["alternativas"]:
            parts.append(f"- {alt['texto']}")
        parts.append("")
    return "\n".join(parts)

def parse_generate_output(text: str) -> List[Dict[str, Any]]:
    results = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.lower().startswith(("saída:", "pergunta")):
            continue
        parts = [p.strip() for p in line.split('|')]
        if len(parts) < 4: continue
        try:
            qid = int(parts[0])
            vf = parts[3].upper()
            if vf not in ("V", "F"): continue
            correct_sentence = parts[4] if vf == "F" and len(parts) > 4 else ""
            results.append({"id": qid, "frase": parts[2], "vf": vf, "correcta": correct_sentence})
        except (ValueError, IndexError):
            continue
    return results

def run_generate_mode(args: argparse.Namespace, llm_client: LLMClient):
    llm_client.system_prompt = GENERATE_SYSTEM_PROMPT # Define o system_prompt aqui

    all_questions = parse_gift_file(args.input_file)
    print(f"Lidas {len(all_questions)} perguntas no total do ficheiro '{args.input_file}'.")

    progress_file = "generate_progress.json"
    processed_ids = set()
    try:
        if os.path.exists(progress_file):
            with open(progress_file, "r", encoding="utf-8") as pf:
                progress_data = json.load(pf)
                if progress_data.get("output_file") == args.output_file:
                    processed_ids = set(progress_data.get("processed_question_ids", []))
                    print(f"Retomando trabalho. {len(processed_ids)} perguntas já foram processadas.")
    except (IOError, json.JSONDecodeError) as e:
        print(f"Aviso: Não foi possível ler o ficheiro de progresso '{progress_file}': {e}. A começar do início.")
    
    questions_to_process = [q for q in all_questions if q["id"] not in processed_ids]
    if not questions_to_process:
        print("Todas as perguntas já foram processadas.")
        if os.path.exists(progress_file): os.remove(progress_file)
        return

    print(f"Perguntas a processar nesta sessão: {len(questions_to_process)}")
    id_to_cat = {q["id"]: q["categoria"] for q in all_questions}

    try:
        with open(args.output_file, "a", encoding="utf-8") as f:
            if f.tell() == 0:
                f.write("Categoria\tID Pergunta\tFrase Gerada\tV/F\tFrase Correcta\n")
                f.flush()

            total_to_process = len(questions_to_process)
            for i in range(0, total_to_process, args.batch_size):
                batch = questions_to_process[i:i + args.batch_size]
                num_processed_total = len(processed_ids)
                print(f"\nA processar lote de {len(batch)} perguntas (Total já feito: {num_processed_total} / {len(all_questions)})", end="")
                
                batch_prompt = build_generate_prompt(batch)
                parsed_items = process_batch_with_retries(llm_client, batch_prompt, args.max_retries, args.initial_sleep, parse_generate_output)

                if parsed_items:
                    batch_ids = {item['id'] for item in parsed_items}
                    for item in parsed_items:
                        cat = id_to_cat.get(item["id"], "desconhecida")
                        f.write(f"{cat}\t{item['id']}\t{item['frase']}\t{item['vf']}\t{item['correcta']}\n")
                    f.flush(); os.fsync(f.fileno())

                    processed_ids.update(batch_ids)
                    with open(progress_file, "w", encoding="utf-8") as pf:
                        json.dump({"output_file": args.output_file, "processed_question_ids": list(processed_ids)}, pf, indent=2)
                    print(f"Lote processado e guardado com sucesso.")

                if i + args.batch_size < total_to_process and args.sleep > 0:
                    print(f"A aguardar {args.sleep} segundos...")
                    time.sleep(args.sleep)
    except IOError as e:
        print(f"Erro ao escrever no ficheiro de saída '{args.output_file}': {e}")
        sys.exit(1)

    print(f"\nTrabalho 'generate' concluído. {len(processed_ids)} perguntas processadas no total.")
    if os.path.exists(progress_file): os.remove(progress_file)

# ==========================
# LÓGICA DO MODO "VALIDATE"
# ==========================
VALIDATE_SYSTEM_PROMPT = (
    "És um assistente especialista em anatomia e fisiologia, incumbido de validar a veracidade de afirmações.\n"
    "Para cada linha recebida, que contém uma afirmação e se ela foi marcada como Verdadeira (V) ou Falsa (F), deves:\n"
    "1. Avaliar a correção da afirmação no contexto da pergunta original implícita.\n"
    "2. Avaliar se a etiqueta 'V' ou 'F' está correta.\n"
    "3. Fornecer uma percentagem de confiança na tua avaliação (de 0 a 100).\n"
    "4. Fornecer uma explicação curta (1 frase) para a tua avaliação, incluindo um link de referência (URL) se possível.\n\n"
    "Formato de saída estrito (usa '|' como separador):\n"
    "ID_LINHA | CONFIANÇA_% | EXPLICAÇÃO_CURTA_COM_URL"
)
VALIDATE_FEW_SHOT = """
EXEMPLO:
INPUT:
1 | Sistema Locomotor | 1 | O músculo Redondo Maior não pertence ao manguito rotador. | V | 

SAÍDA:
1 | 100 | A afirmação está correta; o Redondo Maior é um adutor do braço, não fazendo parte do manguito rotador (https://www.kenhub.com/pt/library/anatomia/musculo-redondo-maior).

INPUT:
2 | Sistema Locomotor | 2 | O músculo Redondo Menor não pertence ao manguito rotador. | F | O músculo Redondo Menor pertence ao manguito rotador.

SAÍDA:
2 | 100 | A afirmação original é falsa e a correção está correta; o Redondo Menor é um dos quatro músculos do manguito rotador.
"""

def build_validate_prompt(batch: List[Dict[str, Any]]) -> str:
    parts = ["EXEMPLO:", VALIDATE_FEW_SHOT, "\nAGORA VALIDA AS SEGUINTES AFIRMAÇÕES:\n"]
    for item in batch:
        parts.append(f"INPUT:")
        parts.append(f"{item['id']} | {item['content']}")
        parts.append("")
    return "\n".join(parts)

def parse_validate_output(text: str) -> List[Dict[str, Any]]:
    results = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.lower().startswith(("saída:", "input:")):
            continue
        parts = [p.strip() for p in line.split('|')]
        if len(parts) != 3: continue
        try:
            line_id = int(parts[0])
            confidence = int(parts[1])
            rationale = parts[2]
            results.append({"id": line_id, "confidence": confidence, "rationale": rationale})
        except (ValueError, IndexError):
            continue
    return results

def run_validate_mode(args: argparse.Namespace, llm_client: LLMClient):
    llm_client.system_prompt = VALIDATE_SYSTEM_PROMPT # Define o system_prompt aqui

    try:
        with open(args.input_file, "r", encoding="utf-8") as f:
            # Ignora o cabeçalho ao ler as linhas
            reader = csv.reader(f, delimiter='\t')
            header = next(reader)
            all_lines = [{"id": i+1, "content": "\t".join(row), "data": row} for i, row in enumerate(reader)]
    except FileNotFoundError:
        print(f"Erro: Ficheiro de entrada não encontrado em '{args.input_file}'")
        sys.exit(1)
    except StopIteration:
        print(f"Erro: Ficheiro de entrada '{args.input_file}' está vazio ou não tem cabeçalho.")
        sys.exit(1)

    print(f"Lidas {len(all_lines)} linhas do ficheiro '{args.input_file}'.")

    progress_file = "validate_progress.json"
    processed_ids = set()
    try:
        if os.path.exists(progress_file):
            with open(progress_file, "r", encoding="utf-8") as pf:
                progress_data = json.load(pf)
                if progress_data.get("output_file") == args.output_file:
                    processed_ids = set(progress_data.get("processed_line_ids", []))
                    print(f"Retomando trabalho. {len(processed_ids)} linhas já foram validadas.")
    except (IOError, json.JSONDecodeError) as e:
        print(f"Aviso: Não foi possível ler o ficheiro de progresso '{progress_file}': {e}. A começar do início.")

    lines_to_process = [line for line in all_lines if line["id"] not in processed_ids]
    if not lines_to_process:
        print("Todas as linhas já foram validadas.")
        if os.path.exists(progress_file): os.remove(progress_file)
        return

    print(f"Linhas a validar nesta sessão: {len(lines_to_process)}")
    
    try:
        with open(args.output_file, "a", encoding="utf-8") as f_out:
            writer = csv.writer(f_out, delimiter='\t')
            if f_out.tell() == 0:
                writer.writerow(header + ["Confiança (%)", "Racional"])
                f_out.flush()

            total_to_process = len(lines_to_process)
            for i in range(0, total_to_process, args.batch_size):
                batch = lines_to_process[i:i + args.batch_size]
                num_processed_total = len(processed_ids)
                print(f"\nA validar lote de {len(batch)} linhas (Total já feito: {num_processed_total} / {len(all_lines)})", end="")

                batch_prompt = build_validate_prompt(batch)
                output_text = process_batch_with_retries(llm_client, batch_prompt, args.max_retries, args.initial_sleep, parse_validate_output)
                
                # A função process_batch_with_retries já retorna a lista de dicionários processada
                parsed_items = output_text 
                
                parsed_map = {item['id']: item for item in parsed_items}

                if output_text: # Se houver output para ser parsed
                    batch_ids = []
                    for line_item in batch:
                        line_id = line_item['id']
                        if line_id in parsed_map:
                            validated_data = parsed_map[line_id]
                            writer.writerow(line_item['data'] + [validated_data['confidence'], validated_data['rationale']])
                            batch_ids.append(line_id)
                    
                    f_out.flush(); os.fsync(f_out.fileno())

                    processed_ids.update(batch_ids)
                    with open(progress_file, "w", encoding="utf-8") as pf:
                        json.dump({"output_file": args.output_file, "processed_line_ids": list(processed_ids)}, pf, indent=2)
                    print(f"Lote validado e guardado com sucesso.")

                if i + args.batch_size < total_to_process and args.sleep > 0:
                    print(f"A aguardar {args.sleep} segundos...")
                    time.sleep(args.sleep)

    except IOError as e:
        print(f"Erro ao escrever no ficheiro de saída '{args.output_file}': {e}")
        sys.exit(1)

    print(f"\nTrabalho 'validate' concluído. {len(processed_ids)} linhas validadas no total.")
    if os.path.exists(progress_file): os.remove(progress_file)


# ==========================
# FUNÇÃO PRINCIPAL (MAIN)
# ==========================
def main():
    prefs = Preferences()
    
    parser = argparse.ArgumentParser(description="Converte ou valida perguntas de anatomia.")
    subparsers = parser.add_subparsers(dest="mode", required=True, help="Modo de operação: 'generate' ou 'validate'")

    # --- Argumentos comuns ---
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument("--provider", default=prefs.get_llm_provider(), help=f"Provedor LLM (default: {prefs.get_llm_provider()})")
    parent_parser.add_argument("--model", help="Modelo a usar (sobrescreve o guardado nas preferências).")
    parent_parser.add_argument("--batch_size", type=int, default=DEFAULT_BATCH_SIZE, help=f"Nº de itens por lote (default: {DEFAULT_BATCH_SIZE})")
    parent_parser.add_argument("--sleep", type=int, default=DEFAULT_SLEEP_SECONDS, help=f"Segundos de espera entre lotes (default: {DEFAULT_SLEEP_SECONDS})")
    parent_parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES, help=f"Nº máximo de retentativas por lote (default: {DEFAULT_MAX_RETRIES})")
    parent_parser.add_argument("--initial-sleep", type=int, default=DEFAULT_INITIAL_SLEEP, help=f"Espera inicial antes da primeira retentativa (default: {DEFAULT_INITIAL_SLEEP})")

    # --- Modo Generate ---
    parser_generate = subparsers.add_parser('generate', parents=[parent_parser], help="Gera frases V/F a partir de um ficheiro GIFT.")
    parser_generate.add_argument("input_file", help="Caminho para o ficheiro .gift de entrada.")
    parser_generate.add_argument("output_file", help="Caminho para o ficheiro de texto de saída.")

    # --- Modo Validate ---
    parser_validate = subparsers.add_parser('validate', parents=[parent_parser], help="Valida e avalia um ficheiro de frases geradas.")
    parser_validate.add_argument("input_file", help="Caminho para o ficheiro de frases de entrada.")
    parser_validate.add_argument("output_file", help="Caminho para o ficheiro de frases validadas de saída.")

    args = parser.parse_args()

    # Configuração do cliente LLM
    provider = args.provider
    api_key = prefs.get_llm_api_key(provider)
    model = args.model or prefs.get_llm_model(provider)

    if not api_key:
        print(f"Erro: A API key para '{provider}' não está definida nas preferências (data/preferences.json).")
        sys.exit(1)

    # Criação do cliente LLM
    # O system_prompt é agora definido dentro das funções de modo (run_generate_mode, run_validate_mode)
    # para permitir que o LLMClient seja instanciado uma única vez
    llm_client = LLMClient(provider=provider, api_key=api_key, model=model, system_prompt="") # system_prompt vazio aqui

    # Executa o modo selecionado
    if args.mode == 'generate':
        run_generate_mode(args, llm_client)
    elif args.mode == 'validate':
        run_validate_mode(args, llm_client)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()