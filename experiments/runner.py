"""Measurement series of the final configuration: run main.py --experiment as a subprocess
for 3 tasks × 3 recordings × 3 repetitions = 27 trials (+1 warm-up).

Uses only the standard library and never imports the application, so a crashing or
hanging trial cannot affect the runner. Run from the repo root:
    uv run python -m experiments.runner
"""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime
from math import isfinite
from statistics import mean

from .evaluate import EXPECTED_ARGUMENTS, SCENARIOS, evaluate_session

ROOT = Path(__file__).resolve().parent.parent
REPETITIONS = 3
RECORDINGS = 3
RECORDING_TYPES = ('polecenie wprost', 'naturalna parafraza', 'polecenie nie wprost')
TIMEOUT_S = 300
# Final configuration; ASR_LABEL must equal asr.model_label(ASR) (checked by a test).
ASR = 'whisper-large-v3-turbo-q5_0'
ASR_LABEL = 'Whisper large-v3-turbo-q5_0 (whisper.cpp)'
LLM = 'qwen3.5:2b'
MODELS = dict(asr=ASR_LABEL, llm=LLM, tts='Supertonic')
def _stats(values):
    values = [value for value in values
              if type(value) in (int, float) and isfinite(value) and value >= 0]
    return dict(n=len(values), mean=mean(values) if values else None,
                min=min(values) if values else None, max=max(values) if values else None)


def _save_summary(directory, summary):
    runs = summary['runs']
    summary['success_count'] = sum(run['success'] for run in runs)
    summary['success_rate_percent'] = 100 * summary['success_count'] / len(runs) if runs else None
    summary['task_success_count'] = sum(run.get('task_success') is True for run in runs)
    summary['task_assessed_count'] = sum(type(run.get('task_success')) is bool for run in runs)
    summary['timeout_count'] = sum(run.get('timed_out') is True for run in runs)
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
    models = summary.get('models', {})
    lines = [f"Konfiguracja: {models.get('asr', 'brak danych')} + {models.get('llm', 'brak danych')}",
             f"Zadanie: {summary['task']}",
             f"Zakończone próby: {len(runs)}/{summary.get('planned_runs', summary['repetitions'])}"]
    for run in runs:
        label = 'SUKCES' if run['success'] else 'NIEPOWODZENIE'
        lines.extend(['', f"RUN {run['run']:02d} — {label}", f"Ocena: {run['reason']}",
                      f"Raport: {run.get('report') or 'brak danych'}"])
        if 'prompt_text' in run:
            lines.extend([f"Audio {run['recording']}: {run['recording_type']}",
                          f"Polecenie deklarowane: {run['prompt_text']}"])
        if 'audio_file' in run:
            lines.extend([f"Nagranie: {run['audio_file']}", f"Powtórzenie: {run['repetition']}"])
        if 'task_success' in run:
            lines.append(f"Ocena zadania z raportu: {run['task_success']}; timeout procesu: {run['timed_out']}")
        if run.get('report_complete') is False:
            lines.append('Raport cząstkowy: dostępne pomiary tylko do ostatniego zapisu; brakujące etapy nie są zerami.')
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
                  f"Poprawne zadania według raportów: {summary['task_success_count']}/{len(runs)}; oceniono: {summary['task_assessed_count']}; timeouty procesów: {summary['timeout_count']}.",
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


