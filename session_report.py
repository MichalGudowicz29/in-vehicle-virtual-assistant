"""Local session events and a human-readable report; all durations are monotonic."""

import json
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from statistics import mean
from threading import RLock
from time import perf_counter
from uuid import uuid4


PAIRS = {
    'Czas mowy': ('speech_start', 'speech_end'),
    'Koniec mowy → transkrypcja': ('speech_end', 'transcription_ready'),
    'Transkrypcja → start agenta': ('transcription_ready', 'agent_start'),
    'Transkrypcja → pierwsze żądanie': ('transcription_ready', 'llm_start'),
    'Łączny czas agenta na turę': ('agent_start', 'agent_end'),
    'Synteza TTS': ('tts_start', 'tts_end'),
    'Koniec agenta → start audio': ('agent_end', 'audio_start'),
    'Koniec mowy → start audio': ('speech_end', 'audio_start'),
    'Odtwarzanie': ('audio_start', 'audio_end'),
    'Cała tura': ('speech_start', 'turn_end'),
}
LABELS = {
    'speech_detected': 'Vosk wykrył częściową wypowiedź',
    'speech_start': 'Początek mowy użytkownika (estymacja Vosk)',
    'speech_end': 'Koniec mowy (estymacja Vosk)',
    'transcription_ready': 'Transkrypcja gotowa',
    'agent_start': 'Start agenta', 'agent_end': 'Koniec agenta',
    'llm_start': 'Żądanie do LLM', 'llm_end': 'Odpowiedź LLM',
    'tool_start': 'Start narzędzia', 'tool_end': 'Koniec narzędzia',
    'tts_start': 'Start syntezy TTS', 'tts_end': 'Koniec syntezy TTS',
    'audio_start': 'Start odtwarzania', 'audio_end': 'Koniec odtwarzania',
    'turn_end': 'Koniec tury', 'tts_error': 'Błąd TTS',
    'screen_change': 'Zmiana ekranu',
    'asr_warning': 'Ostrzeżenie ASR', 'session_error': 'Błąd sesji',
    'touch_start': 'Dotyk — początek operacji',
    'touch_end': 'Dotyk — koniec operacji', 'touch': 'Dotyk',
}
STATUSES = {'completed': 'zakończona', 'failed': 'błędna', 'interrupted': 'przerwana'}


