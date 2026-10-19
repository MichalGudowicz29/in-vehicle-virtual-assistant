# Architektura aplikacji — pełny przepływ

Diagram pokazuje aktualną architekturę aplikacji: dwa sposoby sterowania
samochodem (głos i dotyk), wspólny `CarSystem`, wykonanie akcji przez
LangGraph, aktualizację interfejsu QML oraz rejestrowanie sesji badawczej.

```mermaid
flowchart TB
    User([Użytkownik])
    Mic([Mikrofon])
    AudioFile([Plik audio\nprzyszły runner datasetu])
    Speaker([Głośnik])

    subgraph Voice[Ścieżka głosowa — osobny QThread]
        ASR[asr.py\nVOSK obecnie\nwymienny moduł ASR]
        Worker[VoiceWorker\npętla mikrofonu]
        Runner[ConversationRunner\nASR → Assistant → TTS]
        Assistant[Assistant\ncreate_agent + pamięć sesji]
        LLM[OpenAI gpt-4o-mini\nrozumienie polecenia]
        TTS[tts.py\nSupertonic + osobny worker]
    end

    subgraph Evaluation[Ewaluacja]
        Logger[EventLogger\neventy + run_id + turn_id]
        JSONL[(evaluation/runs\nrun_id.jsonl)]
    end

    subgraph Tools[Narzędzia Assistanta]
        MusicRead[Odczyt muzyki\nget_track_list / search_track]
        ContactsRead[Odczyt kontaktów\nget_contacts]
        PlacesRead[Odczyt miejsc\nget_places_list]
        MusicAction[Akcje muzyczne\nplay_pause / next / previous / select]
        ContactAction[Akcja kontaktów\ncall_contact]
        NavigationAction[Akcje nawigacji\nnavigate_to / add_stop]
    end

    subgraph Graph[LangGraph — wykonanie akcji]
        InputState[HMIState\nintent + action + payload]
        Router[router\nwybór domeny]
        MusicNode[music_node]
        ContactsNode[contacts_node]
        NavigationNode[navigation_node]
        UnknownNode[unknown]
        Result[result\nsuccess + action + dane]
    end

    subgraph Car[CarSystem — wspólny stan aplikacji]
        CarSystem[CarSystem\nobiekt wystawiony do QML]
        MusicController[MusicController\npygame + isPlaying + tracks]
        ContactController[ContactController\ncontacts + isCalling]
        NavigationController[NavigationController\ndestination + stops + routePoints]
    end

    subgraph UI[Qt/QML — główny wątek]
        Main[Main.qml\nApplicationWindow + StackView]
        Home[HomeScreen.qml]
        Music[MusicScreen.qml]
        Contacts[ContactsScreen.qml]
        Navigation[NavigationScreen.qml]
        Map[MapScreen.qml\nQt Location + OSM]
        CallOverlay[CallOverlay.qml\nvisible = car.contacts.isCalling]
        RouteQuery[RouteQuery + RouteModel\nOSRM routing]
        MapRoute[MapRoute\ntrasa na mapie]
    end

    User --> Mic
    Mic --> ASR
    ASR -->|tekst| Runner
    Worker -->|nasłuchiwanie| Runner
    AudioFile -.->|transcribe callable| Runner
    Runner -->|tekst i turn_id| Assistant
    Assistant --> LLM
    LLM -->|wybór narzędzia| MusicRead
    LLM -->|wybór narzędzia| ContactsRead
    LLM -->|wybór narzędzia| PlacesRead
    LLM -->|wybór narzędzia| MusicAction
    LLM -->|wybór narzędzia| ContactAction
    LLM -->|wybór narzędzia| NavigationAction

    MusicRead -.-> MusicController
    ContactsRead -.-> ContactController
    PlacesRead -.-> NavigationController

    MusicAction -->|intent + action + payload| InputState
    ContactAction -->|intent + action + payload| InputState
    NavigationAction -->|intent + action + payload| InputState
    InputState --> Router
    Router -->|music| MusicNode
    Router -->|contacts| ContactsNode
    Router -->|navigation| NavigationNode
    Router -->|inna domena| UnknownNode
    MusicNode -->|car.music| MusicController
    ContactsNode -->|car.contacts| ContactController
    NavigationNode -->|set_destination / add_stop| NavigationController
    MusicController --> Result
    ContactController --> Result
    NavigationController --> Result
    UnknownNode --> Result
    Result -->|wynik toola| Assistant
    Assistant -->|odpowiedź tekstowa| Runner
    Runner --> TTS
    TTS --> Speaker
    Runner -->|eventy| Logger
    Assistant -->|eventy tooli| Logger
    Logger --> JSONL

    Main --> Home
    Main --> Music
    Main --> Contacts
    Main --> Navigation
    Main --> Map
    Main --> CallOverlay
    Main -.->|context property: car| CarSystem
    CarSystem --> MusicController
    CarSystem --> ContactController
    CarSystem --> NavigationController
    Music -.->|akcje i właściwości| MusicController
    Contacts -.->|kontakty i call_contact| ContactController
    Navigation -.->|akcje przystanków| NavigationController
    ContactController -.->|isCallingChanged + currentContactName| CallOverlay
    NavigationController -.->|routePointsChanged| Map
    NavigationController -.->|mapScreenRequested| Main
    Map --> RouteQuery
    RouteQuery -->|OSRM| MapRoute
    MapRoute --> Map
    Home -.->|push| Main
```

