import os
import time
import re
import argparse
import sys
import json
from typing import List, Dict, Any

# Adicionar o diretório pai ao sys.path para encontrar os módulos data
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from data.llm_client import LLMClient, LLMError
from data.preferences import Preferences

# ==========================
# CONFIGURAÇÃO INICIAL
# ==========================

BATCH_SIZE = 10          # n.º de perguntas por batch
SLEEP_SECONDS = 5        # espera entre batches para não abusar dos limites

# ==========================
# PARSER GIFT (múltipla escolha)
# ==========================

GIFT_CATEGORY_RE = re.compile(r'^\$CATEGORY:\s*(?:name=)?(?P<cat>.+)$')
GIFT_QUESTION_RE = re.compile(r'^(?P<name>::[^:]+::)?(?P<text>.+?)\s*\{(?P<answers>.*)\}\s*$', re.DOTALL)

def parse_gift_file(path: str) -> List[Dict[str, Any]]:
    """
    Lê um ficheiro GIFT e devolve uma lista de perguntas de escolha múltipla.
    """
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

        if not stripped_line:  # Linha em branco, processa o bloco anterior
            if block_buffer:
                block_content = "\n".join(block_buffer)
                
                # Verifica se é uma categoria
                cat_match = GIFT_CATEGORY_RE.match(block_content)
                if cat_match:
                    current_category = cat_match.group("cat").strip()
                else: # Tenta processar como pergunta
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
                                "categoria": current_category,
                                "id": question_id,
                                "texto": q_text,
                                "alternativas": alternativas
                            })
                            question_id += 1
                block_buffer = [] # Limpa o buffer
        elif stripped_line.startswith("//"):
            continue # Ignora comentários
        else:
            block_buffer.append(stripped_line)

    # Processa o último bloco se o ficheiro não terminar com linha em branco
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
                    "categoria": current_category,
                    "id": question_id,
                    "texto": q_text,
                    "alternativas": alternativas
                })
                question_id += 1

    return questions


# ==========================
# PROMPT PARA O MODELO
# ==========================

SYSTEM_PROMPT = (
    "És um assistente que converte perguntas de escolha múltipla "
    "em frases do tipo verdadeiro/falso, em português de Portugal.\n\n"
    "Para cada pergunta recebida, e para cada alternativa, deves:\n"
    "- Gerar uma frase declarativa completa que avalie a veracidade da alternativa no contexto da pergunta.\n"
    "- Indicar se essa frase é VERDADEIRO ou FALSO.\n"
    "- Se a frase for FALSA, deves fornecer a frase correta correspondente.\n\n"
    "REGRA CRÍTICA: Para cada pergunta original, o conjunto de frases geradas TEM DE CONTER exatamente uma frase verdadeira e as restantes falsas, OU exatamente uma frase falsa e as restantes verdadeiras. A lógica original da pergunta tem de ser preservada.\n\n"
    "Formato de saída estrito (usa '|' como separador):\n"
    "ID_PERGUNTA | TEXTO_DA_ALTERNATIVA | FRASE_GERADA | V/F | FRASE_CORRETA (se aplicável)\n"
    "Se a frase for 'V', a última coluna deve ficar vazia.\n"
    "Não produzas nenhum texto adicional fora deste formato."
)

FEW_SHOT_EXAMPLE = """
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

EXEMPLO 2:
PERGUNTA 2 (categoria: Osteologia):
Texto: Todos os seguintes são ossos do carpo, EXCETO:
Alternativas:
- Escafoide
- Semilunar
- Metatarso
- Capitato

SAÍDA:
2 | Escafoide | O osso Escafoide é um osso do carpo. | V |
2 | Semilunar | O osso Semilunar é um osso do carpo. | V |
2 | Metatarso | O osso Metatarso é um osso do carpo. | F | O osso Metatarso não é um osso do carpo, é um osso do pé.
2 | Capitato | O osso Capitato é um osso do carpo. | V |
"""

