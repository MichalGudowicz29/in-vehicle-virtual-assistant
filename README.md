# Uruchomienie z lokalnym LLM

Projekt używa Vosk, LangChain/LangGraph, lokalnej Ollamy i Supertonic.

1. Zainstaluj [uv](https://docs.astral.sh/uv/getting-started/installation/)
   oraz [Ollamę](https://ollama.com/download). Zainstaluj zależności projektu:

   ```bash
   uv sync --locked
   ```

2. Przygotuj lokalny model obsługujący **tool calling**. Przykład z dokumentacji
   ChatOllama (wybór modelu i jego wymagania sprzętowe należą do użytkownika):

   ```bash
   ollama pull gpt-oss:20b
   ```

   Dodaj do istniejącego `.env` jedną zmienną, zgodną z tagiem pobranego modelu:

   ```env
   OLLAMA_MODEL=gpt-oss:20b
   ```

   Wzór: [.env.example](.env.example). Domyślna nazwa jest taka sama.
   Zmiana modelu wymaga ponownego uruchomienia aplikacji. Można też podać ją
   wyłącznie dla jednego uruchomienia:

   ```bash
   OLLAMA_MODEL=gpt-oss:20b uv run python main.py
   ```

3. TTS używa `auto_download=True`: brakujący model zostanie pobrany przy
   pierwszym uruchomieniu, które wymaga wtedy internetu. Po pobraniu model
   jest używany lokalnie z cache. Model Vosk znajduje się w `models/`.

4. Uruchom lokalny serwer Ollama (`ollama serve`, jeśli aplikacja Ollama jeszcze
   go nie uruchomiła), a następnie asystenta. Mikrofon i głośniki wymagają zgód
   systemowych:

   ```bash
   uv run python main.py
   ```

LLM łączy się z `http://127.0.0.1:11434`, bez proxy środowiskowego i fallbacku
do chmurowego API. Model nie jest automatycznie pobierany ani instalowany.
Wybieraj modele lokalne, nie warianty `-cloud`. Aplikacja wyłącza tracing
LangSmith/LangChain przez `LANGSMITH_TRACING=false` i `LANGCHAIN_TRACING_V2=false`.

ASR–LLM–TTS działa lokalnie po przygotowaniu modeli. Mapa jest lokalnym
schematem: pokazuje adresy z bazy i linię START → przystanki → cel. Zmiany
głosem i dotykiem aktualizują punkty oraz kolejność trasy. Widok nie pobiera
kafelków ani tras z internetu; linia nie odwzorowuje rzeczywistych dróg.

Konfiguracja ChatOllama: [oficjalna dokumentacja](https://docs.langchain.com/oss/python/integrations/chat/ollama).

# Klawiatura ekranowa

Dotknięcie pola adresu lub przystanku otwiera lokalną klawiaturę ekranową.
Enter chowa klawiaturę; START NAVIGATION i DODAJ chowają ją oraz wykonują
akcję. Widok nad klawiaturą zmniejsza się, żeby pole pozostawało widoczne.

# Wyszukiwanie adresów

Cel i przystanek można wpisywać fragmentami, bez `ul.`, polskich znaków,
wielkich liter i przecinków, np. `zolnierska47`. Podpowiedzi pojawiają się
nad klawiaturą. Dotknięcie wyniku wypełnia pole pełnym adresem; dopiero
START NAVIGATION lub DODAJ wykonuje akcję. Numery domów są porównywane
w całości (`47` nie pasuje do `147`). Niejednoznaczny adres wymaga wyboru
lub doprecyzowania. Te same reguły wyszukiwania obowiązują narzędzia głosowe.
Wyszukiwanie korzysta z lokalnej bazy; nie poprawia literówek.

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

Nazwa modelu w TXT/JSON pochodzi z tej samej konfiguracji co agent. Tokeny
pochodzą z metadanych modelu (dla Ollamy: liczniki prompt/eval, jeśli zwrócone). Raport podaje pokrycie pomiaru;
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

Testy korzystają z wirtualnego audio SDL, Qt bez ekranu i programowego
renderowania. Tymczasowy WAV zastępuje prywatne pliki `music/*.mp3`, również
w testach uruchamiających aplikację w osobnym procesie. Nie trzeba udostępniać
karty dźwiękowej ani własnej muzyki. Workflow Ubuntu instaluje systemowe
biblioteki PortAudio i Qt, których samo `uv sync` nie dostarcza.

# Jedna tura z pliku audio

```bash
uv run python main.py --audio-file assets/voice/Telefon.mp3
```

Folder wyników można wskazać parametrem `--report-dir`, także w trybie mikrofonu:

```bash
OLLAMA_MODEL=qwen3.5:4b uv run python main.py \
  --audio-file assets/voice/Telefon.mp3 \
  --report-dir logs/eksperymenty/Konfiguracja1_Zadanie2
```

Folder i brakujące katalogi nadrzędne powstają automatycznie. Każde uruchomienie
zapisuje osobną parę `session_<czas>_<id>.txt` i `.json`, więc dziesięć uruchomień
do tego samego folderu daje dziesięć par raportów. Bez parametru wyniki trafiają
do `logs/sessions/`. Ścieżki względne odnoszą się do katalogu uruchomienia programu.
Nieprawidłowy folder (np. ścieżka zajęta przez plik) powoduje błąd przed startem UI.

Przyszły runner może przekazywać ten sam folder dla kolejnych powtórzeń danej
konfiguracji i zadania. Automatyczny runner i import wyników do Excela nie są
jeszcze zaimplementowane. Pole `counts.completed` potwierdza ukończenie tury,
a nie poprawność wykonania scenariusza; błędy są zapisane w JSON i nie należy
oceniać powodzenia wyłącznie po kodzie zakończenia procesu.

Plik zastępuje mikrofon. Aplikacja podaje jego audio do Vosk w naturalnym
tempie 1x, wykonuje jedną turę agenta i TTS, a po zakończeniu odpowiedzi
zapisuje raport TXT/JSON i zamyka się automatycznie. Wejście nie jest dodatkowo
odtwarzane przez głośniki. Bez `--audio-file` nadal działa ciągły mikrofon.

MP3 i WAV są dekodowane przez już zainstalowany `soundfile`. Do Vosk trafia
PCM 16-bit mono; stereo jest uśredniane do mono. Rozpoznawacz dostaje rzeczywistą
częstotliwość pliku — dostarczone MP3 44,1 kHz nie wymagają osobnej konwersji Hz.
Tak jak mikrofon, pierwsza rozpoznana wypowiedź kończy się przy niepustym
wyniku endpointu Vosk; dalsza cisza lub następna wypowiedź w pliku nie trafiają
do tej tury. Jeśli najpierw nastąpi EOF, `FinalResult()` opróżnia rozpoznawanie
również w nagraniu bez końcowej ciszy. Czasy w raporcie korzystają z tego samego zegara
co mikrofon i pozostałe etapy; nagłówek dodaje `Wejście: audiofile`, ścieżkę
pliku i tempo 1x. JSON udostępnia te dane w `input_source`.

Jeśli agent poprosi o doprecyzowanie, jego pytanie kończy tę pojedynczą turę;
tryb plikowy nie otwiera potem mikrofonu. Pusty lub uszkodzony plik oraz brak
rozpoznanej mowy kończą próbę błędem, bez przekazywania pustego tekstu do LLM.
Przy zamykaniu przed wykryciem mowy wejście zostaje przerwane; po wykryciu
mowy aplikacja kończy rozpoczętą wypowiedź i odpowiedź, tak jak rozpoczętą turę
mikrofonową. Ten tryb służy pojedynczym krótkim wypowiedziom.
