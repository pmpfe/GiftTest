# Sistema de Testes GIFT

Aplicação para praticar perguntas em formato GIFT com possibilidade de explicar as respostas via serviços de IA.

![Explanation](assets/shot2_explain.png)
![Main Menu](assets/shot1_menu.png)

### Instalação via Python

**Outras distros / venv:**
```bash
pip install -r requirements.txt
```

### Instalação via Executável

Para Windows e Linux, pode descarregar executáveis pré-compilados:

- **[Última Release →](https://github.com/pmpfe/GiftTest/releases/latest)**


## Funcionalidades
- Seleção de categorias e número de perguntas
- Explicação de perguntas via LLM (Groq, Hugging Face, Gemini, Mistral, Perplexity, OpenRouter, Cloudflare)
- Configurações para ficheiro GIFT, provedor/modelo LLM e prompt
- Resultados com estatísticas e histórico
- Correção imediata opcional durante o teste ("Corrigir-me se estiver errado")
- Acesso rápido a "Explicar" a partir do histórico/resultados
- Renderização HTML com QTextBrowser (leve e sem dependências extra)
- Zoom no conteúdo da explicação (Ctrl + roda do rato, Ctrl +/-, Ctrl + 0)
- Links abrem automaticamente no browser externo
- Imagens ilustrativas opcionais nas explicações (coluna lateral) com seleção de fonte:
	- Wikimedia Commons, Openverse, Radiopaedia (scraping best-effort), Unsplash Source
	- Pexels (requer `PEXELS_API_KEY`)
	- Sem imagens

## Configuração LLM
- Aceder a "Configurações" → LLM
- Configurar uma API_KEY (precisa de registo prévio, quase todos oferecem acessos free tier)
- Providers: Groq, Hugging Face, Google Gemini, Mistral, Perplexity, OpenRouter, Cloudflare
- Prompt padrão gera HTML formatado
- Para enriquecer com imagens, o LLM pode incluir no HTML comentários no formato:
	- `<!-- IMAGE_KEYWORDS: palavra1, palavra2 -->`
	- A fonte de imagens pode ser definida em Configurações (e também alterada no diálogo da explicação sem persistir)
- API keys guardadas localmente em `data/preferences.json`

## Estrutura
- `main.py`: aplicação principal (QMainWindow)
- `data/constants.py`: constantes da aplicação
- `data/selection_screen.py`: seleção de categorias
- `data/question_screen.py`: apresentação de perguntas
- `data/results_screen.py`: resultados e estatísticas
- `data/history_screen.py`: histórico detalhado de testes
- `data/settings_screen.py`: configurações (ficheiro, LLM)
- `data/explanation_viewer.py`: visualizador HTML
- `data/image_enrichment.py`: extração de keywords e pesquisa de imagens (opcional)
- `data/gift_parser.py`: parser de ficheiros GIFT
- `data/llm_client.py`: cliente LLM (múltiplos providers)
- `data/preferences.py`: persistência de configurações
- `data/test_logger.py`: histórico de testes

## Notas
- Interface Qt6 moderna
- Tamanhos de janela configuráveis em "Configurações" (percentagem do ecrã)
- Executável Windows com ~21MB (compilado com Nuitka)
