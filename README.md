# Uruchomienie z lokalnym LLM

Projekt używa Vosk lub whisper.cpp, LangChain/LangGraph, lokalnej Ollamy i Supertonic.

1. Zainstaluj [uv](https://docs.astral.sh/uv/getting-started/installation/)
   oraz [Ollamę](https://ollama.com/download). Zainstaluj zależności projektu:

   ```bash
   uv sync --locked
   ```

2. **Oba modele wybierasz w jednym pliku: `.env` w katalogu projektu.**
   Jeśli go nie ma, utwórz go na podstawie [.env.example](.env.example).
   Przykładowa konfiguracja:

   ```env
   OLLAMA_MODEL=qwen3.5:2b
   ASR_MODEL=vosk
   ```

   `config.py` tylko odczytuje te wartości; nie ma własnych nazw zapasowych.
   Aplikacja, runner i raporty korzystają z tej samej konfiguracji.
   `.env.example` jest wzorem, nie aktywną konfiguracją. Po zmianie `.env`
   uruchom aplikację lub runner ponownie. LLM musi obsługiwać **tool calling**.
   Pobierz model wskazany w konfiguracji:

   ```bash
   uv run python -c "import config, subprocess; subprocess.run(['ollama', 'pull', config.OLLAMA_MODEL], check=True)"
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

# Wybór ASR

Backend wybierasz przez `ASR_MODEL` w tym samym `.env`, w którym ustawiasz LLM.
Brak którejkolwiek wartości jest błędem konfiguracji. Dostępne warianty:

| Wybór | Model / runtime |
| --- | --- |
| `vosk` | Vosk small-pl-0.22 |
| `whisper-small` | Whisper small / whisper.cpp |
| `whisper-medium` | Whisper medium / whisper.cpp |
| `whisper-large` | Whisper large-v3 / whisper.cpp |
| `whisper-large-v3-turbo-q5_0` | Whisper large-v3-turbo, Q5_0 / whisper.cpp |

Przed pierwszym użyciem Whisper pobierz wybrany model (ten krok wymaga internetu):

```bash
uv run python -c "from pywhispercpp.utils import download_model; download_model('small', 'models/whisper')"
```

Dla pozostałych wariantów zamień `small` na `medium`, `large-v3` albo
`large-v3-turbo-q5_0`. Program oczekuje pliku `models/whisper/ggml-<model>.bin`
i zgłasza brak wag przed rozpoczęciem nasłuchu. Nie pobiera modelu podczas sesji.

```bash
uv run python main.py \
  --audio-file assets/voice/Telefon.mp3 \
  --report-dir logs/eksperymenty/Konfiguracja1_Zadanie2
```

Ten sam wybór działa z mikrofonem po pominięciu `--audio-file`. Pakiet `asr`
udostępnia `listen(stop_event, asr="whisper-small", on_event=callback)` oraz
`listen_file(path, stop_event, asr="whisper-small", on_event=callback)`;
implementacje są w `asr/vosk.py` i `asr/whisper.py`. Model jest ładowany leniwie
i ponownie używany w kolejnych turach; Whisper przechowuje tylko ostatnio wybrany wariant.

Zaawansowane nadpisania pozostają dostępne: `--asr` zmienia ASR dla pojedynczego
uruchomienia aplikacji, a jawne zmienne środowiskowe mają pierwszeństwo nad `.env`.
Runner używa zmiennych procesu do utrwalenia wyboru na wszystkie powtórzenia;
nie zawiera osobnych nazw modeli do ręcznego zmieniania.

Whisper używa ciągłego audio mono float32 16 kHz i WebRTC VAD (tryb 2, ramki
30 ms, zakończenie po 0,45 s ciszy, minimum 90 ms ramek mowy, bufor poprzedzający
do 0,3 s). Pauzy wewnątrz wypowiedzi pozostają w audio. Plik jest podawany
w tempie 1×; EOF domyka wypowiedź bez konieczności dopisywania ciszy.
Vosk zachowuje własne strumieniowe wykrywanie końca wypowiedzi.

W TXT/JSON zapisuje się faktyczny model. Granice mowy Vosk wynikają z czasów
słów, a Whisper z WebRTC VAD; różnicę metod trzeba uwzględnić przy porównaniu
opóźnień. Czas całej sesji obejmuje też ładowanie modelu; latencje od końca
mowy go nie obejmują, ponieważ model ładuje się przed rozpoczęciem wejścia audio.

Runtime [whisper.cpp](https://github.com/ggml-org/whisper.cpp) obsługuje ARM NEON,
Accelerate, Metal i modele kwantyzowane. Integracja korzysta z
[pywhispercpp](https://github.com/absadiki/pywhispercpp); użycie GPU zależy od buildu
i dostępnego sprzętu. Sprawdzono wykrycie Metal na Apple M2, ale nie wykonano
jeszcze benchmarku transkrypcji z wagami Whisper. Nie należy zakładać stałego
przyspieszenia względem innego backendu bez pomiaru na tych samych nagraniach.

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
Zdarzenie `tool_end` przechowuje pełną zwróconą treść w polu `output` oraz
`tool_call_id`, jeśli udostępni je LangChain. Dla `ToolMessage` jest to jego
`content`, czyli treść zwracana modelowi, bez dodatkowych artefaktów narzędzia.
TXT pokazuje ją pod etykietą „Wynik przekazany do LLM”, z czytelnym formatowaniem
JSON. JSON raportu zachowuje oryginalną treść i jej typ, bez skracania.
Wyjątek narzędzia jest zapisywany jako `error`; nie jest zastępowany wynikiem.
Po dopytaniu asystenta następna wypowiedź użytkownika rozpoczyna nową turę.
Kliknięcia są osobną historią, a nie turami głosowymi. Dla powiązania zdarzeń
JSON udostępnia `turn_id`, `run_id` oraz `time_s` względem początku sesji;
w tekście przesunięcia tur odnoszą się do początku mowy.

Granice mowy są **estymacją**: Vosk używa pierwszego i ostatniego rozpoznanego
słowa, a Whisper granic WebRTC VAD. Mikrofon korzysta z czasu wejścia
audio PortAudio. Gdy brakuje wiarygodnych
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
uv run python main.py \
  --audio-file assets/voice/Telefon.mp3 \
  --report-dir logs/eksperymenty/Konfiguracja1_Zadanie2
```

Folder i brakujące katalogi nadrzędne powstają automatycznie. Każde uruchomienie
zapisuje osobną parę `session_<czas>_<id>.txt` i `.json`, więc dziesięć uruchomień
do tego samego folderu daje dziesięć par raportów. Bez parametru wyniki trafiają
do `logs/sessions/`. Ścieżki względne odnoszą się do katalogu uruchomienia programu.
Nieprawidłowy folder (np. ścieżka zajęta przez plik) powoduje błąd przed startem UI.

Runner opisany poniżej przekazuje osobny folder dla każdej próby. Import wyników
do Excela nie jest jeszcze zaimplementowany. Pole `counts.completed` w raporcie
sesji potwierdza ukończenie tury, a nie poprawność wykonania scenariusza; błędy są
zapisane w JSON i nie należy oceniać powodzenia wyłącznie po kodzie zakończenia procesu.

Plik zastępuje mikrofon. Aplikacja podaje jego audio do wybranego ASR w naturalnym
tempie 1x, wykonuje jedną turę agenta i TTS, a po zakończeniu odpowiedzi
zapisuje raport TXT/JSON i zamyka się automatycznie. Wejście nie jest dodatkowo
odtwarzane przez głośniki. Bez `--audio-file` nadal działa ciągły mikrofon.

MP3 i WAV są dekodowane przez już zainstalowany `soundfile`, a kanały są uśredniane
do mono. Do Vosk trafia PCM 16-bit. Rozpoznawacz dostaje rzeczywistą
częstotliwość pliku — dostarczone MP3 44,1 kHz nie wymagają osobnej konwersji Hz.
Tak jak mikrofon, pierwsza rozpoznana wypowiedź kończy się przy niepustym
wyniku endpointu Vosk; dalsza cisza lub następna wypowiedź w pliku nie trafiają
do tej tury. Jeśli najpierw nastąpi EOF, `FinalResult()` opróżnia rozpoznawanie
również w nagraniu bez końcowej ciszy. Whisper otrzymuje float32 16 kHz; pierwszą
wypowiedź wyznacza WebRTC VAD lub EOF. Czasy w raporcie korzystają z tego samego zegara
co mikrofon i pozostałe etapy; nagłówek dodaje `Wejście: audiofile`, ścieżkę
pliku i tempo 1x. JSON udostępnia te dane w `input_source`.

Jeśli agent poprosi o doprecyzowanie, jego pytanie kończy tę pojedynczą turę;
tryb plikowy nie otwiera potem mikrofonu. Pusty lub uszkodzony plik oraz brak
rozpoznanej mowy kończą próbę błędem, bez przekazywania pustego tekstu do LLM.
Przy zamykaniu przed wykryciem mowy wejście zostaje przerwane; po wykryciu
mowy aplikacja kończy rozpoczętą wypowiedź i odpowiedź, tak jak rozpoczętą turę
mikrofonową. Ten tryb służy pojedynczym krótkim wypowiedziom.

# Runner — zadanie 1, telefon, trzy próby

```bash
uv run python runner.py
```

W tym runnerze **Zadanie1** oznacza nagranie `assets/voice/Telefon.mp3` i polecenie
zadzwonienia do Roberta Lewandowskiego. Program wykonuje trzy próby kolejno,
na `ASR_MODEL` i `OLLAMA_MODEL` odczytanych z `.env` na początku eksperymentu.
Żeby zmienić konfigurację eksperymentu, edytuj tylko te dwie wartości w `.env`
i uruchom runner ponownie. Wszystkie trzy próby korzystają z tego samego wyboru.

W `logs/eksperymenty/` powstaje nowy folder `<ASR>_<LLM>_Zadanie1_<czas>_<id>`.
Zawiera `config.txt` z modelami, nagraniem, liczbą powtórzeń, limitem czasu i
oczekiwanym efektem; `summary.txt` i `summary.json` przechowują wyniki wszystkich
prób. W podfolderach `run_01`, `run_02`, `run_03` znajdują się oryginalne raporty
sesji TXT/JSON oraz `console.log`. Kolejny eksperyment tworzy nowy folder.

Oczekiwany efekt to dokładnie jedno wywołanie
`call_contact(name="Robert Lewandowski", number_type="mobile")`. Parametry muszą
być zgodne z oczekiwaniem, a odpowiadający mu `tool_end` musi mieć `success=True`
i należeć do tego samego `run_id` i tej samej zakończonej tury. Sesja z błędem,
przerwaną turą, powtórzonym połączeniem, innym kontaktem lub numerem nie przechodzi
oceny. Samo `get_contacts`, pytanie doprecyzowujące lub deklaracja sukcesu przez
LLM nie wystarczają. To ocena wykonanej akcji w aplikacji, bez prawdziwego połączenia
telefonicznego z siecią komórkową.

Każda próba uruchamia nowy proces aplikacji, więc historia rozmowy i stan HMI
zaczynają się od nowa. Ollama nie jest restartowana ani wymuszenie rozgrzewana:
pierwsza próba może obejmować ładowanie LLM, a kolejne korzystać z modelu w pamięci.
Runner działa z normalnym UI i odtwarzaniem TTS. Limit wynosi 300 s na próbę;
po błędzie lub przekroczeniu limitu zapisuje niepowodzenie i wykonuje kolejne próby.
Podsumowanie jest aktualizowane po każdej próbie. Kod zakończenia runnera to
`0` dla trzech sukcesów, `1` dla co najmniej jednego niepowodzenia i `2` dla braku
nagrania. Wynik oceny znajduje się w podsumowaniu eksperymentu; oryginalny status
tury w raporcie sesji nie jest zmieniany.
