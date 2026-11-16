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
   Aplikacja i jej raporty korzystają z tej konfiguracji. Końcowy runner serii A–D
   ma własną macierz w `runner.VARIANTS` i przekazuje ją procesom przez środowisko.
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

Prompt w `assistant.py` definiuje agenta jako warstwę wykonawczą: jednoznaczne
polecenia realizuje bez pytania o zgodę i bez słownego potwierdzenia sukcesu.
Kontakt z jednym numerem wybiera od razu; przy kilku numerach pyta tylko wtedy,
gdy użytkownik nie wskazał typu. Komunikat głosowy jest potrzebny przy istotnej
niejednoznaczności, błędzie albo pytaniu informacyjnym. Pusta odpowiedź końcowa
kończy turę bez uruchamiania TTS i bez pomiarów syntezy/odtwarzania w raporcie.
Stosowanie tych reguł przez dany model należy sprawdzać na nagraniach testowych.

Przed akcjami wykonawczymi agent zapisuje `set_action_plan` z nazwami wszystkich
żądanych akcji w kolejności wykonania. Plan jest niezmienny w obrębie tury.
Narzędzia z jednej odpowiedzi modelu wykonują się kolejno (`max_concurrency=1`),
żeby zaplanowana pauza nie wyprzedziła wyboru utworu.
Pobranie kontaktów, biblioteki lub miejsc nie zalicza żadnej akcji planu.
Po sukcesie ostatniej akcji middleware zwraca pustą odpowiedź bez kolejnego
żądania HTTP do LLM. Nieudana akcja nie przesuwa planu; doprecyzowanie lub
komunikat błędu nadal mogą zakończyć odpowiedź. Pusta odpowiedź bez wykonania
całego planu jest błędem, a nie potwierdzeniem realizacji polecenia.

Udane połączenia, wybory utworów i operacje na trasie są zapamiętywane wraz
z argumentami do końca tury. Identyczna ponowna akcja nie uruchamia kontrolera.
Niezamówione przełączenie muzyki jest blokowane przez plan; jawnie zaplanowana
pauza pozostaje dozwolona. `tool_start` i `tool_end` nadal zapisują próbę,
`success=false` oraz powód blokady w wyniku narzędzia. Limit grafu wynosi 24
kroki, aby pomieścić plan i pobieranie danych dla poleceń złożonych; ochronę
przed powtórzeniem zapewnia kod, niezależnie od tego limitu.

Opcjonalne `OLLAMA_NUM_CTX`, `OLLAMA_NUM_PREDICT` i `OLLAMA_REASONING` są opisane
w `.env.example`. Puste wartości pozostawiają domyślne ustawienia runtime.
Raporty TXT/JSON zapisują żądane ustawienia przy `llm_start`, a przy `llm_end`
`done_reason`, metadane serwera i dostępne długości treści oraz reasoning.
`null` nie oznacza wyłączonego reasoning ani ustalonego rozmiaru kontekstu.
Domyślnych parametrów generacji nie zmieniono bez dowodu przyczyny błędów.
[Diagnoza przypadków 4096 tokenów i XML](GENERATION_DIAGNOSIS.md).

Przed wyborem muzyki agent pobiera `get_track_list` w bieżącej turze i dopasowuje
życzenie do dostępnych tytułów i wykonawców. `select_track` odrzuca tytuł, którego
nie było na tej liście; kontroler dodatkowo sprawdza, czy nadal jest w bibliotece.
Wybór od razu uruchamia odtwarzanie, więc po sukcesie nie należy wywoływać
`play_pause` — zatrzymałoby muzykę. Brak dopasowania lub istotna niejednoznaczność
wymagają krótkiego komunikatu albo pytania. Wznowienie, pauza i przejście do
następnego/poprzedniego utworu nie wymagają pobrania listy.

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
  --audio-file assets/voice/Telefon/1.mp3 \
  --report-dir logs/eksperymenty/Konfiguracja1_Zadanie2
