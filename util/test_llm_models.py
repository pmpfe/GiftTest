#!/usr/bin/env python3
"""
Script para testar todos os modelos de todos os providers e gerar relatório HTML.
"""

import argparse
import sys
import time
from pathlib import Path

# Adicionar o diretório pai ao path para importar módulos locais
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# pylint: disable=wrong-import-position
from data.llm_client import LLMClient, LLMError
from data.preferences import Preferences
# pylint: enable=wrong-import-position


def test_all_models(limit_providers=None):
    """Testa todos os modelos de todos os providers."""
    prefs = Preferences()

    # Obter system prompt configurado
    system_prompt = prefs.get_llm_system_prompt()

    # Pergunta de teste
    test_prompt = "Summarize in 3 bullets your functionalities and what makes you stand out as a specific version of a language model compared to others."

    model_results = []

    # Lista de providers suportados
    providers = ["groq", "huggingface", "gemini", "mistral", "perplexity", "openrouter", "cloudflare"]

    # Filtrar providers se especificado
    if limit_providers:
        providers = [p for p in providers if p in limit_providers]

    for provider in providers:
        print(f"Testando provider: {provider}")

        try:
            # Obter chave API
            api_key = prefs.get_llm_api_key(provider)
            if not api_key:
                print(f"  Pulando {provider}: chave API não configurada")
                continue

            # Criar cliente com system prompt
            client = LLMClient(provider, api_key, system_prompt=system_prompt)

            # Obter lista de modelos
            try:
                models = client.list_models()
            except Exception as e:
                print(f"  Erro ao obter modelos para {provider}: {e}")
                continue

            if not models:
                print(f"  Nenhum modelo encontrado para {provider}")
                continue

            # Limitar a primeiros 5 modelos por provider para não demorar muito
            models_to_test = models  # Testar todos os modelos disponíveis

            for model_info in models_to_test:
                model_id = model_info.get('id', '')
                model_desc = model_info.get('description', '')

                print(f"  Testando modelo: {model_id}")

                try:
                    # Criar client com o modelo específico
                    test_client = LLMClient(provider=provider, api_key=api_key, model=model_id)
                    # Medir tempo
                    start_time = time.time()
                    response = test_client.generate(test_prompt)
                    end_time = time.time()

                    response_time = round(end_time - start_time, 2)
                    response_size = len(response)

                    model_results.append({
                        'provider': provider,
                        'model': model_id,
                        'description': model_desc,
                        'response_time': response_time,
                        'response_size': response_size,
                        'response': response,
                        'success': True
                    })

                    print(f"    ✓ Tempo: {response_time}s, Tamanho: {response_size} chars")

                except Exception as e:
                    if isinstance(e, LLMError) and hasattr(e, 'status_code'):
                        error_msg = f"Status Code: {e.status_code}\nHeaders: {e.headers}\nBody: {e.body}"
                    else:
                        error_msg = str(e)
                        # Tentar extrair corpo de erro se disponível
                        if hasattr(e, 'response') and hasattr(e.response, 'text'):
                            error_msg += f"\nCorpo da resposta: {e.response.text}"
                        elif hasattr(e, 'read'):
                            try:
                                error_body = e.read().decode('utf-8')
                                error_msg += f"\nCorpo do erro: {error_body}"
                            except Exception:  # pylint: disable=broad-exception-caught
                                pass
                    print(f"    ✗ Erro no modelo {model_id}: {error_msg}")
                    model_results.append({
                        'provider': provider,
                        'model': model_id,
                        'description': model_desc,
                        'response_time': 0,
                        'response_size': 0,
                        'response': f"Erro: {error_msg}",
                        'success': False
                    })

                # Espera entre testes para evitar rate limiting
                time.sleep(2)

        except Exception as e:
            print(f"Erro geral com provider {provider}: {e}")

    return model_results


