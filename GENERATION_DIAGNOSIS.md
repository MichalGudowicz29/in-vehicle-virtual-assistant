# Diagnoza generacji — 16 listopada 2026

Poniższa analiza historyczna dotyczy raportów
`logs/eksperymenty/seria_ABCD_20261113_142106_018432`.
Odczytano 112 raportów sesji, w tym 4 warmupy. Nie zmieniano historycznych
raportów i nie uruchamiano nowych modeli. Wyniki poniżej pochodzą z logów,
a nie z ponowienia prób po poprawce.

## Dokładnie 4096 tokenów

W sześciu odpowiedziach suma `input_tokens + output_tokens` wynosi 4096.
Żadna odpowiedź nie ma 4096 samych tokenów wyjściowych.

| Wariant i przypadek | Liczba prób | Wejście | Wyjście |
| --- | ---: | ---: | ---: |
| A / Nawigacja / audio 1 | 3 | 2195 | 1901 |
| A / Nawigacja / audio 3 | 3 | 2187 | 1909 |

W każdym przypadku model nie wywołał narzędzi, zwrócił pustą odpowiedź,
cel pozostał pusty, a dawny `agent_end` oznaczał sukces wykonania agenta.
Nie zapisano `done_reason`, aktywnego kontekstu ani efektywnego limitu generacji.
Zbieżność sumy z 4096 jest przesłanką do diagnozy, ale nie dowodem konkretnego
limitu. Obecnie pusta odpowiedź bez wykonania planu powoduje błąd agenta.

## XML po poprawnym wykonaniu akcji

Dziewięć prób zakończyło się komunikatem:

```text
XML syntax error on line 2: unexpected end element </function> (status code: -1)
```

| Wariant i przypadek | Liczba prób | Poprawna akcja przed błędem |
| --- | ---: | --- |
| C / Muzyka / audio 3 | 3 | `select_track`, odtwarzanie włączone |
| C / Nawigacja / audio 3 | 3 | `navigate_to`, cel ustawiony |
| D / Nawigacja / audio 3 | 3 | `navigate_to`, cel ustawiony |

Błąd dotyczył trzeciego żądania LLM, po udanej akcji. `usage` tego żądania
nie jest dostępne. Logi nie zawierają surowego XML ani wystarczających danych,
by przypisać błąd konkretnej warstwie parsera. Nowy mechanizm zakończenia
usuwa potrzebę dodatkowego żądania po wykonaniu całego planu. Testy z modelem
zastępczym potwierdzają brak takiego żądania; nie są dowodem wyników na modelach
Qwen z tamtej serii.

## Co zapisuje obecna wersja

`llm_start.generation_settings` rozróżnia ustawienia żądane przez klienta
(`source=client_requested`) od nieustalonych efektywnych ustawień serwera
(`effective=unknown`). `null` pozostawia wartość modelowi/serwerowi. Raport
nie udaje, że zna domyślne wartości z procesu Ollamy.

`llm_end` zachowuje `done_reason`, `response_metadata`, liczbę znaków odpowiedzi
i przechwyconego reasoning. Nie zapisuje tekstu reasoning. Brak przechwycenia
ma wartość `null`, a przechwycony pusty tekst — 0. Zainstalowany klient
`langchain-ollama 1.1.0` przy `reasoning=None` może pominąć oddzielne pole
`message.thinking`; brak tego pola w callbacku nie dowodzi braku myślenia.

Domyślne `num_ctx`, `num_predict` i tryb reasoning pozostawiono bez zmian.
Można je jawnie ustawić przez `OLLAMA_NUM_CTX`, `OLLAMA_NUM_PREDICT`
i `OLLAMA_REASONING` dopiero po zebraniu danych diagnostycznych.

## Następna próba diagnostyczna na komputerze Ubuntu

1. Zapisz wersję Ollamy, model/digest i jego konfigurację, a dla załadowanego
   modelu aktywny kontekst (`ollama --version`, `ollama ps`, API `/api/ps`).
2. Ponów pojedynczy przypadek A / Nawigacja / audio 1 bez zmiany generacji.
   Sprawdź `done_reason`, tokeny i długości przechwyconych treści w nowym raporcie.
3. Jeżeli nadal wystąpi XML, zachowaj również log serwera i odpowiedź API.
   Oddziel próbę z nowym sterowaniem planem od porównania parametrów generacji.

Nie da się odtworzyć konfiguracji historycznego serwera z aktualnego lokalnego
runtime. Zmiany promptu, planowania i kończenia wykonania oznaczają też zmianę
warunków względem poprzedniej serii 108 prób.

## Aktualny krok po serii 20261116

Analiza serii `seria_ABCD_20261116_131324_326522` w rejestrze projektu
potwierdza 12 generacji `done_reason=length`; D osiągnął 21/27, z ucięciami
w Muzyka / audio 1. To nowsze dane niż powyższa diagnoza sumy 4096.
Następna próba dotyczy tego przypadku D z jawnym `OLLAMA_REASONING=false`,
bez jednoczesnego strojenia kontekstu i limitu generacji.

Lokalny raport `logs/diagnostics/D_music_audio1_reasoning_false_20261116/`
`session_20261116_171715_58907a1a.json` ma `ended_at=null`, aktywną turę
i brak wyniku drugiego żądania. Potwierdza przesłanie `reasoning=false`
oraz poprawny plan, ale nie wykonanie polecenia ani skuteczność konfiguracji.
Nie traktować go jako sukcesu lub końcowego wyniku porównania.

Tryb ręczny domyślnie wyłącza reasoning, chyba że podano wartość jawną.
Tryb `--experiment` nadal dziedziczy ustawienia z konfiguracji/serwera.
Polecenie pojedynczej próby, kryteria oraz odbiór sprzętu: [ACCEPTANCE.md](ACCEPTANCE.md).