```

Ten sam wybór działa z mikrofonem po pominięciu `--audio-file`. Pakiet `asr`
udostępnia `listen(stop_event, asr="whisper-small", on_event=callback)` oraz
`listen_file(path, stop_event, asr="whisper-small", on_event=callback)`;
implementacje są w `asr/vosk.py` i `asr/whisper.py`. Model jest ładowany leniwie
i ponownie używany w kolejnych turach; Whisper przechowuje tylko ostatnio wybrany wariant.

Zaawansowane nadpisania pozostają dostępne: `--asr` zmienia ASR dla pojedynczego
uruchomienia aplikacji, a jawne zmienne środowiskowe mają pierwszeństwo nad `.env`.
Runner serii A–D ustawia obie zmienne z `runner.VARIANTS` na wszystkie powtórzenia.
`prepare_models.py` pobiera modele z tej samej macierzy, więc nie ma drugiej listy do zmieniania.

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
Narzędzia `navigate_to` i `add_stop` składają adres we wspólnej funkcji:
`Żołnierska`, `ul. Żołnierska` i `ulica Żołnierska` dostają dokładnie jeden
prefiks `ul.`. Jeśli pole ulicy kończy się już podanym osobno numerem domu,
numer nie jest powtarzany. Sprzeczne numery, np. ulica z `147` i osobne `47`,
nie są automatycznie zamieniane na wybrany adres.

# Raport sesji

Po kliknięciu **Zakończ**, zamknięciu okna albo Ctrl+C aplikacja kończy
rozpoczętą odpowiedź i zapisuje w `logs/sessions/` dwa pliki o wspólnym ID:

- `session_….txt` — historia tur, operacji dotykowych i zmian ekranów oraz
  statystyki N / średnia / min / max w sekundach.
- `session_….json` — te same zdarzenia i obliczenia do późniejszej analizy.

W trybie `--experiment` aplikacja dodatkowo zapisuje raport początkowy przed
inicjalizacją kontrolerów i odświeża go co 5 s przez timer Qt. Zapis cząstkowy
nie kończy aktywnej tury ani nie zamraża czasów. TXT pokazuje „w toku — raport
cząstkowy”, JSON ma `ended_at: null`. Normalne zakończenie zastępuje te same
pliki pełnym raportem. Pliki są podmieniane atomowo osobno dla TXT i JSON.
Po przymusowym zakończeniu pozostaje ostatnia udana kopia, z dostępnymi
pomiarami; brakujących etapów nie zastępuje się zerami. Odświeżanie wymaga
działającej pętli Qt — zawieszenie GUI może zatrzymać kolejne zapisy.

Każda tura głosowa zawiera transkrypcję, wywołania LLM i narzędzi, ich
czasy i wyniki, odpowiedź oraz osobne etapy syntezy i odtwarzania TTS.
Statystyki raportu i summary runnera zawierają też czasy komponentów na turę:

- `ASR total`: od początku mowy do gotowej transkrypcji, wliczając wypowiedź.
- `LLM total`: suma czasów wszystkich żądań LLM w turze, bez narzędzi.
  Czas agenta z narzędziami pozostaje osobną metryką. Niepełne pary start/koniec
  żądań wykluczają turę z tej sumy.
- `TTS total`: od startu syntezy do końca odtwarzania, wliczając przerwę
  przed odtwarzaniem. Synteza i odtwarzanie są także pokazywane osobno.

Ładowanie modeli przed znacznikami startu nie wchodzi do tych czasów.
Brak etapu (np. brak odpowiedzi głosowej po sukcesie) oznacza brak pomiaru,
a nie zero. Tabela podaje N / średnią / min / max dla zmierzonych tur.

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
Testy ASR i TTS podmieniają `sounddevice` przed importem, więc nie inicjalizują
PortAudio ani nie wymagają działającego serwera PulseAudio.

# Jedna tura z pliku audio

```bash
uv run python main.py --audio-file assets/voice/Telefon/1.mp3
```

Folder wyników można wskazać parametrem `--report-dir`, także w trybie mikrofonu:

```bash
uv run python main.py \
  --audio-file assets/voice/Telefon/1.mp3 \
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

# Runner — końcowa seria A–D

Na komputerze z Ubuntu użyj istniejącej instalacji Ollamy i zwykłego środowiska uv:

```bash
uv sync --locked --python 3.13
uv run --locked python prepare_models.py
uv run --locked python prepare_models.py --check
uv run --locked python runner.py
```

