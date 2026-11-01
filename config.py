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