## Główne ścieżki

### 1. Polecenie głosowe

```text
mikrofon
  ↓
asr.py (VOSK; moduł wymienny)
  ↓ tekst
VoiceWorker
  ↓ listen(stop_event)
ConversationRunner
  ↓ handle_text(turn_id)
Assistant + model językowy
  ↓ wybór toola
LangGraph (dla akcji zmieniających stan)
  ↓
CarSystem / kontroler
  ↓ wynik
Assistant
  ↓
TTS → głośnik
```

`VoiceWorker` działa w osobnym `QThread`, a interfejs Qt/QML pozostaje w
głównym wątku. `ConversationRunner` wykonuje każdą turę niezależnie od źródła
audio: `VoiceWorker` przekazuje mu mikrofon, a przyszły runner datasetu poda
funkcję ASR dla pliku. `EventLogger` zapisuje eventy do
`evaluation/runs/<run_id>.jsonl`. Moduł ASR jest odseparowany od Assistanta:
jego odpowiedzialność kończy się na zwróceniu tekstu.

### 2. Narzędzia Assistanta

Narzędzia odczytujące dane pobierają stan bezpośrednio z kontrolera:

```text
get_track_list()  → car.music.tracks
search_track()    → car.music.tracks
get_contacts()    → car.contacts.contacts
get_places_list() → car.navigation.places_list
```

Narzędzia wykonujące akcje przechodzą przez graph:

```text
play_pause / next_track / previous_track / select_track
call_contact
navigate_to / add_stop
        ↓
graph.invoke({intent, action, payload})
```

### 3. LangGraph

```text
START
  ↓
router
  ├── music      → music_node      → car.music
  ├── contacts   → contacts_node   → car.contacts
  ├── navigation → navigation_node → car.navigation
  └── unknown    → wynik błędu
  ↓
END
```

Stan wejściowy akcji ma postać:

```python
{
    "intent": "navigation",
    "action": "add_stop",
    "payload": {
        "address": "ul. Stacyjna 10, Szczecin",
    },
}
```

Node zwraca wynik do Assistanta:

```python
{
    "result": {
        "success": True,
        "action": "add_stop",
        "stop": "ul. Stacyjna 10, Szczecin",
    },
}
```

### 4. Nawigacja i mapa

`NavigationController` przechowuje stały punkt startowy, cel oraz listę
przystanków. Każdy adres jest wyszukiwany w testowej bazie miejsc i ma własne
współrzędne.

```text
start → stop 1 → stop 2 → destination
                 ↓
        routePointsChanged
                 ↓
MapScreen.qml
                 ↓
RouteQuery + RouteModel
                 ↓
OSM / OSRM
                 ↓
MapRoute na mapie
```

Cel można ustawić głosem przez `navigate_to(street, city, number)`, a
przystanek dodać głosem przez `add_stop(street, city, number)` albo dotykiem
w `MapScreen.qml`, wpisując dokładny adres testowy. Zmiana celu emituje także
`mapScreenRequested`, dzięki czemu `Main.qml` otwiera ekran mapy.

### 5. Sterowanie dotykowe i CallOverlay

`Main.qml` zarządza ekranami przez `StackView`:

```text
HomeScreen
  ├── MusicScreen
  ├── ContactsScreen
  ├── NavigationScreen
  └── MapScreen
```

`CallOverlay.qml` jest dzieckiem `ApplicationWindow`, a nie konkretnego
ekranu. Dlatego pozostaje widoczny podczas przechodzenia między ekranami,
dopóki `car.contacts.isCalling` ma wartość `true`. Przycisk rozłączenia
wywołuje `car.contacts.end_call()`, zmienia stan na `false` i ukrywa overlay.

Kontrolery emitują sygnały i udostępniają właściwości QML:

```text
MusicController      → MusicScreen.qml
ContactController    → ContactsScreen.qml + CallOverlay.qml
NavigationController → MapScreen.qml
```

## Podział odpowiedzialności

```text
ASR:
    zamienia mowę na tekst

VoiceWorker:
    przekazuje mikrofon do ConversationRunner w pętli głosowej

ConversationRunner:
    wykonuje ASR, Assistanta i TTS dla jednej tury

EventLogger:
    zapisuje eventy tury do pliku JSONL

Assistant / model:
    rozumie polecenie i wybiera narzędzie

Tool:
    odczytuje stan albo tworzy intent, action i payload

Graph:
    wybiera domenę i uruchamia właściwy node

Node:
    wywołuje kontroler

Controller:
    przechowuje stan i wykonuje operację

QML:
    pokazuje stan i obsługuje sterowanie dotykowe

TTS:
    zamienia odpowiedź Assistanta na mowę
```

## Wielowątkowość

```text
główny wątek Qt:
    QApplication + QML + CarSystem + kontrolery

osobny QThread:
    VoiceWorker + mikrofon + Assistant

osobny daemon Thread:
    tts.py worker + synteza i odtwarzanie audio
```

Metody kontrolerów, które mogą zostać wywołane z wątku Assistanta, przekazują
zmianę stanu do właściwego wątku Qt przez `QMetaObject.invokeMethod` i
`QueuedConnection`.

## Obecny stan ASR

Aktualnie `asr.py` korzysta z VOSK. Interfejs aplikacji został rozdzielony tak,
aby późniejsza podmiana na Whisper wymagała zmiany modułu ASR, a nie graphu,
kontrolerów ani ekranów QML.