def _run_trial(directory, task, audio_file):
    command = [sys.executable, str(ROOT / 'main.py'), '--asr', ASR,
               '--experiment', '--audio-file', str(audio_file), '--report-dir', str(directory)]
    result = dict(success=False, task_success=None, timed_out=False, reason='',
                  returncode=None, report=None, report_complete=None, session_id=None, duration_s=None, command=command)
    environment = {**os.environ, 'OLLAMA_MODEL': LLM, 'PYTHONUNBUFFERED': '1'}
    process_error = ''
    try:
        with (directory / 'console.log').open('w', encoding='utf-8') as log:
            process = subprocess.run(command, cwd=ROOT, env=environment, stdout=log,
                                     stderr=subprocess.STDOUT, timeout=TIMEOUT_S)
        result['returncode'] = process.returncode
        if process.returncode != 0:
            process_error = f'Proces zakończył się kodem {process.returncode}; szczegóły: console.log.'
    except subprocess.TimeoutExpired:
        result['timed_out'] = True
        process_error = f'Przekroczono limit czasu próby ({TIMEOUT_S} s); proces zakończony.'
    except OSError as error:
        process_error = str(error)
    try:
        reports = list(directory.glob('session_*.json'))
        if len(reports) != 1:
            raise ValueError(f'Oczekiwano jednego raportu JSON; znaleziono: {len(reports)}.')
        report_path = reports[0]
        result['report'] = report_path.name
        data = json.loads(report_path.read_text(encoding='utf-8'))
        if not isinstance(data, dict) or data.get('models') != MODELS:
            raise ValueError('Konfiguracja w raporcie nie odpowiada konfiguracji eksperymentu.')
        if data.get('input_source') != {'type': 'audiofile', 'path': str(audio_file)}:
            raise ValueError('Raport nie pochodzi z oczekiwanego pliku audio.')
        metrics, tokens = data.get('metrics', {}), data.get('tokens', {})
        if (not isinstance(metrics, dict) or not isinstance(tokens, dict)
                or any(not isinstance(metric, dict) for metric in metrics.values())):
            raise ValueError('Niepoprawny format pomiarów lub tokenów w raporcie.')
        result['session_id'] = data.get('session_id')
        result['duration_s'] = data.get('duration_s')
        result['metrics'] = metrics
        result['tokens'] = tokens
        result['report_complete'] = data.get('ended_at') is not None
        result['task_success'], result['reason'] = evaluate_session(data, task)
        result['success'] = not process_error and result['task_success']
        if not result['report_complete']:
            result['reason'] = f"Raport cząstkowy. {result['reason']}"
    except (OSError, ValueError) as error:
        result['reason'] = str(error)
    if process_error:
        result['reason'] = f"{process_error} {result['reason']}"
    path = directory / 'result.json'
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)
    return result


def _run_scenario(task, directory, audio_files, created_at):
    scenario = SCENARIOS[task]
    directory.mkdir()
    expected = dict(tools=scenario['tools'], state=scenario['state'], effect=scenario['effect'])
    if task == 2:
        expected['arguments'] = EXPECTED_ARGUMENTS
    summary = dict(task=f'Zadanie{task} — {scenario["title"]}',
                   repetitions=REPETITIONS, planned_runs=len(audio_files) * REPETITIONS,
                   created_at=created_at.isoformat(), asr_id=ASR, models=MODELS,
                   audio_files=[str(path) for path in audio_files], timeout_s=TIMEOUT_S,
                   expected=expected, runs=[])
    configuration_text = '\n'.join([
        f"Zadanie: {summary['task']}",
        f'Powtórzeń każdego nagrania: {REPETITIONS}', f"Łącznie prób: {summary['planned_runs']}",
        f'ASR: {ASR} ({ASR_LABEL})', f'LLM: {LLM}', f'TTS: {MODELS["tts"]}',
        f'Limit jednej próby: {TIMEOUT_S} s',
        'Nowy proces i domyślny stan HMI w każdej próbie; bez restartu Ollamy.',
        'Tryb --experiment: dotyk wyłączony, mikrofon wyłączony, wejście wyłącznie z pliku audio.',
        'Jedna próba rozgrzewająca w osobnym folderze warmup, poza statystykami.',
        'NAGRANIA:', *(f'{path} | {RECORDING_TYPES[number - 1]} | {scenario["prompts"][number - 1]}'
                       for number, path in enumerate(audio_files, 1)),
        'OCZEKIWANY EFEKT:', scenario['effect'], json.dumps(expected, ensure_ascii=False), '',
    ])
    (directory / 'config.txt').write_text(configuration_text, encoding='utf-8')
    _save_summary(directory, summary)
    for recording, audio_file in enumerate(audio_files, 1):
        recording_dir = directory / f'recording_{recording:02d}'
        recording_dir.mkdir()
        for repetition in range(1, REPETITIONS + 1):
            number = len(summary['runs']) + 1
            run_dir = recording_dir / f'run_{repetition:02d}'
            run_dir.mkdir()
            print(f"Zadanie {task}, nagranie {recording}/{len(audio_files)}, próba {repetition}/{REPETITIONS}", flush=True)
            result = _run_trial(run_dir, task, audio_file)
            result.update(run=number, recording=recording, repetition=repetition, audio_file=str(audio_file),
                          recording_type=RECORDING_TYPES[recording - 1],
                          prompt_text=scenario['prompts'][recording - 1])
            if result['report']:
                result['report'] = str((run_dir / result['report']).relative_to(directory))
            summary['runs'].append(result)
            _save_summary(directory, summary)
            print(f"{'SUKCES' if result['success'] else 'NIEPOWODZENIE'}: {result['reason']}", flush=True)
    print(f"Wynik: {summary['success_count']}/{summary['planned_runs']}. Podsumowanie: {directory / 'summary.txt'}", flush=True)
    return summary['success_count'] == summary['planned_runs']


