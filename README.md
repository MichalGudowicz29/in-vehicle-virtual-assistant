UV needed to run
https://docs.astral.sh/uv/getting-started/installation/

# How to run
1. Add '.env' file with OPENAI_API_KEY
2. Give access to microphone and speakers

3. Run with 'uv'
```bash
uv sync
uv run python main.py
```

The assistant listens continuously and speaks each response.

# Raport sesji

Po kliknięciu **Zakończ**, zamknięciu okna albo Ctrl+C aplikacja kończy
rozpoczętą odpowiedź i zapisuje w `logs/sessions/` dwa pliki o wspólnym ID:

- `session_….txt` — historia tur, operacji dotykowych i zmian ekranów oraz
  statystyki N / średnia / min / max w sekundach.
- `session_….json` — te same zdarzenia i obliczenia do późniejszej analizy.

Każda tura głosowa zawiera transkrypcję, wywołania LLM i narzędzi, ich
czasy i wyniki, odpowiedź oraz osobne etapy syntezy i odtwarzania TTS.
Po dopytaniu asystenta następna wypowiedź użytkownika rozpoczyna nową turę.
Kliknięcia są osobną historią, a nie turami głosowymi. Dla powiązania zdarzeń
JSON udostępnia `turn_id`, `run_id` oraz `time_s` względem początku sesji;
w tekście przesunięcia tur odnoszą się do początku mowy.

Granice mowy są **estymacją Vosk** według pierwszego i ostatniego
rozpoznanego słowa, z czasem wejścia audio PortAudio. Gdy brakuje wiarygodnych
granic lub mikrofon zgłasza utratę danych, raport pokazuje brak pomiaru.
Start audio oznacza wywołanie odtwarzania, nie pomiar dźwięku przy głośniku.
Pauza 0,7 s po odpowiedzi nie wchodzi do czasu tury.

Tokeny pochodzą z metadanych dostawcy modelu. Raport podaje pokrycie pomiaru;
brak zużycia nie jest traktowany jako zero. Statystyki wykorzystują wyłącznie
kompletne pary znaczników, również dla żądań zakończonych błędem. Przy
równoległych narzędziach suma ich czasów nie jest czasem agenta.

Status `zakończona` oznacza ukończenie przetwarzania tury. **Nie jest oceną
sukcesu zadania**. Błędy narzędzi mają własny wynik. Automatyczne scenariusze,
limit 10 s na zadanie i import datasetów nie są częścią tej funkcji.
Raport dotyku mierzy operacje i zapisuje kliknięcia; nie wylicza czasu całego
zadania ręcznego bez osobnego oznaczenia jego początku i końca.

Raporty zawierają tekst wypowiedzi i argumenty narzędzi, więc mogą zawierać
dane osobowe. Katalog `logs/` jest wykluczony z Git. Nagłe zabicie procesu
nie gwarantuje raportu końcowego. Błąd zapisu jest wyświetlany w konsoli
i nie blokuje zamknięcia aplikacji.

Weryfikacja bez mikrofonu i płatnego API:

```bash
uv run pytest
```
