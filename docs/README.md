# Dokumentacja projektu — In-Vehicle Virtual Assistant

Aplikacja demonstracyjna samochodowego asystenta głosowego. Użytkownik
może sterować muzyką, kontaktami i nawigacją głosem albo dotykiem przez interfejs
QML.

Architektura

```text
ASR rozpoznaje mowę
Assistant rozumie polecenie
Tool przekazuje akcję
Graph wybiera node
Node wywołuje kontroler
Controller zmienia stan
QML pokazuje stan
TTS odpowiada głosem
```

Pełny diagram znajduje się w [architecture-flow.md](architecture-flow.md).

## 1. Uruchomienie

Wymagane są Python, `uv`, dostęp do mikrofonu i głośników oraz plik `.env` z
kluczem modelu:

```env
OPENAI_API_KEY=...
```

Uruchomienie:

```bash
uv sync
uv run python main.py
```

Testy:

```bash
uv run pytest
```

## 2. Struktura projektu

```text
.
├── main.py                    punkt startowy aplikacji Qt
├── asr.py                     rozpoznawanie mowy
├── tts.py                     synteza mowy
├── voice_worker.py            pętla ASR → Assistant → TTS
├── assistant.py               agent i definicje tools
├── Main.qml                   główny QML i StackView
│
├── CarSystem/
│   ├── car_system.py          obiekt wystawiony do QML
│   ├── music_controller.py    stan i akcje muzyczne
│   ├── contact_controller.py  kontakty i połączenia
│   └── navigation_controller.py cel i sygnał mapy
│
├── graph/
│   ├── state.py               typ wspólnego stanu grafu
│   ├── builder.py             budowa i kompilacja grafu
│   ├── router.py              wybór domeny
│   └── nodes/                 wykonanie akcji domenowych
│
├── qml/
│   ├── HomeScreen.qml
│   ├── MusicScreen.qml
│   ├── ContactsScreen.qml
│   ├── NavigationScreen.qml
│   └── MapScreen.qml
│
└── tests/                     testy jednostkowe i integracyjne
```

## 3. Start aplikacji i połączenie Python–QML

`main.py` tworzy jeden wspólny obiekt `CarSystem`:

```python
car = CarSystem()
```

Następnie wystawia go do QML pod nazwą `car`:

```python
engine.rootContext().setContextProperty("car", car)
```

Od tego momentu każdy ekran QML może korzystać z:

```qml
car.music
car.contacts
car.navigation
```

`main.py` tworzy również `VoiceWorker` i przenosi go do osobnego `QThread`,
żeby nasłuchiwanie mikrofonu i obsługa agenta nie blokowały interfejsu.

## 4. `CarSystem` — centralny obiekt HMI

`CarSystem` jest kontenerem kontrolerów. Sam nie wykonuje całej logiki muzyki,
kontaktów ani nawigacji. Udostępnia kontrolery jako stałe właściwości Qt:

```text
car.music       → MusicController
car.contacts    → ContactController
car.navigation  → NavigationController
```

Dzięki temu Python i QML korzystają z tych samych obiektów i widzą ten sam stan.

## 5. Kontrolery

### `MusicController`

Przechowuje:

- listę `tracks`;
- indeks `currentTrackIndex`;
- stan `isPlaying`.

Udostępnia akcje:

```python
play_pause()
next_track()
previous_track()
select_track(title)
```

Zmiana stanu emituje sygnały `isPlayingChanged`, `currentTrackChanged` albo
`tracksChanged`. QML może dzięki temu automatycznie odświeżyć widok.

### `ContactController`

Przechowuje listę kontaktów w postaci słowników:

```python
{
    "name": "Anna Kowalska",
    "mobile": "502345678",
    "work": "223456789",
}
```

Udostępnia:

```python
contacts
call_contact(contact_name, contact_type)
set_contacts(contacts)
```

`contact_type` powinien być `mobile` albo `work`. Jeśli kontakt ma dwa numery,
agent musi najpierw zapytać użytkownika, który wybrać.

### `NavigationController`

Przechowuje właściwość:

```python
destination
```

Akcja:

```python
set_destination(address)
```

Po ustawieniu celu emituje `destinationChanged` i `mapScreenRequested`. `Main.qml`
nasłuchuje `mapScreenRequested` i otwiera `MapScreen`.

## 6. Voice pipeline

Pełny przepływ głosowy wygląda tak:

```text
mikrofon
  ↓
asr.listen()
  ↓ tekst
VoiceWorker
  ↓ handle_text(text)
Assistant
  ↓ wybór toola
tool
  ↓ wynik tekstowy
TTS
  ↓
głośnik
```

`VoiceWorker` nie powinien znać szczegółów kontaktów ani muzyki. Przekazuje
tekst do `Assistant` i odtwarza otrzymaną odpowiedź.

## 7. Assistant i tools