def main() -> int:
    recordings = {}
    expected_names = [f'{number}.mp3' for number in range(1, RECORDINGS + 1)]
    try:
        for task, scenario in SCENARIOS.items():
            folder = ROOT / 'assets/voice' / scenario['title']
            files = sorted(path.resolve() for path in folder.glob('*.mp3') if path.is_file())
            if [path.name for path in files] != expected_names:
                raise ValueError(f'{folder}: wymagane dokładnie {RECORDINGS} nagrania MP3 '
                                 f'o nazwach {expected_names}; znaleziono {[path.name for path in files]}.')
            if any(path.stat().st_size == 0 for path in files):
                raise ValueError(f'{folder}: znaleziono pusty plik MP3.')
            recordings[task] = files
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2
    created_at = datetime.now().astimezone()
    series = ROOT / 'logs/eksperymenty' / f'seria_{created_at:%Y%m%d_%H%M%S_%f}'
    series.mkdir(parents=True)
    manifest = dict(created_at=created_at.isoformat(), models=MODELS, asr_id=ASR,
                    repetitions=REPETITIONS, recordings_per_task=RECORDINGS,
                    planned_runs=len(SCENARIOS) * RECORDINGS * REPETITIONS,
                    warmup_runs=1, timeout_s=TIMEOUT_S, experiment_mode=True,
                    recordings={task: [dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                                           recording=number, recording_type=RECORDING_TYPES[number - 1],
                                           prompt_text=SCENARIOS[task]['prompts'][number - 1])
                                       for number, path in enumerate(paths, 1)] for task, paths in recordings.items()})
    (series / 'config.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    warmup_dir = series / 'warmup'
    warmup_dir.mkdir()
    print(f'Rozgrzewanie {ASR} + {LLM} (poza statystykami).', flush=True)
    warmup = _run_trial(warmup_dir, 1, recordings[1][0])
    warmup.update(models=MODELS, audio_file=str(recordings[1][0]), excluded_from_statistics=True)
    (warmup_dir / 'summary.json').write_text(json.dumps(warmup, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    results = [warmup['success']]
    if not warmup['success']:
        print(f"Rozgrzewanie nieudane: {warmup['reason']}", flush=True)
    for task, scenario in SCENARIOS.items():
        results.append(_run_scenario(task, series / f'zad{task}_{scenario["title"]}',
                                     recordings[task], created_at))
    print(f'Wyniki serii: {series}', flush=True)
    return 0 if all(results) else 1


if __name__ == '__main__':
    sys.exit(main())
