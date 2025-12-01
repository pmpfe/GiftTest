# Sistema de Testes GIFT

Aplicação para praticar perguntas em formato GIFT com interface Qt6.

## Dependências

A aplicação usa apenas bibliotecas Qt:

- `PyQt6` (widgets, layouts)
- `PyQt6-WebEngine` (renderização HTML para explicações)

Instalação:

**Arch Linux:**
```bash
sudo pacman -S python-pyqt6 python-pyqt6-webengine
```

**Outras distros / venv:**
```bash
pip install PyQt6 PyQt6-WebEngine
```

## Executar

```bash
python gift_test_practice.py
```

## Funcionalidades
- Seleção de categorias e número de perguntas
- Explicação de perguntas via LLM (Groq, Hugging Face, Gemini)
- Suporte adicional (experimental) a Mistral, Perplexity, OpenRouter (chat compatível)
- Configurações para ficheiro GIFT, provedor/modelo LLM e prompt
- Resultados com estatísticas e histórico
- Renderização HTML rica com QWebEngineView
- Zoom no conteúdo da explicação (Ctrl + roda do rato, Ctrl +/-, Ctrl + 0)

## Configuração LLM
- Aceda a "Configurações" → LLM
- Provedores: Groq, Hugging Face, Google Gemini, Mistral, Perplexity, OpenRouter, Cloudflare (geração Cloudflare não implementada)
- Prompt padrão gera HTML formatado
- API keys guardadas localmente em `data/preferences.json`

## Estrutura
- `gift_test_practice.py`: aplicação principal (QMainWindow)
- `data/selection_screen.py`: seleção de categorias
- `data/question_screen.py`: apresentação de perguntas
- `data/results_screen.py`: resultados e estatísticas
- `data/settings_screen.py`: configurações (ficheiro, LLM)
- `data/explanation_viewer.py`: visualizador HTML
- `data/gift_parser.py`: parser de ficheiros GIFT
- `data/llm_client.py`: cliente LLM (Groq/HF/Gemini)
- `data/preferences.py`: persistência de configurações
- `data/test_logger.py`: histórico de testes
- `data/literatura-classica-50.gift.txt`: exemplo de dataset (768 perguntas)

## Notas
- Interface Qt6 moderna
- Tamanhos de janela configuráveis em "Configurações" (percentagem do ecrã)
- Links das explicações: abrir no browser ou dentro da aplicação (configurável)
