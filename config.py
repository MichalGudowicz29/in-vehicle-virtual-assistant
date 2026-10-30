import os

from dotenv import load_dotenv

load_dotenv()

# Offline operation must not enable cloud tracing inherited from the environment.
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gpt-oss:20b").strip()
if not OLLAMA_MODEL:
    raise ValueError("OLLAMA_MODEL nie może być puste; podaj nazwę lokalnego modelu Ollama.")
