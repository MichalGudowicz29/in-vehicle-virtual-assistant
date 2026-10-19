```mermaid
sequenceDiagram
    actor U as Użytkownik
    participant W as VoiceWorker + ASR<br/>(QThread)
    participant R as ConversationRunner
    participant A as Assistant + LLM
    participant G as LangGraph
    participant C as CarSystem
    participant Q as QML<br/>(główny wątek)
    participant T as TTS
    participant L as EventLogger

    U->>W: komenda głosowa
    W->>R: tekst (ASR)
    R->>A: tekst + turn_id
    A->>A: wybór narzędzia (LLM)

    alt akcja (play_pause, call_contact, navigate_to...)
        A->>G: intent + action + payload
        G->>C: wywołanie kontrolera domeny
        C-->>Q: sygnał (np. isCallingChanged)
        C-->>G: rezultat
        G-->>A: success + action + dane
    else odczyt (get_track_list, get_contacts, get_places_list)
        A->>C: zapytanie o stan
        C-->>A: dane
    end

    A-->>R: odpowiedź tekstowa
    R->>T: tekst
    T-->>U: mowa
    A--)L: eventy tooli
    R--)L: eventy
```