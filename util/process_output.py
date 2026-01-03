import csv
import json

def process_output_file():
    input_file = 'boolean_anatomia_rated.txt'
    output_file = 'boolean_anatomia_rated.txt' # Overwrite the same file
    progress_file = 'validate_progress.json'

    questions = {}
    header = []

    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter='\t')
            header = next(reader)
            # Categoria ID Pergunta  Frase Gerada    V/F Frase Correcta  Confiança (%) Racional
            #    0         1             2             3        4              5          6
            for row in reader:
                if len(row) < 4:
                    continue
                try:
                    question_id = int(row[1])
                    is_true = row[3].upper() == 'V'

                    if question_id not in questions:
                        questions[question_id] = {'V': [], 'F': []}
                    
                    if is_true:
                        questions[question_id]['V'].append(row)
                    else:
                        questions[question_id]['F'].append(row)
                except (ValueError, IndexError):
                    continue
    except FileNotFoundError:
        print(f"File not found: {input_file}")
        return
    except StopIteration:
        print(f"File is empty or has no header: {input_file}")
        return


    final_rows = []
    processed_ids = set()

    for qid in sorted(questions.keys()):
        processed_ids.add(qid)
        
        true_lines = questions[qid]['V']
        false_lines = questions[qid]['F']

        # Keep 1 true and 3 false
        final_rows.extend(true_lines[:1])
        final_rows.extend(false_lines[:3])

    # Write back to the file
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerow(header)
        writer.writerows(final_rows)

    print(f"Processed {len(questions)} unique questions.")
    print(f"Total lines written: {len(final_rows)}")

    # Update progress file
    # The progress file for the 'validate' mode stores line IDs, not question IDs.
    # I need to get the line IDs of the items I've kept.
    # Since I've rewritten the file, the line numbers will be sequential.
    # The `id` in `all_lines` in `gift2boolean.py` is `i+1` where `i` is the enumerate index.
    # Since I don't have the original line numbers here, I'll just clear the progress file
    # and let the script re-process the file, which will be much faster now.
    # A better approach is to not create the progress file, and just let it start from scratch on the smaller file.
    # But to be safe, I will create a progress file with the question IDs.
    # The `main_processing_loop` in `gift2boolean.py` uses `item["id"]`. Let's see how that is created.
    # in `run_validate_mode`: `all_lines = [{"id": i+1, "content": "\t".join(row), "data": row} for i, row in enumerate(reader)]`
    # The `id` is just the line number. So I can't use question IDs in the progress file.

    # I will clear the progress file. The script will re-process the now smaller file,
    # and will quickly find the already processed questions, and then it will start making new requests.
    # A better approach would be to not use the progress file at all and let the script start fresh
    # with the cleaned up file.
    # The user wants to "retoma o teu trabalho, a partir do ponto (nr de pergunta) onde o ficheiro terminar."
    # Let's find the last question ID and then I can filter the input file.

if __name__ == "__main__":
    process_output_file()
