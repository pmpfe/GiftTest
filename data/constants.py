"""
Constantes da aplicação.
"""

# Versão da aplicação
APP_VERSION = "1.0.0"
APP_NAME = "GiftTest"

# Limites de tamanho de janela (percentagem)
MIN_WINDOW_PERCENT = 30
MAX_WINDOW_PERCENT = 100
DEFAULT_WINDOW_PERCENT = 66

# Limites de perguntas para teste rápido
MIN_QUICK_TEST_QUESTIONS = 5
MAX_QUICK_TEST_QUESTIONS = 100
DEFAULT_QUICK_TEST_QUESTIONS = 20

# LLM
DEFAULT_LLM_TIMEOUT = 60
DEFAULT_LLM_PROVIDER = "groq"

# Providers suportados
LLM_PROVIDERS = [
    'groq',
    'huggingface',
    'gemini',
    'mistral',
    'perplexity',
    'openrouter',
    'cloudflare'
]

# Modelos padrão por provider
DEFAULT_MODELS = {
    'groq': 'llama-3.3-70b-versatile',
    'huggingface': 'meta-llama/Llama-3.1-8B-Instruct',
    'gemini': 'gemini-1.5-flash',
    'mistral': 'mistral-small-latest',
    'perplexity': 'sonar-pro',
    'openrouter': 'meta-llama/Meta-Llama-3.1-8B-Instruct',
    'cloudflare': '@cf/meta/llama-3-8b-instruct'
}

# Zoom
MIN_ZOOM = 0.3
MAX_ZOOM = 3.0
ZOOM_STEP = 0.1
DEFAULT_ZOOM = 1.0
DEFAULT_FONT_SIZE = 12