def generate_html(results):
    """Gera arquivo HTML com os resultados."""
    test_prompt = (
        "Resume em 3 bullets as tuas funcionalidades, e o que te destaca, "
        "enquanto versão específica de modelo de linguagem, dos outros modelos."
    )

    # Separar resultados
    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]

    # Calcular estatísticas por provider
    stats = {}
    for provider in ["groq", "huggingface", "gemini", "mistral", "perplexity", "openrouter", "cloudflare"]:
        provider_results = [r for r in results if r['provider'] == provider]
        if provider_results:
            success_count = len([r for r in provider_results if r['success']])
            fail_count = len([r for r in provider_results if not r['success']])
            if success_count > 0:
                total_time = sum(
                    r['response_time'] for r in provider_results if r['success']
                )
                avg_time = round(total_time / success_count, 2)
            else:
                avg_time = 0
            stats[provider] = {
                'success': success_count,
                'fail': fail_count,
                'avg_time': avg_time
            }

    html_content = f"""<!DOCTYPE html>
<html lang="pt">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Teste de Modelos LLM</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        h1 {{
            color: #333;
            text-align: center;
        }}
        .summary {{
            background-color: white;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .summary h2 {{
            color: #333;
            margin-top: 0;
        }}
        .summary-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }}
        .summary-table th, .summary-table td {{
            padding: 8px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        .summary-table th {{
            background-color: #f0f0f0;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background-color: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #4CAF50;
            color: white;
        }}
        tr:hover {{
            background-color: #f1f1f1;
        }}
        button {{
            background-color: #4CAF50;
            color: white;
            border: none;
            padding: 8px 12px;
            cursor: pointer;
            border-radius: 4px;
        }}
        button:hover {{
            background-color: #45a049;
        }}
        .error-button {{
            background-color: #f44336;
            color: white;
            border: none;
            padding: 8px 12px;
            cursor: pointer;
            border-radius: 4px;
        }}
        .error-button:hover {{
            background-color: #d32f2f;
        }}
        .modal {{
            display: none;
            position: fixed;
            z-index: 1;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.4);
        }}
        .modal-content {{
            background-color: #fefefe;
            margin: 15% auto;
            padding: 20px;
            border: 1px solid #888;
            width: 80%;
            max-width: 800px;
            border-radius: 8px;
        }}
        .close {{
            color: #aaa;
            float: right;
            font-size: 28px;
            font-weight: bold;
            cursor: pointer;
        }}
        .close:hover {{
            color: black;
        }}
        pre {{
            white-space: pre-wrap;
            word-wrap: break-word;
            background-color: #f9f9f9;
            padding: 10px;
            border-radius: 4px;
            max-height: 400px;
            overflow-y: auto;
        }}
    </style>
</head>
<body>
    <h1>Teste de Modelos LLM</h1>
    <p>Pergunta de teste: "{test_prompt}"</p>
    <p>Total de testes realizados: {len(results)}</p>

    <div class="summary">
        <h2>Resumo dos Testes</h2>
        <table class="summary-table">
            <thead>
                <tr>
                    <th>Provider</th>
                    <th>Modelos Bem-Sucedidos</th>
                    <th>Modelos Falhados</th>
                    <th>Tempo Médio (s) - Sucessos</th>
                </tr>
            </thead>
            <tbody>
"""

    for provider, stat in stats.items():
        html_content += f"""
                <tr>
                    <td>{provider}</td>
                    <td>{stat['success']}</td>
                    <td>{stat['fail']}</td>
                    <td>{stat['avg_time']}</td>
                </tr>
"""

    html_content += """
            </tbody>
        </table>
    </div>

    <h2>Modelos Bem-Sucedidos</h2>
    <table>
        <thead>
            <tr>
                <th>Provider</th>
                <th>Modelo</th>
                <th>Descrição</th>
                <th>Tempo (s)</th>
                <th>Tamanho (chars)</th>
                <th>Ação</th>
            </tr>
        </thead>
        <tbody>
"""

    for i, result in enumerate(successful):
        desc = result['description']
        escaped_desc = desc.replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')
        if len(desc) > 50:
            truncated_desc = desc[:50] + "..."
            desc_cell = f'{truncated_desc} <button class="button" title="{escaped_desc}">Ver descrição completa</button>'
        else:
            desc_cell = desc
        html_content += f"""
            <tr>
                <td>{result['provider']}</td>
                <td>{result['model']}</td>
                <td>{desc_cell}</td>
                <td>{result['response_time']}</td>
                <td>{result['response_size']}</td>
                <td><button onclick="showModal({i})">Ver Resposta</button></td>
            </tr>
"""

    html_content += """
        </tbody>
    </table>

    <h2>Modelos Falhados</h2>
    <table>
        <thead>
            <tr>
                <th>Provider</th>
                <th>Modelo</th>
                <th>Descrição</th>
                <th>Erro</th>
            </tr>
        </thead>
        <tbody>
"""

    error_modal_index = len(successful)
    for result in failed:
        desc = result['description']
        escaped_desc = desc.replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')
        if len(desc) > 50:
            truncated_desc = desc[:50] + "..."
            desc_cell = f'{truncated_desc} <button class="button" title="{escaped_desc}">Ver descrição completa</button>'
        else:
            desc_cell = desc
        escaped_error = result['response'].replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')
        if len(escaped_error) > 50:
            truncated_error = escaped_error[:50] + "..."
            error_cell = f'{truncated_error} <button class="error-button" onclick="showErrorModal({error_modal_index})">Ver erro completo</button>'
        else:
            error_cell = f'{escaped_error} <button class="error-button" onclick="showErrorModal({error_modal_index})">Ver detalhes</button>'
        html_content += f"""
            <tr>
                <td>{result['provider']}</td>
                <td>{result['model']}</td>
                <td>{desc_cell}</td>
                <td>{error_cell}</td>
            </tr>
"""
        error_modal_index += 1

    html_content += """
        </tbody>
    </table>
"""

    # Adicionar modais apenas para sucessos
    for i, result in enumerate(successful):
        response = result['response']
        if isinstance(response, str):
            escaped_response = response.replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')
        else:
            escaped_response = str(response).replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')
        html_content += f"""
    <div id="modal{i}" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeModal({i})">&times;</span>
            <h2>{result['provider']} - {result['model']}</h2>
            <p><strong>Descrição:</strong> {result['description']}</p>
            <p><strong>Tempo:</strong> {result['response_time']}s</p>
            <p><strong>Tamanho:</strong> {result['response_size']} caracteres</p>
            <h3>Resposta:</h3>
            <pre>{escaped_response}</pre>
        </div>
    </div>
"""

    # Adicionar modais para erros
    error_modal_index = len(successful)
    for result in failed:
        error_msg = result['response']
        if isinstance(error_msg, str):
            escaped_error = error_msg.replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')
        else:
            escaped_error = str(error_msg).replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')
        html_content += f"""
    <div id="errorModal{error_modal_index}" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeErrorModal({error_modal_index})">&times;</span>
            <h2>{result['provider']} - {result['model']}</h2>
            <h3>Erro Completo:</h3>
            <pre>{escaped_error}</pre>
        </div>
    </div>
"""
        error_modal_index += 1

    html_content += """
    <script>
        function showModal(index) {
            document.getElementById('modal' + index).style.display = 'block';
        }

        function closeModal(index) {
            document.getElementById('modal' + index).style.display = 'none';
        }

        function showDescModal(index) {
            document.getElementById('descModal' + index).style.display = 'block';
        }

        function closeDescModal(index) {
            document.getElementById('descModal' + index).style.display = 'none';
        }

        function showErrorModal(index) {
            document.getElementById('errorModal' + index).style.display = 'block';
        }

        function closeErrorModal(index) {
            document.getElementById('errorModal' + index).style.display = 'none';
        }

        // Fechar modal clicando fora
        window.onclick = function(event) {
            if (event.target.className === 'modal') {
                event.target.style.display = 'none';
            }
        }
    </script>
</body>
</html>
"""

    # Salvar arquivo
    output_path = Path(__file__).resolve().parent.parent / "llm_tests.html"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"Arquivo HTML gerado: {output_path}")
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Testar modelos LLM de providers.")
    parser.add_argument("--limitproviders", nargs="*", help="Lista de providers para limitar o teste (ex.: groq perplexity)")
    args = parser.parse_args()

    print("Iniciando testes de modelos LLM...")
    results = test_all_models(limit_providers=args.limitproviders)
    print(f"Testes concluídos. {len(results)} modelos testados.")

    if results:
        html_file = generate_html(results)
        print(f"Relatório HTML gerado: {html_file}")
    else:
        print("Nenhum teste realizado. Verifique as configurações de API.")