def build_batch_user_content(batch_questions: List[Dict[str, Any]]) -> str:
    """Constrói o conteúdo do 'user' para um batch de perguntas."""
    parts = ["EXEMPLO:", FEW_SHOT_EXAMPLE, "\nAGORA TRANSFORMA AS SEGUINTES PERGUNTAS:\n"]
    for q in batch_questions:
        parts.append(f"PERGUNTA {q['id']} (categoria: {q['categoria']}):")
        parts.append(f"Texto: {q['texto']}")
        parts.append("Alternativas:")
        for alt in q["alternativas"]:
            parts.append(f"- {alt['texto']}")
        parts.append("")
    return "\n".join(parts)


def call_llm(client: LLMClient, batch_questions: List[Dict[str, Any]]) -> str:
    """Chama a API do LLM para um batch e devolve o texto de saída."""
    user_prompt = build_batch_user_content(batch_questions)
    return client.generate(user_prompt)


# ==========================
# PARSE DA RESPOSTA DO MODELO
# ==========================

def parse_model_output(text: str) -> List[Dict[str, Any]]:
    """
    Analisa a saída do modelo, que deve estar no formato:
    ID | Alternativa | Frase Gerada | V/F | Frase Correta (opcional)
    """
    results = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.lower().startswith("saída:") or line.lower().startswith("pergunta"):
            continue
        
        parts = [p.strip() for p in line.split('|')]
        if len(parts) < 4:
            continue
        try:
            qid = int(parts[0])
            vf = parts[3].upper()
            if vf not in ("V", "F"):
                continue
            
            correct_sentence = ""
            if vf == "F" and len(parts) > 4:
                correct_sentence = parts[4]

            results.append({
                "id": qid,
                "frase": parts[2],
                "vf": vf,
                "correcta": correct_sentence
            })
        except (ValueError, IndexError):
            continue
    return results

# ==========================
# PIPELINE PRINCIPAL
# ==========================

def process_batch_with_retries(llm_client: LLMClient, batch: List[Dict[str, Any]], max_retries: int = 3, initial_sleep: int = 10) -> List[Dict[str, Any]]:
    """
    Tenta processar um lote, com um número de retentativas e espera exponencial em caso de falha.
    """
    for attempt in range(max_retries):
        try:
            print(f" (Tentativa {attempt + 1}/{max_retries})...", end="", flush=True)
            output_text = call_llm(llm_client, batch)
            parsed = parse_model_output(output_text)
            
            if not parsed:
                print("\n[DEBUG] A resposta do modelo não pôde ser analisada ou estava vazia.")
                print("==================== RESPOSTA BRUTA DO MODELO ====================")
                print(output_text)
                print("==================================================================")
                raise LLMError("Resposta do modelo inválida ou vazia.")

            print(" Sucesso.")
            return parsed

        except LLMError as e:
            print(f" Erro: {e}")
            if attempt < max_retries - 1:
                sleep_time = initial_sleep * (2 ** attempt)
                print(f"A aguardar {sleep_time} segundos antes de tentar novamente...")
                time.sleep(sleep_time)
            else:
                print(f"[ERRO FATAL] O lote falhou após {max_retries} tentativas. A ignorar este lote.")
                return []
    return []