`prepare_models.py` pobiera LLM i Whisper wskazane w `runner.VARIANTS` oraz
przygotowuje Supertonic. Ollama musi już działać lokalnie. Skopiuj także
`assets/voice/`, `music/` i model Vosk — Git pomija pliki MP3. Nie przenoś `.venv`
z macOS; `uv sync` utworzy środowisko dla Ubuntu.

Przy uruchamianiu przez SSH bez dostępu do ekranu zamień ostatnie polecenie na:

```bash
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software uv run --locked python runner.py
```

To wyłącza wyświetlanie okna, ale nadal wymaga działającego wyjścia audio na tym
komputerze (pygame i TTS). Dostęp do dźwięku przez SSH zależy od sesji użytkownika;
nie dodajemy konfiguracji wirtualnych głośników. GPU dla Ollamy sprawdzisz przez
`ollama ps` podczas działania modelu. Zwykły pakiet pywhispercpp z PyPI używa CPU;
CUDA dla Ollamy nie włącza automatycznie CUDA dla Whisper.

```bash
uv run python runner.py
```

Runner jest samodzielnym skryptem korzystającym z biblioteki standardowej.
Uruchamia `main.py` w osobnych procesach, przekazując `--asr`, `--audio-file`,
`--report-dir`, `--experiment` oraz zmienne `ASR_MODEL` i `OLLAMA_MODEL` w środowisku dziecka.
Nie importuje aplikacji, nie modyfikuje jej kodu ani `.env`. Wartości modeli w
`.env` nie wybierają wariantu eksperymentu; macierz jest stała:

| Wariant | ASR_MODEL | OLLAMA_MODEL |
| --- | --- | --- |
| A | vosk | qwen3.5:2b |
| B | whisper-small | qwen3.5:2b |
| C | vosk | qwen3.5:4b |
| D | whisper-small | qwen3.5:4b |

TTS pozostaje Supertonic. Wcześniej przygotuj oba modele ASR i oba modele LLM,
uruchom Ollamę i zapewnij pamięć potrzebną całej aplikacji. Runner nie pobiera
modeli ani nie zmienia ustawień generacji, promptu lub limitu kroków agenta.

## Nagrania i kolejność

W każdym katalogu zadania są **dokładnie trzy niepuste pliki `1.mp3`, `2.mp3`,
`3.mp3`**. Numery odpowiadają Audio 1, 2, 3 z notatek użytkownika.
Brak katalogu, inne nazwy lub liczba plików, albo pusty plik kończą runner kodem 2, przed
utworzeniem serii i uruchomieniem jakiegokolwiek procesu aplikacji.

| Zadanie | Katalog | Oczekiwany efekt wszystkich trzech wypowiedzi |
| --- | --- | --- |
| 1 — Muzyka | `assets/voice/Muzyka/` | Odtwarzanie Christmas Eve, czyli `music/1.mp3`. |
| 2 — Telefon | `assets/voice/Telefon/` | Jedno połączenie z Robertem Lewandowskim, numer mobilny. |
| 3 — Nawigacja | `assets/voice/Nawigacja/` | Cel ul. Żołnierska 47, Szczecin, bez przystanków. |

| Zadanie | Audio 1 — polecenie wprost | Audio 2 — naturalna parafraza | Audio 3 — polecenie nie wprost |
| --- | --- | --- | --- |
| Muzyka | Włącz piosenkę Christmas Eve | Włącz Christmas Eve, święta już blisko | Włącz jakąś muzykę, chcę poczuć klimat świąt |
| Telefon | Zadzwoń do Roberta Lewandowskiego | Połącz mnie z Robertem Lewandowskim, musze mu coś powiedzieć | Zadzwoń do pierwszego mężczyzny jakiego mam w kontaktach |
| Nawigacja | Ustaw cel nawigacji na ulicę Żołnierska 47 w Szczecinie | Jedziemy na ulicę Żołnierską 47 | Potrzebuje dojechać na Żołnierską, tam gdzie zawsze. |

