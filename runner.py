"""Three sequential, single-turn phone trials using the current configuration."""

import json
import os
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime
from uuid import uuid4
from math import isfinite
from statistics import mean

import config
from asr import model_label, resolve_model


ROOT = Path(__file__).resolve().parent
REPETITIONS = 3
TIMEOUT_S = 300
EXPECTED_ARGUMENTS = {'name': 'Robert Lewandowski', 'number_type': 'mobile'}


def evaluate_session(data) -> tuple[bool, str]:
    if not isinstance(data, dict):
        return False, 'Niepoprawny format raportu.'
    events, turns = data.get('events'), data.get('turns')
    if (not isinstance(events, list) or not isinstance(turns, list)
            or not all(isinstance(item, dict) for item in events + turns)):
        return False, 'Brak poprawnej historii zdarzeń lub tur.'
    for event in events:
        if event.get('type') == 'session_error':
            return False, f"Błąd sesji: {event.get('error', 'brak szczegółów')}"
    if (len(turns) != 1 or turns[0].get('status') != 'completed'
            or not isinstance(turns[0].get('id'), int)):
        return False, 'Oczekiwano jednej poprawnie zakończonej tury.'
    calls = [e for e in events if e.get('type') == 'tool_start' and e.get('name') == 'call_contact']
    if len(calls) != 1:
        return False, f'Oczekiwano jednego call_contact; wykonano: {len(calls)}.'
    call = calls[0]
    arguments = call.get('arguments')
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            return False, 'Niepoprawny JSON argumentów call_contact.'
    if arguments != EXPECTED_ARGUMENTS:
        return False, f'Nieprawidłowe argumenty call_contact: {arguments!r}.'
    if not call.get('run_id') or call.get('turn_id') != turns[0].get('id'):
        return False, 'Wywołanie call_contact nie jest przypisane do oczekiwanej tury.'
    ends = [e for e in events if e.get('type') == 'tool_end'
            and e.get('name') == 'call_contact' and e.get('run_id') == call['run_id']
            and e.get('turn_id') == call['turn_id']]
    if len(ends) != 1 or ends[0].get('success') is not True:
        return False, 'Brak potwierdzonego sukcesu właściwego call_contact.'
    return True, 'Jedno poprawne call_contact dla Roberta Lewandowskiego (mobile), wynik OK.'


def _stats(values):
    values = [value for value in values
              if type(value) in (int, float) and isfinite(value) and value >= 0]
    return dict(n=len(values), mean=mean(values) if values else None,
                min=min(values) if values else None, max=max(values) if values else None)