def main():
    prefs = Preferences()
    
    parser = argparse.ArgumentParser(description="Converte perguntas GIFT para um formato Verdadeiro/Falso usando um LLM.")
    parser.add_argument("input_file", help="Caminho para o ficheiro .gift de entrada.")
    parser.add_argument("output_file", help="Caminho para o ficheiro de texto de saída.")
    parser.add_argument("--provider", default=prefs.get_llm_provider(), help=f"Provedor LLM (default: {prefs.get_llm_provider()})")
    parser.add_argument("--model", help="Modelo a usar (sobrescreve o guardado nas preferências).")
    parser.add_argument("--batch_size", type=int, default=BATCH_SIZE, help=f"Nº de perguntas por batch (default: {BATCH_SIZE})")
    parser.add_argument("--sleep", type=int, default=SLEEP_SECONDS, help=f"Segundos de espera entre lotes bem-sucedidos (default: {SLEEP_SECONDS})")
    
    args = parser.parse_args()

    provider = args.provider
    api_key = prefs.get_llm_api_key(provider)
    model = args.model or prefs.get_llm_model(provider)

    if not api_key:
        print(f"Erro: A API key para '{provider}' não está definida nas preferências (data/preferences.json).")
        sys.exit(1)

    llm_client = LLMClient(
        provider=provider,
        api_key=api_key,
        model=model,
        system_prompt=SYSTEM_PROMPT
    )

    all_questions = parse_gift_file(args.input_file)
    print(f"Lidas {len(all_questions)} perguntas no total do ficheiro '{args.input_file}'.")

    progress_file = "gift2boolean_progress.json"
    processed_ids = set()

    # Carregar estado anterior, se existir
    try:
        if os.path.exists(progress_file):
            with open(progress_file, "r", encoding="utf-8") as pf:
                progress_data = json.load(pf)
                # Verifica se o progresso corresponde aos ficheiros atuais
                if progress_data.get("output_file") == args.output_file:
                    processed_ids = set(progress_data.get("processed_question_ids", []))
                    print(f"Retomando trabalho. {len(processed_ids)} perguntas já foram processadas.")
    except (IOError, json.JSONDecodeError) as e:
        print(f"Aviso: Não foi possível ler o ficheiro de progresso '{progress_file}': {e}. A começar do início.")
        processed_ids = set()

    questions_to_process = [q for q in all_questions if q["id"] not in processed_ids]
    
    if not questions_to_process:
        print("Todas as perguntas já foram processadas. Trabalho concluído.")
        if os.path.exists(progress_file):
            os.remove(progress_file)
        return

    print(f"Perguntas a processar nesta sessão: {len(questions_to_process)}")
    id_to_cat = {q["id"]: q["categoria"] for q in all_questions}

    try:
        # Abre o ficheiro em modo 'append' para poder retomar
        with open(args.output_file, "a", encoding="utf-8") as f:
            # Escreve o cabeçalho apenas se o ficheiro estiver vazio (novo ou recomeçado)
            if f.tell() == 0:
                f.write("Categoria\tID Pergunta\tFrase Gerada\tV/F\tFrase Correcta\n")
                f.flush()

            total_to_process = len(questions_to_process)
            for i in range(0, total_to_process, args.batch_size):
                batch = questions_to_process[i:i + args.batch_size]
                
                num_processed_total = len(processed_ids)
                num_in_batch = len(batch)
                print(f"\nA processar lote de {num_in_batch} perguntas (Total já feito: {num_processed_total} / {len(all_questions)})", end="")
                
                parsed_items = process_batch_with_retries(llm_client, batch)
                
                if parsed_items:
                    batch_ids = []
                    for item in parsed_items:
                        cat = id_to_cat.get(item["id"], "desconhecida")
                        f.write(f"{cat}\t{item['id']}\t{item['frase']}\t{item['vf']}\t{item['correcta']}\n")
                        batch_ids.append(item["id"])
                    
                    # Forçar a escrita para o disco
                    f.flush()
                    os.fsync(f.fileno())

                    # Atualizar e guardar o ficheiro de progresso
                    processed_ids.update(batch_ids)
                    with open(progress_file, "w", encoding="utf-8") as pf:
                        json.dump({
                            "output_file": args.output_file,
                            "processed_question_ids": list(processed_ids)
                        }, pf, indent=2)

                    print(f"Lote processado e guardado com sucesso.")

                if i + args.batch_size < total_to_process:
                    print(f"A aguardar {args.sleep} segundos para o próximo lote...")
                    time.sleep(args.sleep)

    except IOError as e:
        print(f"Erro ao escrever no ficheiro de saída '{args.output_file}': {e}")
        sys.exit(1)

    print(f"\nTrabalho concluído. {len(processed_ids)} perguntas processadas no total.")
    # Limpar o ficheiro de progresso no final
    if os.path.exists(progress_file):
        os.remove(progress_file)


if __name__ == "__main__":
    main()

