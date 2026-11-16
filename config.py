import os
from pathlib import Path

from dotenv import load_dotenv

# Active model choices live in the project's .env; explicit environment values
# let the runner preserve the same configuration across its child processes.
load_dotenv(Path(__file__).with_name(".env"))

# Offline operation must not enable cloud tracing inherited from the environment.
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "").strip()
if not OLLAMA_MODEL:
    raise ValueError("Ustaw OLLAMA_MODEL w pliku .env; podaj nazwę lokalnego modelu Ollama.")

ASR_MODEL = os.getenv("ASR_MODEL", "").strip()
if not ASR_MODEL:
    raise ValueError("Ustaw ASR_MODEL w pliku .env; wybierz backend rozpoznawania mowy.")


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


# None delegates to the model/server; the effective value remains unknown.
LLM_GENERATION = {
    'num_ctx': _optional_positive_int('OLLAMA_NUM_CTX'),
    'num_predict': _optional_positive_int('OLLAMA_NUM_PREDICT'),
    'reasoning': _optional_bool('OLLAMA_REASONING'),
}
