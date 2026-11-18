# Odbiór prototypu na urządzeniu

## Stan i zakres

Istniejący tor błędu: `VoiceWorker.userMessage` → slot `SessionControls.showUserMessage`
w wątku GUI → właściwość Qt `userMessage` → baner `Main.qml`.
Nieukończone polecenie i limit grafu nie kończą nasłuchu mikrofonowego;
nieudana tura pozostaje błędem w raporcie. Nie dodano automatycznego ponawiania
akcji ani nowego wywołania LLM do utworzenia komunikatu.

Testy kontrolowane nie zastępują odbioru mikrofonu, głośników i dotyku.
Konfiguracja docelowa pozostaje kandydatem do sprawdzenia na urządzeniu:
Whisper small, Qwen3.5 4B, temperature=0, reasoning=false; kontekst i limit
generacji dziedziczone z serwera, ich wartości trzeba zanotować.

## Jedna próba D / Muzyka / audio 1

Uruchom z katalogu repo na docelowym urządzeniu (z działającą Ollamą i pobranymi modelami):

```bash
ollama --version
ollama show qwen3.5:4b
OLLAMA_MODEL=qwen3.5:4b OLLAMA_REASONING=false OLLAMA_NUM_CTX= OLLAMA_NUM_PREDICT= uv run python main.py --experiment --asr whisper-small --audio-file assets/voice/Muzyka/1.mp3 --report-dir logs/diagnostics/D_music_audio1_reasoning_false_acceptance
ollama ps
```

Puste zmienne kontekstu i generacji celowo delegują je serwerowi, również gdy
`.env` zawiera inne wartości. Zapisz aktywny kontekst i identyfikator modelu.
Wynik sprawdź istniejącym kryterium runnera:

```bash
uv run python - <<'PY'
import json
from pathlib import Path
from experiments.evaluate import evaluate_session

reports = sorted(Path('logs/diagnostics/D_music_audio1_reasoning_false_acceptance').glob('session_*.json'))
if not reports:
    raise SystemExit('Brak raportu próby.')
path = reports[-1]
data = json.loads(path.read_text())
ok, reason = evaluate_session(data, task=1)
print(path, ok, reason)
print('Raport końcowy:', data.get('ended_at') is not None)
for event in data['events']:
    if event['type'] == 'llm_start':
        print('Ustawienia:', event.get('generation_settings'))
    elif event['type'] == 'llm_end':
        print('Generacja:', event.get('done_reason'), event.get('usage'))
raise SystemExit(0 if ok and data.get('ended_at') is not None else 1)
PY
```

Wymagane: raport końcowy, sukces kryterium muzyki, pobranie biblioteki przed
jednym wyborem Christmas Eve, odtwarzanie włączone oraz brak `length`.
Sam poprawny plan nie potwierdza sukcesu. Lokalny raport
`session_20261116_171715_58907a1a` jest cząstkowy (`ended_at=null`, tura aktywna)
i nie zamyka tej próby. Nie porównuj jego czasu z serią Ubuntu jako wyniku
tego samego środowiska.

## Odbiór głosu i dotyku — około 10 minut

Uruchom `OLLAMA_MODEL=qwen3.5:4b OLLAMA_REASONING=false uv run python main.py`.
Każdy wiersz sprawdź głosem i odpowiednimi przyciskami; zapisz wynik oraz nazwę raportu.

| Próba | Co potwierdzić |
| --- | --- |
| Muzyka | Wybór tytułu uruchamia właściwy utwór; pauza i wznowienie działają; dwukrotna pauza głosem nie wznawia, dwukrotne wznowienie nie zatrzymuje; następny i poprzedni utwór odpowiadają ekranowi i dźwiękowi. |
| Telefon | Wybór właściwego kontaktu i numeru, widoczna nakładka połączenia, zakończenie przyciskiem. To symulacja, bez rzeczywistego telefonu. |
| Nawigacja | Właściwy cel, dodanie i usunięcie przystanku, wyczyszczenie trasy; ekran pokazuje aktualny stan. |
| Niewykonanie | Dla rzeczywistego błędu nieukończenia lub limitu grafu pojawia się baner; zamknięcie i wygaśnięcie działają; następne poprawne polecenie oraz dotyk nadal działają. Pytanie o doprecyzowanie nie jest takim błędem. |

Nie wywołuj błędu przez psucie plików muzyki. Kontrolowane testy odtwarzają
nieukończenie i limit grafu; jeśli model nie wywoła ich podczas odbioru,
oznacz próbę błędu na urządzeniu jako niewykonaną.

Po odbiorze zapisz commit aplikacji, wersje runtime, model/digest i ustawienia
serwera wraz z raportami. Dopiero udana próba i odbiór pozwalają zamrozić wersję.