`Assistant` jest warstwą rozumienia języka. Model językowy wybiera narzędzie
na podstawie wypowiedzi użytkownika.

### Tools odczytujące dane

Te narzędzia pobierają dane, ale nie zmieniają stanu przez graf:

```text
get_contacts()
get_track_list()
search_track(query)
```

### Tools wykonujące akcję

Narzędzia delegują wykonanie do grafu:

```text
play_pause()
next_track()
previous_track()
select_track(title)
call_contact(name, number_type)
navigate_to(address)
```

Przykładowy tool muzyczny wywołuje logicznie:

```python
self._execute_graph_action(
    "music",
    "play_pause",
    {},
)
```

## 8. Graph — warstwa wykonawcza

Agent rozumie język, a graf wykonuje już wybraną akcję w przewidywalny sposób.

### Stan grafu

```python
{
    "intent": "contacts",
    "action": "call_contact",
    "payload": {
        "name": "Anna Kowalska",
        "number_type": "work",
    },
}
```

Znaczenie pól:

- `intent` — domena: `contacts`, `music` albo `navigation`;
- `action` — konkretna operacja;
- `payload` — argumenty operacji;
- `route` — decyzja routera;
- `result` — wynik wykonania.

### Przepływ grafu

```text
START
  ↓
router
  ├── contacts_node    → car.contacts
  ├── music_node       → car.music
  ├── navigation_node  → car.navigation
  └── unknown_node
  ↓
END
```

Każdy node obsługuje jedną domenę. Node nie zna ASR, TTS ani QML. Wywołuje
metodę kontrolera i zwraca wynik:

```python
{
    "success": True,
    "action": "play_pause",
}
```

## 9. QML i nawigacja ekranów

`Main.qml` jest głównym kontenerem interfejsu. Używa `StackView` i przełącza
ekrany:

```text
HomeScreen
  ├── MusicScreen
  ├── ContactsScreen
  ├── NavigationScreen
  └── MapScreen
```

Przyciski na `HomeScreen` wykonują `stackView.push(...)`. Ekrany emitują
`backClicked()`, a `Main.qml` wykonuje `stackView.pop()`.

### Połączenia ekranów z kontrolerami

```text
MusicScreen.qml
  → car.music.isPlaying
  → car.music.currentTrackIndex
  → car.music.play_pause()
  → car.music.next_track()
  → car.music.previous_track()

ContactsScreen.qml
  → car.contacts.contacts
  → car.contacts.call_contact(name, type)

MapScreen.qml
  → pokazuje mapę QtLocation

Main.qml
  → car.navigation.mapScreenRequested
  → otwiera MapScreen
```

Ważne: sygnał `mapScreenRequested` otwiera ekran mapy, ale obecna wersja
`MapScreen.qml` nie rysuje jeszcze pinezki na podstawie adresu. Do tego trzeba
później dodać geokodowanie adresu albo testowe współrzędne.

## 10. Wielowątkowość

Interfejs Qt/QML działa w głównym wątku. `VoiceWorker` działa w osobnym wątku.
Kontrolery należą do głównego wątku, dlatego mają wzorzec:

```text
metoda publiczna wywołana z innego wątku
  ↓
QMetaObject.invokeMethod(..., QueuedConnection)
  ↓
prywatna metoda _...
  ↓
zmiana stanu w wątku kontrolera
```

Przykład dla muzyki:

```python
play_pause()  →  _play_pause()
```

Publiczny slot sprawdza wątek i przekazuje wykonanie do bezpiecznej metody
wewnętrznej.

## 11. Testy

### Testy kontrolerów

```text
tests/test_car_system.py
tests/test_contact_controller.py
```

Sprawdzają stan muzyki, nawigacji i kontaktów.

### Testy grafu

```text
tests/test_graph.py
tests/test_assistant_graph.py
```

Sprawdzają routing, node’y, wynik akcji i połączenie `Assistant → Graph`.

### Test ASR

```text
tests/test_asr.py
```

Sprawdza podstawowe zachowanie modułu rozpoznawania mowy.

Uruchomienie wszystkich testów:

```bash
uv run pytest
```

## 12. Zasady rozbudowy

Przy dodawaniu nowej funkcji trzymaj się tej kolejności:

1. Dodaj stan i metodę do właściwego kontrolera.
2. Dodaj lub zmień slot Qt i sygnał, jeśli QML ma widzieć zmianę.
3. Dodaj node albo akcję w istniejącym node’ie.
4. Dodaj tool w `Assistant`.
5. Dodaj test kontrolera, node’a i przepływu Assistant → Graph.
6. Dopiero potem dodaj lub zmień ekran QML.

Nie wkładaj logiki biznesowej do QML ani do prompta. Prompt opisuje zasady
decyzji agenta, ale poprawność wykonania musi być zabezpieczona w kodzie i
testach.

