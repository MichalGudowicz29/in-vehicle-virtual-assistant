"""Three sequential, single-turn phone trials using the current configuration."""

import json
import os
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime
from uuid import uuid4

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


def _save_summary(directory, summary):
    summary['success_count'] = sum(run['success'] for run in summary['runs'])
    lines = [f"Zadanie: {summary['task']}",
             f"Sukces: {summary['success_count']}/{summary['repetitions']}",
             f"Zakończone próby: {len(summary['runs'])}/{summary['repetitions']}", '']
    for run in summary['runs']:
        label = 'SUKCES' if run['success'] else 'NIEPOWODZENIE'
        lines.append(f"Próba {run['run']:02d}: {label} — {run['reason']}")
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