def _save_summary(directory, summary):
    runs = summary['runs']
    summary['success_count'] = sum(run['success'] for run in runs)
    summary['success_rate_percent'] = 100 * summary['success_count'] / len(runs) if runs else None
    measurements = {}
    ranked = []
    for run in runs:
        for name, metric in run.get('metrics', {}).items():
            values = [metric.get(key) for key in ('mean_s', 'min_s', 'max_s')]
            if (type(metric.get('n')) is not int or metric['n'] <= 0
                    or not all(type(value) in (int, float) and isfinite(value) and value >= 0
                               for value in values)):
                continue
            measurements.setdefault(name, []).append(metric)
            if name == 'Cała tura' and run['success']:
                ranked.append(dict(run=run['run'], session_id=run.get('session_id'),
                                   report=run.get('report'), turn_duration_s=metric['mean_s']))
    summary['best_run'] = min(ranked, key=lambda run: run['turn_duration_s']) if ranked else None
    summary['worst_run'] = max(ranked, key=lambda run: run['turn_duration_s']) if ranked else None
    summary['statistics'] = {
        'duration_s': _stats(run.get('duration_s') for run in runs),
        'metrics': {name: dict(n=sum(m['n'] for m in metrics), runs=len(metrics),
                               mean_s=sum(m['n'] * m['mean_s'] for m in metrics) / sum(m['n'] for m in metrics),
                               min_s=min(m['min_s'] for m in metrics), max_s=max(m['max_s'] for m in metrics))
                    for name, metrics in measurements.items()},
        'tokens': {key: _stats(run.get('tokens', {}).get(key) for run in runs)
                   for key in ('input_tokens', 'output_tokens', 'total_tokens')},
        'token_coverage': {key: sum(run.get('tokens', {}).get(key, 0) for run in runs)
                           for key in ('known_requests', 'missing_requests')},
    }
    rate = summary['success_rate_percent']
    lines = [f"Zadanie: {summary['task']}",
             f"Zakończone próby: {len(runs)}/{summary['repetitions']}"]
    for run in runs:
        label = 'SUKCES' if run['success'] else 'NIEPOWODZENIE'
        lines.extend(['', f"RUN {run['run']:02d} — {label}", f"Ocena: {run['reason']}",
                      f"Raport: {run.get('report') or 'brak danych'}"])
        duration = run.get('duration_s')
        lines.append(f'Czas całej sesji: {duration:.3f} s' if duration is not None
                     else 'Czas całej sesji: brak danych')
        lines.append(f"{'Pomiar':44} {'N':>5} {'Średnia [s]':>13} {'Min [s]':>10} {'Max [s]':>10}")
        for name, metric in run.get('metrics', {}).items():
            lines.append(f"{name:44} {metric['n']:5d} {metric['mean_s']:13.3f} {metric['min_s']:10.3f} {metric['max_s']:10.3f}")
        if not run.get('metrics'):
            lines.append('Pomiary etapów: brak danych')
        tokens = run.get('tokens', {})
        for key, title in [('input_tokens', 'Tokeny wejściowe'), ('output_tokens', 'Tokeny wyjściowe'), ('total_tokens', 'Tokeny razem')]:
            value = tokens.get(key)
            lines.append(f"{title}: {value if value is not None else 'brak danych'}")
        lines.append(f"Pokrycie tokenów: {tokens.get('known_requests', 0)} żądań z danymi / {tokens.get('missing_requests', 0)} bez danych.")
    statistics = summary['statistics']
    lines.extend(['', f'ŚREDNIE STATYSTYKI Z {len(runs)} PRÓB',
                  'Wszystkie dostępne pomiary, także z nieudanych prób; braki nie są zerami.',
                  'Średnie żądań LLM i narzędzi są ważone liczbą pomiarów N.',
                  f"{'Pomiar':44} {'N':>5} {'Próby':>6} {'Średnia [s]':>13} {'Min [s]':>10} {'Max [s]':>10}"])
    duration = statistics['duration_s']
    if duration['n']:
        lines.append(f"{'Czas całej sesji':44} {duration['n']:5d} {duration['n']:6d} {duration['mean']:13.3f} {duration['min']:10.3f} {duration['max']:10.3f}")
    else:
        lines.append('Czas całej sesji: brak danych')
    for name, metric in statistics['metrics'].items():
        lines.append(f"{name:44} {metric['n']:5d} {metric['runs']:6d} {metric['mean_s']:13.3f} {metric['min_s']:10.3f} {metric['max_s']:10.3f}")
    lines.extend(['', 'TOKENY NA PRÓBĘ (tylko dostępne zużycie)',
                  f"{'Pomiar':24} {'Próby':>6} {'Średnia':>13} {'Min':>10} {'Max':>10}"])
    for key, title in [('input_tokens', 'Tokeny wejściowe'), ('output_tokens', 'Tokeny wyjściowe'), ('total_tokens', 'Tokeny razem')]:
        metric = statistics['tokens'][key]
        lines.append(f"{title:24} {metric['n']:6d} {metric['mean']:13.2f} {metric['min']:10.0f} {metric['max']:10.0f}"
                     if metric['n'] else f'{title}: brak danych')
    coverage = statistics['token_coverage']
    lines.extend([f"Pokrycie tokenów: {coverage['known_requests']} żądań z danymi / {coverage['missing_requests']} bez danych.",
                  '', f"Sukces: {summary['success_count']}/{len(runs)}",
                  f"Success rate (wszystkie zakończone próby, także błędy i timeouty): {f'{rate:.2f}%' if rate is not None else 'brak danych'}",
                  'Ranking: czas całej tury, wyłącznie próby z sukcesem zadania.'])
    for key, title in [('best_run', 'Najlepsza próba'), ('worst_run', 'Najgorsza próba')]:
        run = summary[key]
        lines.append(f"{title}: {run['run']:02d} — {run['turn_duration_s']:.3f} s | {run['report']}"
                     if run else f'{title}: brak danych')
    for name, contents in [('summary.json', json.dumps(summary, ensure_ascii=False, indent=2)),
                           ('summary.txt', '\n'.join(lines) + '\n')]:
        path = directory / name
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(contents, encoding='utf-8')
        temporary.replace(path)