class SessionReport:
    def __init__(self):
        self.started_at = datetime.now().astimezone()
        self.started_timer = perf_counter()
        self.session_id = f'session_{self.started_at:%Y%m%d_%H%M%S}_{uuid4().hex[:8]}'
        self.events = []
        self.turns = []
        self._next_turn = 1
        self._lock = RLock()
        self._ended_at = None
        self._duration = None

    def begin_turn(self):
        with self._lock:
            turn_id = self._next_turn
            self._next_turn += 1
            self.turns.append({'id': turn_id, 'status': 'active'})
            return turn_id

    def emit(self, event, *, turn_id=None, at=None, **data):
        with self._lock:
            self.events.append({
                'type': event, 'time_s': (perf_counter() if at is None else at) - self.started_timer,
                'turn_id': turn_id, **deepcopy(data),
            })

    def end_turn(self, turn_id, status):
        if status not in STATUSES:
            raise ValueError(f'Unknown turn status: {status}')
        with self._lock:
            turn = next(t for t in self.turns if t['id'] == turn_id)
            if turn['status'] == 'active':
                turn['status'] = status
                self.emit('turn_end', turn_id=turn_id, status=status)

    def discard_empty_turn(self, turn_id):
        with self._lock:
            speech_events = {'speech_detected', 'speech_start', 'speech_end', 'transcription_ready'}
            if not any(e['turn_id'] == turn_id and e['type'] in speech_events for e in self.events):
                for event in self.events:
                    if event['turn_id'] == turn_id:
                        event['turn_id'] = None
                self.turns = [t for t in self.turns if t['id'] != turn_id]

    def snapshot(self):
        with self._lock:
            events = sorted(deepcopy(self.events), key=lambda e: e['time_s'])
            turns = deepcopy(self.turns)
            ended_at = self._ended_at
            duration = self._duration if self._duration is not None else perf_counter() - self.started_timer
        samples = defaultdict(list)
        for turn in turns:
            history = [e for e in events if e['turn_id'] == turn['id']]
            first = {}
            for event in history:
                first.setdefault(event['type'], event['time_s'])
            for label, (start, end) in PAIRS.items():
                if start in first and end in first and first[end] >= first[start]:
                    samples[label].append(first[end] - first[start])
        starts = {}
        token_totals = {'input_tokens': 0, 'output_tokens': 0, 'total_tokens': 0}
        known_runs = set()
        llm_runs = set()
        for event in events:
            kind = event['type']
            run_key = (event['turn_id'], event.get('run_id'))
            if kind in ('llm_start', 'tool_start', 'touch_start'):
                starts[(kind, run_key)] = event
                if kind == 'llm_start':
                    llm_runs.add(run_key)
            if kind in ('llm_end', 'tool_end', 'touch_end'):
                start = starts.pop((kind.replace('_end', '_start'), run_key), None)
                if start is not None and event['time_s'] >= start['time_s']:
                    label = ('Pojedyncze żądanie LLM' if kind == 'llm_end' else
                             f"Narzędzie: {start['name']}" if kind == 'tool_end' else
                             f"Dotyk: {start['action']}")
                    samples[label].append(event['time_s'] - start['time_s'])
            if kind == 'llm_end':
                llm_runs.add(run_key)
                usage = event.get('usage')
                if usage is not None and run_key not in known_runs:
                    known_runs.add(run_key)
                    for name in ('input_tokens', 'output_tokens', 'total_tokens'):
                        token_totals[name] += usage[name]
        tokens = {name: value if known_runs else None for name, value in token_totals.items()}
        tokens['known_requests'] = len(known_runs)
        tokens['missing_requests'] = len(llm_runs - known_runs)
        counts = Counter(t['status'] for t in turns)
        return {
            'session_id': self.session_id, 'started_at': self.started_at.isoformat(),
            'ended_at': ended_at.isoformat() if ended_at else None,
            'duration_s': duration,
            'models': {'asr': 'Vosk', 'llm': 'gpt-4o-mini', 'tts': 'Supertonic'},
            'turns': turns, 'events': events,
            'counts': {status: counts[status] for status in STATUSES},
            'metrics': {name: {'n': len(values), 'mean_s': mean(values),
                               'min_s': min(values), 'max_s': max(values)}
                        for name, values in samples.items()},
            'tokens': tokens,
        }

    def save(self, directory=Path('logs/sessions')):
        with self._lock:
            if self._ended_at is None:
                for turn in self.turns:
                    if turn['status'] == 'active':
                        self.end_turn(turn['id'], 'interrupted')
                self._ended_at = datetime.now().astimezone()
                self._duration = perf_counter() - self.started_timer
            data = self.snapshot()
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        text_path = directory / f'{self.session_id}.txt'
        json_path = directory / f'{self.session_id}.json'
        # Write the independent outputs even if one of them fails.
        errors = []
        for path, contents in ((text_path, render_report(data)),
                               (json_path, json.dumps(data, ensure_ascii=False, indent=2))):
            try:
                temporary = path.with_suffix(path.suffix + '.tmp')
                temporary.write_text(contents, encoding='utf-8')
                temporary.replace(path)
            except OSError as error:
                errors.append(error)
        if errors:
            raise errors[0]
        return text_path, json_path