To deklarowane treści i typy nagrań, zapisane w runnerze jako metadane,
bez weryfikacji zgodności z dźwiękiem. Nie są podawane ASR ani LLM jako
podpowiedzi i nie zastępują faktycznej transkrypcji. Nie są zwalidowanymi
poziomami trudności: dla telefonu Audio 3 wymaga interpretacji imienia i
kolejności kontaktów (Robert jest pierwszy; baza nie ma pola płci).
Nawigacja Audio 2 nie podaje miasta, a Audio 3 także numeru. Baza ma jeden
adres przy Żołnierskiej — 47 w Szczecinie — dostępny przez get_places_list,
ale aplikacja nie ma historii miejsc „tam gdzie zawsze”. Pytanie o
doprecyzowanie bez wykonania nadal oznacza niewykonanie zadania w jednej turze;
samo w sobie nie dowodzi błędnego zachowania asystenta.

Kolejność: A, B, C, D. Każdy wariant wykonuje zadania 1, 2, 3; w każdym zadaniu
najpierw trzy powtórzenia nagrania 1, następnie nagrania 2 i 3.
Łącznie **4 × 3 × 3 × 3 = 108 ocenianych prób**.

Przed zadaniami każdego wariantu odbywa się jedna dodatkowa próba rozgrzewająca
z pierwszym nagraniem muzyki. Jej raporty i wynik trafiają do `warmup/`; nie
wchodzą do 108 prób, success rate, średnich ani rankingu zadań. Łącznie aplikacja
jest więc wywoływana 112 razy. Niepowodzenie rozgrzewania jest widoczne w konsoli
i `warmup/summary.json`; runner nadal wykonuje zadania i kolejne warianty.
Ollama nie jest restartowana. Rozgrzewanie nie gwarantuje braku późniejszego
wyładowania modelu lub wpływu temperatury/pamięci na czasy.
Dotyczy przede wszystkim LLM utrzymywanego przez Ollamę; ASR i TTS są ponownie
inicjalizowane w każdym nowym procesie aplikacji.

Każda próba uruchamia nowy proces, z domyślnym stanem HMI i nową historią rozmowy.
Tryb `--experiment` jest włączony także podczas rozgrzewania. Wymaga
`--audio-file`, więc mikrofon nie jest otwierany. Cała zawartość okna jest
nieaktywna dla użytkownika (dotyk, mysz i klawiatura), a metody obsługujące dotyk
odrzucają akcje i nie zapisują pomiarów dotyku. Agent nadal steruje kontrolerami,
ekrany mogą się aktualizować, a TTS i muzyka działają normalnie. Przycisk
„Zakończ” w oknie także jest nieaktywny; do przerwania serii służy Ctrl+C
w terminalu. Systemowe zamknięcie okna nadal może zakończyć bieżącą próbę.
Zwykłe uruchomienie aplikacji bez `--experiment` zachowuje obsługę dotykową
i mikrofonową; samo `--audio-file` nie blokuje dotyku.

Tryb `--experiment` zaczyna od wstrzymanego Chill song, zamiast docelowego
Christmas Eve. Zwykłe uruchomienie nadal zaczyna od wstrzymanego Christmas Eve.
Ocena muzyki wymaga pobrania biblioteki przed wyborem Christmas Eve dokładnie
raz i jego odtwarzania na końcu; samo `play_pause` nie zalicza zadania.
Wcześniejsze serie zaczynały od Christmas Eve i używały łagodniejszego kryterium,
więc ich wyników nie należy porównywać bez uwzględnienia tej zmiany warunków.
Numeracja zadań jest zgodna z dokumentacją ewaluacji i Excelem.

## Wyniki

Każde uruchomienie tworzy nowy katalog, zachowując poprzednie serie:

```text
logs/eksperymenty/seria_ABCD_<data>_<czas>_<mikrosekundy>/
  config.json
  A_vosk_qwen3.5_2b/
    warmup/                  # raporty sesji, console.log, summary.json
    zad1_Muzyka/
      config.txt
      summary.json
      summary.txt
      recording_01/
        run_01/              # raporty sesji TXT/JSON, console.log i result.json
        run_02/
        run_03/
      recording_02/
      recording_03/
    zad2_Telefon/
    zad3_Nawigacja/
  B_whisper-small_qwen3.5_2b/
  C_vosk_qwen3.5_4b/
  D_whisper-small_qwen3.5_4b/
```

