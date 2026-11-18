import os
from pathlib import Path

from dotenv import load_dotenv

# Optional overrides live in the project's .env; without it the defaults below are used.
load_dotenv(Path(__file__).with_name(".env"))

# Offline operation must not enable cloud tracing inherited from the environment.
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"

DEFAULT_LLM = "qwen3.5:2b"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "").strip() or DEFAULT_LLM

# Tests and tools that must not load models at start-up set ASSISTANT_PRELOAD=0.
PRELOAD = os.getenv("ASSISTANT_PRELOAD", "1").strip() != "0"


def _optional_positive_int(name):
    value = os.getenv(name, '').strip()
    if not value:
        return None
    try:
        number = int(value)
    except ValueError:
        raise ValueError(f'{name} musi być dodatnią liczbą całkowitą.') from None
    if number <= 0:
        raise ValueError(f'{name} musi być dodatnią liczbą całkowitą.')
    return number


def _optional_bool(name):
    value = os.getenv(name, '').strip().lower()
    if not value:
        return None
    if value not in ('true', 'false'):
        raise ValueError(f'{name} musi mieć wartość true albo false.')
    return value == 'true'


# None delegates to the Ollama server. Thinking is off by default: it adds latency and,
# with the server's token limit, cut off answers before any tool call.
_reasoning = _optional_bool('OLLAMA_REASONING')
LLM_GENERATION = {
    'num_ctx': _optional_positive_int('OLLAMA_NUM_CTX'),
    'num_predict': _optional_positive_int('OLLAMA_NUM_PREDICT'),
    'reasoning': False if _reasoning is None else _reasoning,
}