def main() -> int:
    audio_file = (ROOT / 'assets/voice/Telefon.mp3').resolve()
    if not audio_file.is_file():
        print(f'Nie znaleziono nagrania: {audio_file}', file=sys.stderr)
        return 2
    asr = resolve_model()
    models = {'asr': model_label(asr), 'llm': config.OLLAMA_MODEL, 'tts': 'Supertonic'}
    created_at = datetime.now().astimezone()
    configuration = re.sub(r'[^\w.-]+', '_', f'{asr}_{models["llm"]}')
    directory = ROOT / 'logs/eksperymenty' / f'{configuration}_Zadanie1_{created_at:%Y%m%d_%H%M%S}_{uuid4().hex[:8]}'
    directory.mkdir(parents=True)
    expected = {'tool': 'call_contact', 'arguments': EXPECTED_ARGUMENTS, 'count': 1, 'success': True}
    runs = []
    summary = dict(task='Zadanie1 — Telefon', repetitions=REPETITIONS,
                   created_at=created_at.isoformat(), asr_id=asr, models=models,
                   audio_file=str(audio_file), timeout_s=TIMEOUT_S, expected=expected, runs=runs)
    configuration_text = '\n'.join([
        f"Zadanie: {summary['task']}", f'Nagranie: {audio_file}',
        f'Liczba powtórzeń: {REPETITIONS}', f'ASR_MODEL: {asr} ({models["asr"]})',
        f'OLLAMA_MODEL: {models["llm"]}', f'TTS: {models["tts"]}',
        f'Rozpoczęcie: {created_at.isoformat()}', f'Limit jednej próby: {TIMEOUT_S} s',
        'Nowy proces aplikacji i stan początkowy w każdej próbie; bez restartu Ollamy.',
        'OCZEKIWANY EFEKT:',
        'call_contact(name="Robert Lewandowski", number_type="mobile") — dokładnie raz, wynik success=True.',
        'Wywołanie i wynik muszą należeć do tej samej poprawnie zakończonej tury.',
        'Samo pytanie o doprecyzowanie, get_contacts lub ukończenie tury nie oznacza sukcesu zadania.',
        '',
    ])
    (directory / 'config.txt').write_text(configuration_text, encoding='utf-8')
    _save_summary(directory, summary)
    print(f'Eksperyment: {directory}', flush=True)
    environment = {**os.environ, 'OLLAMA_MODEL': models['llm'], 'ASR_MODEL': asr}
    for number in range(1, REPETITIONS + 1):
        run_dir = directory / f'run_{number:02d}'
        run_dir.mkdir()
        command = [sys.executable, str(ROOT / 'main.py'), '--asr', asr,
                   '--audio-file', str(audio_file), '--report-dir', str(run_dir)]
        result = dict(run=number, success=False, reason='', returncode=None, report=None,
                      session_id=None, duration_s=None, command=command)
        print(f'Próba {number}/{REPETITIONS}…', flush=True)
        try:
            with (run_dir / 'console.log').open('w', encoding='utf-8') as log:
                process = subprocess.run(command, cwd=ROOT, env=environment, stdout=log,
                                         stderr=subprocess.STDOUT, timeout=TIMEOUT_S)
            result['returncode'] = process.returncode
            if process.returncode != 0:
                raise ValueError(f'Proces zakończył się kodem {process.returncode}; szczegóły: console.log.')
            reports = list(run_dir.glob('session_*.json'))
            if len(reports) != 1:
                raise ValueError(f'Oczekiwano jednego raportu JSON; znaleziono: {len(reports)}.')
            report_path = reports[0]
            result['report'] = str(report_path.relative_to(directory))
            data = json.loads(report_path.read_text(encoding='utf-8'))
            if not isinstance(data, dict) or data.get('models') != models:
                raise ValueError('Konfiguracja w raporcie nie odpowiada konfiguracji eksperymentu.')
            if data.get('input_source') != {'type': 'audiofile', 'path': str(audio_file)}:
                raise ValueError('Raport nie pochodzi z oczekiwanego pliku audio.')
            result['session_id'] = data.get('session_id')
            result['duration_s'] = data.get('duration_s')
            result['metrics'] = data.get('metrics', {})
            result['tokens'] = data.get('tokens', {})
            result['success'], result['reason'] = evaluate_session(data)
        except subprocess.TimeoutExpired:
            result['reason'] = f'Przekroczono limit czasu próby ({TIMEOUT_S} s); proces zakończony.'
        except (OSError, ValueError) as error:
            result['reason'] = str(error)
        runs.append(result)
        _save_summary(directory, summary)
        label = 'SUKCES' if result['success'] else 'NIEPOWODZENIE'
        print(f"{label}: {result['reason']}", flush=True)
    print(f"Wynik: {summary['success_count']}/{REPETITIONS}. Podsumowanie: {directory / 'summary.txt'}", flush=True)
    return 0 if summary['success_count'] == REPETITIONS else 1


if __name__ == '__main__':
    sys.exit(main())