`config.json` zapisuje macierz, liczbę prób, limit czasu i listę wejściowych
plików z SHA-256, numerami audio, typami i deklarowanymi treściami poleceń.
`config.txt` każdego zadania zawiera wariant, modele, pliki, typy, treści i
oczekiwany efekt. Każde zadanie ma dziewięć ocenianych prób. W `runs` znajdują
się osobno `recording`, `recording_type`, `prompt_text`, `repetition`,
`audio_file` i numer `run` 1–9. TXT również pokazuje numer, typ i treść
polecenia przy każdej próbie. Summary zadania nadal łączy jego dziewięć prób;
numer i typ audio pozwalają rozdzielić je w dalszej analizie.
Podsumowania są aktualizowane po każdej próbie.
`result.json` w każdym folderze próby (także warmup) zapisuje wynik procesu,
ocenę zadania i dostępne pomiary również wtedy, gdy aplikacja nie utworzyła
raportu sesji. Flaga `report_complete` ma wartość true dla raportu końcowego,
false dla cząstkowego i null, gdy brak poprawnego raportu. Logi Pythona są
niebuforowane (`PYTHONUNBUFFERED=1`), więc widoczny jest postęp przed timeoutem.
Nie oznacza to usunięcia przyczyny ewentualnego zawieszenia.

`summary.txt` zawiera wyniki kolejnych prób, czasy etapów N/średnia/min/max,
tokeny, statystyki zbiorcze, success rate i best/worst run. Statystyki obejmują
wszystkie dostępne pomiary, także z prób nieudanych; brak nie jest zerem.
Średnie pojedynczych żądań LLM i narzędzi są ważone liczbą pomiarów N.
Best/worst to czas pełnej tury wśród poprawnie zakończonych prób.

## Ocena zadania i procesu

Ocena wymaga jednej poprawnie zakończonej tury, braku błędu sesji, właściwych
wywołań narzędzi i ich potwierdzeń `tool_end` z `success=True`, tym samym `run_id`
i `turn_id`, a także właściwego końcowego `app_state`:

- Muzyka: potwierdzone `get_track_list` zawierające Christmas Eve przed dokładnie
  jednym `select_track(title="Christmas Eve")`, bez dodatkowych przełączeń muzyki;
  końcowo Christmas Eve i `is_playing=True`.
- Telefon: dokładnie jedno `call_contact(name="Robert Lewandowski", number_type="mobile")`
  i aktywne połączenie z tym kontaktem.
- Nawigacja: dokładnie jedno `navigate_to`, właściwy kanoniczny cel i brak przystanków.

To ocena stanu prototypu, bez potwierdzenia rzeczywistego połączenia, trasy drogowej
lub akustycznego odtwarzania. Nie ocenia wszystkich niezamówionych operacji poza
badaną funkcją. Samo pobranie listy, deklaracja LLM lub status completed nie wystarcza.

Limit każdej próby, w tym rozgrzewania, wynosi 300 s. Po błędzie lub timeout
runner zapisuje wynik i kontynuuje. **Po timeout również odczytuje istniejący
raport**, zamiast tracić zapisany efekt i pomiary. W pojedynczym wyniku:

- `task_success`: ocena zadania z poprawnego raportu; `null`, jeśli nie można ocenić.
- `timed_out` i `returncode`: wynik wykonania procesu.
- `report_complete`: czy odczytany raport ma zapisany koniec sesji.
- `success`: poprawne zadanie oraz wyjście procesu kodem 0 bez timeoutu.

`success_count` i success rate liczą ścisłe sukcesy wśród wykonanych prób;
błędy i timeouty są w mianowniku. `task_success_count`, `task_assessed_count` i
`timeout_count` pokazują osobno poprawność efektu, pokrycie oceny i timeouty.
Jeśli połączenie zostało wykonane, ale proces się zawiesił, `task_success` może
wynosić true przy `success=false`. Pomiary poprawnego raportu pozostają w summary.
Oryginalne raporty sesji nie są zmieniane.

Kod zakończenia: `0` dla wszystkich 108 sukcesów i udanego rozgrzewania czterech
wariantów; `1` dla niepowodzenia którejkolwiek próby lub rozgrzewania;
`2` dla błędu kompletności nagrań przed startem. Starsze foldery pilotażu
pozostają bez zmian. Wyniki tej serii dotyczą dziewięciu konkretnych nagrań;
trzy powtórzenia nie są trzema nowymi wypowiedziami.
