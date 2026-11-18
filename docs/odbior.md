# Odbiór prototypu na urządzeniu

Testy automatyczne (`uv run pytest`) nie zastępują sprawdzenia mikrofonu, głośników
i dotyku. Odbiór robi się na docelowym komputerze z działającą Ollamą i modelami
przygotowanymi przez `uv run python -m experiments.prepare_models`.
Najlepiej z mikrofonem wbudowanym albo przewodowym, nie ze słuchawek Bluetooth.

## 1. Seria głosowa z nagrań (około 15–30 min)

```bash
uv run python -m experiments.prepare_models --check
uv run python -m experiments.runner
```

Wynik: `logs/eksperymenty/seria_<czas>/zad*/summary.txt` (skuteczność i czasy etapów).
Zapisz też wersję Ollamy i identyfikator modelu (`ollama --version`, `ollama list`).

## 2. Odbiór głosu i dotyku (około 10 min)

Uruchom `uv run python main.py`. Każdy wiersz sprawdź przyciskiem „Mów” i dotykiem;
zapisz wynik oraz nazwę raportu z `logs/sessions/`.

| Próba | Co potwierdzić |
| --- | --- |
| Telefon | „Zadzwoń do Roberta” dzwoni do jedynego Roberta; „Zadzwoń do Anny” pyta o numer (mobilny/służbowy); nakładka połączenia, zakończenie przyciskiem. Połączenie jest symulowane. |
| Muzyka | „Włącz Christmas Eve” i „Włącz coś świątecznego” uruchamiają właściwy utwór; pauza i wznowienie; dwukrotna pauza głosem nie wznawia; następny i poprzedni utwór zgadzają się z ekranem i dźwiękiem. |
| Nawigacja | „Jedziemy na Żołnierską” ustawia jedyny zapisany adres; dodanie i usunięcie przystanku; wyczyszczenie trasy; ekran pokazuje aktualny stan. |
| Niewykonanie | Dla polecenia, którego nie da się wykonać, pojawia się baner; zamknięcie i wygaśnięcie działają; następne polecenie oraz dotyk nadal działają. Pytanie o doprecyzowanie nie jest takim błędem. |

Tor błędu: `VoiceWorker.userMessage` → `SessionControls.showUserMessage` (wątek GUI)
→ właściwość `userMessage` → baner w `Main.qml`. Nieudane polecenie nie kończy nasłuchu,
a tura zostaje zapisana w raporcie jako błędna.

Po odbiorze zapisz commit aplikacji, wersje runtime i model wraz z raportami.