def render_report(data):
    lines = [f"SESJA: {data['session_id']}", 'ASR: Vosk | LLM: gpt-4o-mini | TTS: Supertonic',
             f"Rozpoczęcie: {data['started_at']}", f"Zakończenie: {data['ended_at']}",
             'Granice mowy: estymacja Vosk, według rozpoznanych słów.',
             'Start audio: wywołanie odtwarzania; bez pomiaru akustycznego.',
             'Zakończona tura nie oznacza potwierdzenia wykonania zadania.', '']
    events = data['events']
    for turn in data['turns']:
        history = [e for e in events if e['turn_id'] == turn['id']]
        speech = next((e for e in history if e['type'] == 'speech_start'), None)
        origin = speech['time_s'] if speech else (history[0]['time_s'] if history else 0)
        lines.append(f"TURA {turn['id']} [{STATUSES.get(turn['status'], turn['status'])}]")
        if speech is None:
            lines.append('Granice mowy: brak danych; przesunięcia od pierwszego zdarzenia tury.')
        lines.extend(_history_lines(history, origin))
        lines.append('')
    lines.append('HISTORIA DOTYKU I ZDARZEŃ SESJI (od początku sesji)')
    lines.extend(_history_lines([e for e in events if e['turn_id'] is None], 0))
    lines.extend(['', 'STATYSTYKI SESJI', f"Czas całej sesji: {data['duration_s']:.3f} s"])
    counts = data['counts']
    lines.append(f"Tury: {counts['completed']} zakończonych / {counts['failed']} błędnych / {counts['interrupted']} przerwanych")
    tokens = data['tokens']
    lines.append(f"Tokeny wejście / wyjście / razem: {_number(tokens['input_tokens'])} / {_number(tokens['output_tokens'])} / {_number(tokens['total_tokens'])}")
    lines.append(f"Pokrycie tokenów: {tokens['known_requests']} żądań z danymi / {tokens['missing_requests']} bez danych; suma obejmuje tylko dostępne dane.")
    lines.extend(['', f"{'Pomiar':44} {'N':>5} {'Średnia [s]':>13} {'Min [s]':>10} {'Max [s]':>10}"])
    names = list(PAIRS)
    names.insert(4, 'Pojedyncze żądanie LLM')
    names.extend(name for name in data['metrics'] if name not in names)
    for name in names:
        metric = data['metrics'].get(name)
        if metric:
            lines.append(f"{name:44} {metric['n']:5d} {metric['mean_s']:13.3f} {metric['min_s']:10.3f} {metric['max_s']:10.3f}")
        else:
            lines.append(f'{name:44}     0    brak danych')
    lines.append('\nCzasy narzędzi mogą się nakładać; ich suma nie jest czasem agenta.\n')
    return '\n'.join(lines)


def _number(value):
    return 'brak danych' if value is None else str(value)


def _history_lines(events, origin):
    lines = []
    starts = {}
    first = {}
    request_numbers = {}
    for event in events:
        kind: str = event['type']
        first.setdefault(kind, event['time_s'])
        run_id = event.get('run_id')
        label = LABELS.get(kind, kind)
        if kind == 'llm_start':
            request_numbers[run_id] = len(request_numbers) + 1
        if kind.startswith('llm_'):
            label += f" #{request_numbers.get(run_id, '?')}"
        if 'name' in event:
            label += f": {event['name']}"
        if 'action' in event:
            label += f": {event['action']}"
        if 'success' in event:
            label += (' [BRAK DANYCH]' if event['success'] is None else
                      ' [OK]' if event['success'] else ' [BŁĄD]')
        lines.append(f"+{event['time_s'] - origin:06.3f}  {label}")
        for key, title in (('text', 'Tekst'), ('arguments', 'Argumenty'),
                           ('tools', 'Wywołaj'), ('screen', 'Ekran'), ('error', 'Błąd'), ('warning', 'Uwaga')):
            if key in event:
                lines.append(f'         {title}: {json.dumps(event[key], ensure_ascii=False)}')
        if kind in ('llm_start', 'tool_start', 'touch_start'):
            starts[(kind, run_id)] = event['time_s']
        if kind in ('llm_end', 'tool_end', 'touch_end'):
            start = starts.get((kind.replace('_end', '_start'), run_id))
            if start is not None:
                lines.append(f"         Czas wykonania: {event['time_s'] - start:.3f} s")
        if kind == 'llm_end':
            lines.append(f"         Tokeny: {json.dumps(event.get('usage'), ensure_ascii=False) if event.get('usage') is not None else 'brak danych'}")
        for title, (start_kind, end_kind) in PAIRS.items():
            if kind == end_kind and start_kind in first:
                if kind == 'llm_start' and request_numbers.get(run_id) != 1:
                    continue
                lines.append(f"         {title}: {event['time_s'] - first[start_kind]:.3f} s")
    return lines or ['brak danych']
