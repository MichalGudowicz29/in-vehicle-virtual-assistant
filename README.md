# In-Vehicle Virtual Assistant

Prototyp ekranu samochodowego (muzyka, telefon, nawigacja) obsługiwanego dotykiem
i głosem. Polecenie głosowe przechodzi lokalnie przez ASR → LLM z narzędziami → TTS;
nic nie jest wysyłane do chmury. Osobny runner wykonuje serię pomiarową 108 prób
i ocenia, czy zadanie zostało wykonane.

To symulacja: połączenie telefoniczne jest udawane, mapa jest schematem z lokalnej
bazy adresów (bez rzeczywistych tras), muzyka gra z plików w `music/`.

## Szybki start

Wymagania: [uv](https://docs.astral.sh/uv/), [Ollama](https://ollama.com/download)
(uruchomiona lokalnie), mikrofon i głośniki.

```bash
uv sync --locked
cp .env.example .env                                  # OLLAMA_MODEL, ASR_MODEL
uv run python -m experiments.prepare_models           # LLM, Whisper, Vosk, TTS (wymaga internetu)
uv run python main.py                                 # mikrofon + dotyk
```

Pliki `music/1.mp3`–`3.mp3` i nagrania `assets/voice/` nie są w gicie (MP3) — skopiuj je ręcznie.

| Tryb | Polecenie |
| --- | --- |
| Mikrofon + dotyk (Whisper small) | `uv run python main.py` |
| Jedna tura z pliku, potem wyjście | `uv run python main.py --audio-file assets/voice/Telefon/1.mp3` |
| Inny ASR | `--asr vosk` / `whisper-small` / `whisper-medium` / `whisper-large` / `whisper-large-v3-turbo-q5_0` |
| Folder raportów | `--report-dir logs/...` (domyślnie `logs/sessions/`) |
| Seria pomiarowa A–D | `uv run python -m experiments.runner` |
| Testy (bez mikrofonu i LLM) | `uv run pytest` |

Na serwerze bez ekranu (SSH): `QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software`
przed poleceniem; wyjście audio nadal musi działać.

Konfiguracja `.env` (wzór: [.env.example](.env.example)): `OLLAMA_MODEL` (lokalny model
z tool calling), `ASR_MODEL`, opcjonalnie `OLLAMA_NUM_CTX`, `OLLAMA_NUM_PREDICT`,
`OLLAMA_REASONING` (puste = domyślne serwera; ręcznie reasoning domyślnie `false`).

## Struktura

```text
main.py              start: Qt + wątek głosowy + raport, parametry CLI
CarSystem/           model HMI: MusicController, ContactController, NavigationController
qml/, Main.qml       widok: ekrany dotykowe, mapa, klawiatura ekranowa, baner błędu
voice_worker.py      pętla głosowa w osobnym wątku: ASR → Assistant → TTS
asr/                 Vosk i whisper.cpp (mikrofon lub plik w tempie 1×)
assistant/           agent LLM: prompts, tools, plan_guard (strażnik planu), agent
tts.py               Supertonic
session_report.py    zdarzenia i czasy tury → raport TXT/JSON
session_callbacks.py pomiar żądań LLM i narzędzi (callbacki LangChain)
session_controls.py  akcje dotykowe z QML + baner komunikatu
shutdown.py          zamknięcie: stan końcowy HMI + zapis raportu
experiments/         runner serii A–D, kryterium oceny, przygotowanie modeli
docs/                architektura (baza rozdz. 3–4), procedura odbioru
```

Opis architektury, przepływu tury, raportu i serii pomiarowej: [docs/architektura.md](docs/architektura.md).
Procedura odbioru na docelowym urządzeniu: [docs/odbior.md](docs/odbior.md).

Raporty w `logs/` zawierają transkrypcje i argumenty narzędzi (dane osobowe) — katalog jest poza gitem.
