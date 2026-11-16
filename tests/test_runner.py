import json
import pytest

from session_report import SessionReport


def phone_session(name='Robert Lewandowski', number_type='mobile', success=True):
    report = SessionReport()
    turn = report.begin_turn()
    report.emit('tool_start', turn_id=turn, run_id='call1', name='call_contact',
                arguments={'name': name, 'number_type': number_type})
    report.emit('tool_end', turn_id=turn, run_id='call1', name='call_contact', success=success)
    report.end_turn(turn, 'completed')
    report.emit('app_state', state={'contacts': {'name': name, 'is_calling': True}})
    return report.snapshot()


def test_expected_phone_action_passes_and_completed_dialog_alone_does_not():
    from runner import evaluate_session
    data = phone_session()
    assert evaluate_session(data)[0] is True
    data['events'] = [e for e in data['events'] if e['type'] == 'turn_end']
    success, reason = evaluate_session(data)
    assert success is False
    assert 'call_contact' in reason


@pytest.mark.parametrize('name, number_type, tool_success', [
    ('Anna Kowalska', 'mobile', True),
    ('Robert Lewandowski', 'work', True),
    ('Robert Lewandowski', 'mobile', False),
    ('Robert Lewandowski', 'mobile', None),
])
def test_wrong_contact_number_or_tool_failure_is_not_task_success(name, number_type, tool_success):
    from runner import evaluate_session
    assert evaluate_session(phone_session(name, number_type, tool_success))[0] is False


@pytest.mark.parametrize('problem', ['duplicate', 'wrong_run_id', 'wrong_turn', 'unfinished', 'session_error'])
def test_only_one_completed_and_correctly_paired_call_counts_as_success(problem):
    from runner import evaluate_session
    data = phone_session()
    if problem == 'duplicate':
        data['events'].append(dict(data['events'][0], run_id='call2'))
    elif problem == 'wrong_run_id':
        data['events'][1]['run_id'] = 'different_call'
    elif problem == 'wrong_turn':
        data['events'][1]['turn_id'] = 9
    elif problem == 'unfinished':
        data['turns'][0]['status'] = 'failed'
    else:
        data['events'].append({'type': 'session_error', 'error': 'LLM unavailable'})
    assert evaluate_session(data)[0] is False


def prepare_experiment(project, failures=False, tail=''):
    for task, title in [(1, 'Muzyka'), (2, 'Telefon'), (3, 'Nawigacja')]:
        folder = project / 'assets/voice' / title
        folder.mkdir(parents=True)
        for recording in range(1, 4):
            (folder / f'{recording}.mp3').write_bytes(b'test input')
    (project / '.env').write_text('ASR_MODEL=unchanged\nOLLAMA_MODEL=unchanged\n')
    script = r'''
import argparse, json, os
from pathlib import Path
parser = argparse.ArgumentParser()
parser.add_argument('--audio-file', type=Path)
parser.add_argument('--report-dir', type=Path)
parser.add_argument('--asr')
parser.add_argument('--experiment', action='store_true', required=True)
args = parser.parse_args()
assert args.asr == os.environ['ASR_MODEL']
assert os.environ.get('PYTHONUNBUFFERED') == '1'
run = 1 if args.report_dir.name == 'warmup' else int(args.report_dir.name[-2:])
task = {'Muzyka': 1, 'Telefon': 2, 'Nawigacja': 3}[args.audio_file.parent.name]
with Path('order.jsonl').open('a') as order:
    order.write(json.dumps(dict(asr=args.asr, llm=os.environ['OLLAMA_MODEL'], task=task,
                               audio=args.audio_file.name, repetition=run,
                               warmup=args.report_dir.name == 'warmup')) + '\n')
tool, arguments, state = {
    1: ('select_track', {'title': 'Christmas Eve'}, {'music': {'title': 'Christmas Eve', 'is_playing': True}}),
    2: ('call_contact', {'name': 'Robert Lewandowski', 'number_type': 'mobile'}, {'contacts': {'name': 'Robert Lewandowski', 'is_calling': True}}),
    3: ('navigate_to', {'street': 'Żołnierska', 'number': '47', 'city': 'Szczecin'}, {'navigation': {'destination': 'ul. Żołnierska 47, Szczecin', 'stops': []}}),
}[task]
events = []
if not FAILURES or run != 2:
    events = [dict(type='tool_start', turn_id=1, run_id='call', name=tool, arguments=arguments),
              dict(type='tool_end', turn_id=1, run_id='call', name=tool, success=True)]
    if task == 1:
        events[:0] = [
            dict(type='tool_start', turn_id=1, run_id='list', name='get_track_list', arguments={}),
            dict(type='tool_end', turn_id=1, run_id='list', name='get_track_list', success=True,
                 output=json.dumps({'success': True, 'tracks': [{'id': 0, 'title': 'Christmas Eve', 'author': 'Toto'}]})),
        ]
events.append(dict(type='app_state', turn_id=None, state=state))
label = {'vosk': 'Vosk small-pl-0.22', 'whisper-small': 'Whisper small (whisper.cpp)'}[args.asr]
data = dict(session_id=f'session_{run}', ended_at='2026-11-05T10:00:00+01:00', models=dict(asr=label, llm=os.environ['OLLAMA_MODEL'], tts='Supertonic'),
            input_source=dict(type='audiofile', path=str(args.audio_file)),
            turns=[dict(id=1, status='completed')], events=events, duration_s=1.5,
            metrics={'Cała tura': dict(n=1, mean_s=float(run), min_s=float(run), max_s=float(run))}, tokens={})
(args.report_dir / f'session_{run}.json').write_text(json.dumps(data))
(args.report_dir / f'session_{run}.txt').write_text('session report')
print('Child process finished', flush=True)
if FAILURES and run == 3:
    raise SystemExit(7)
'''
    (project / 'main.py').write_text(f'FAILURES = {failures!r}\n' + script + tail)


@pytest.mark.parametrize('failures', [False, True])
def test_runner_executes_108_trials_in_variant_task_recording_order(monkeypatch, tmp_path, failures):
    import runner
    project = tmp_path / 'project with spaces'
    prepare_experiment(project, failures)
    original = {name: (project / name).read_bytes() for name in ('main.py', '.env')}
    monkeypatch.setattr(runner, 'ROOT', project)
    assert runner.main() == (1 if failures else 0)
    order = [json.loads(line) for line in (project / 'order.jsonl').read_text().splitlines()]
    expected = []
    for asr, llm in [('vosk', 'qwen3.5:2b'), ('whisper-small', 'qwen3.5:2b'),
                     ('vosk', 'qwen3.5:4b'), ('whisper-small', 'qwen3.5:4b')]:
        expected.append(dict(asr=asr, llm=llm, task=1, audio='1.mp3', repetition=1, warmup=True))
        for task, title in [(1, 'Muzyka'), (2, 'Telefon'), (3, 'Nawigacja')]:
            for recording in range(1, 4):
                for repetition in range(1, 4):
                    expected.append(dict(asr=asr, llm=llm, task=task, audio=f'{recording}.mp3',
                                         repetition=repetition, warmup=False))
    assert order == expected
    series = list((project / 'logs/eksperymenty').iterdir())
    assert len(series) == 1
    variants = sorted(p for p in series[0].iterdir() if p.is_dir())
    assert [p.name for p in variants] == ['A_vosk_qwen3.5_2b', 'B_whisper-small_qwen3.5_2b',
                                        'C_vosk_qwen3.5_4b', 'D_whisper-small_qwen3.5_4b']
    manifest = json.loads((series[0] / 'config.json').read_text())
    assert manifest['planned_runs'] == 108
    music = manifest['recordings']['1']
    assert [entry['recording'] for entry in music] == [1, 2, 3]
    assert [entry['recording_type'] for entry in music] == [
        'polecenie wprost', 'naturalna parafraza', 'polecenie nie wprost']
    assert music[0]['prompt_text'] == 'Włącz piosenkę Christmas Eve'
    assert music[2]['prompt_text'] == 'Włącz jakąś muzykę, chcę poczuć klimat świąt'
    for variant in variants:
        assert (variant / 'warmup/summary.json').is_file()
        for task in range(1, 4):
            experiment = next(variant.glob(f'zad{task}_*'))
            assert len(list(experiment.glob('recording_*/run_*/session_*.json'))) == 9
            summary = json.loads((experiment / 'summary.json').read_text())
            assert summary['variant'] == variant.name[0]
            assert summary['repetitions'] == 3 and summary['planned_runs'] == 9
            assert [run['success'] for run in summary['runs']] == ([True, False, False] * 3 if failures else [True] * 9)
            assert summary['success_count'] == (3 if failures else 9)
            assert summary['statistics']['metrics']['Cała tura']['n'] == 9
            assert summary['statistics']['metrics']['Cała tura']['mean_s'] == 2
            assert summary['best_run']['run'] == 1
            assert summary['worst_run']['run'] == (1 if failures else 3)
            assert len({run['audio_file'] for run in summary['runs']}) == 3
            assert [run['recording_type'] for run in summary['runs']] == (
                ['polecenie wprost'] * 3 + ['naturalna parafraza'] * 3 + ['polecenie nie wprost'] * 3)
            assert all(run['prompt_text'] for run in summary['runs'])
            assert summary['runs'][0]['prompt_text'] in (experiment / 'summary.txt').read_text()
            assert 'Wariant:' in (experiment / 'config.txt').read_text()
            assert (experiment / 'recording_01/run_01/console.log').read_text().strip() == 'Child process finished'
            if failures:
                assert summary['runs'][2]['task_success'] is True
                assert 'kodem 7' in summary['runs'][2]['reason']
                assert summary['task_success_count'] == 6
            assert ('3/9' if failures else '9/9') in (experiment / 'summary.txt').read_text()
    assert all((project / name).read_bytes() == content for name, content in original.items())
    # A new invocation must preserve the previous series and its reports.
    if not failures:
        assert runner.main() == 0
        assert len(list((project / 'logs/eksperymenty').iterdir())) == 2


@pytest.mark.parametrize('problem', ['missing', 'extra', 'empty', 'wrong_name'])
def test_runner_rejects_incomplete_recording_set_before_starting(monkeypatch, tmp_path, problem):
    import runner
    prepare_experiment(tmp_path)
    path = tmp_path / 'assets/voice/Nawigacja/3.mp3'
    if problem == 'missing':
        path.unlink()
    elif problem == 'extra':
        (path.parent / 'extra.mp3').write_bytes(b'extra')
    elif problem == 'wrong_name':
        path.rename(path.with_name('inna_nazwa.mp3'))
    else:
        path.write_bytes(b'')
    monkeypatch.setattr(runner, 'ROOT', tmp_path)
    assert runner.main() == 2
    assert not (tmp_path / 'order.jsonl').exists()
    assert not (tmp_path / 'logs/eksperymenty').exists()


def test_timeout_keeps_completed_task_report_and_metrics(monkeypatch, tmp_path):
    import runner
    prepare_experiment(tmp_path, tail='\nimport time; time.sleep(5)\n')
    monkeypatch.setattr(runner, 'ROOT', tmp_path)
    monkeypatch.setattr(runner, 'TIMEOUT_S', .5)
    directory = tmp_path / 'trial'
    directory.mkdir()
    models = dict(asr='Vosk small-pl-0.22', llm='qwen3.5:2b', tts='Supertonic')
    # Name matches the ordinary per-recording trial layout.
    trial = directory / 'run_01'
    trial.mkdir()
    result = runner._run_trial(trial, 2, 'vosk', models, tmp_path / 'assets/voice/Telefon/1.mp3')
    assert result['success'] is False and result['timed_out'] is True
    assert result['task_success'] is True
    assert result['report'] == 'session_1.json'
    assert result['metrics']['Cała tura']['mean_s'] == 1
    assert 'limit' in result['reason']


def test_timeouts_continue_through_all_variants_and_tasks(monkeypatch, tmp_path):
    import runner
    prepare_experiment(tmp_path)
    (tmp_path / 'main.py').write_text('import time; time.sleep(5)')
    monkeypatch.setattr(runner, 'ROOT', tmp_path)
    monkeypatch.setattr(runner, 'TIMEOUT_S', .05)
    monkeypatch.setattr(runner, 'REPETITIONS', 1)
    assert runner.main() == 1
    summaries = list((tmp_path / 'logs/eksperymenty').glob('*/[ABCD]_*/zad*/summary.json'))
    assert len(summaries) == 12
    for path in summaries:
        data = json.loads(path.read_text())
        assert data['success_count'] == 0 and data['timeout_count'] == 3
        assert len(data['runs']) == 3
        assert all(run['task_success'] is None and 'limit' in run['reason'] for run in data['runs'])
        results = list(path.parent.glob('recording_*/run_*/result.json'))
        assert len(results) == 3
        for result_path in results:
            result = json.loads(result_path.read_text())
            assert result['timed_out'] is True
            assert result['task_success'] is None
            assert result['report'] is None
            assert 'limit' in result['reason']


def test_timeout_retains_partial_report_metrics_without_claiming_task_success(monkeypatch, tmp_path):
    import runner
    prepare_experiment(tmp_path, tail='''
data.update(ended_at=None, turns=[dict(id=1, status='active')],
            metrics={'ASR total': dict(n=1, mean_s=1.2, min_s=1.2, max_s=1.2)})
(args.report_dir / f'session_{run}.json').write_text(json.dumps(data))
import time; time.sleep(5)
''')
    monkeypatch.setattr(runner, 'ROOT', tmp_path)
    monkeypatch.setattr(runner, 'TIMEOUT_S', .5)
    trial = tmp_path / 'run_01'
    trial.mkdir()
    result = runner._run_trial(trial, 1, 'vosk',
                               dict(asr='Vosk small-pl-0.22', llm='qwen3.5:2b', tts='Supertonic'),
                               tmp_path / 'assets/voice/Muzyka/1.mp3')
    assert result['timed_out'] is True
    assert result['report_complete'] is False
    assert result['success'] is False and result['task_success'] is False
    assert result['metrics']['ASR total']['mean_s'] == 1.2
    assert 'Cała tura' not in result['metrics']
    assert 'Raport cząstkowy' in result['reason']


def test_runner_preflight_is_independent_of_application_imports_and_env(tmp_path):
    import os
    from pathlib import Path
    import subprocess
    import sys
    source = Path(__file__).resolve().parents[1] / 'runner.py'
    script = tmp_path / 'runner.py'
    script.write_bytes(source.read_bytes())
    environment = {key: value for key, value in os.environ.items() if key not in ('OLLAMA_MODEL', 'ASR_MODEL', 'PYTHONPATH')}
    result = subprocess.run([sys.executable, '-I', str(script)], cwd=tmp_path,
                            env=environment, capture_output=True, text=True, timeout=5)
    assert result.returncode == 2
    assert 'wymagane dokładnie 3 nagrania MP3' in result.stderr


@pytest.mark.parametrize('field, value', [('metrics', []), ('metrics', {'Cała tura': []}), ('tokens', [])])
def test_invalid_measurements_are_rejected_before_summary(monkeypatch, tmp_path, field, value):
    import runner
    tail = f"\ndata[{field!r}] = {value!r}\n(args.report_dir / f'session_{{run}}.json').write_text(json.dumps(data))\n"
    prepare_experiment(tmp_path, tail=tail)
    monkeypatch.setattr(runner, 'ROOT', tmp_path)
    trial = tmp_path / 'run_01'
    trial.mkdir()
    result = runner._run_trial(trial, 1, 'vosk',
                               dict(asr='Vosk small-pl-0.22', llm='qwen3.5:2b', tts='Supertonic'),
                               tmp_path / 'assets/voice/Muzyka/1.mp3')
    assert result['success'] is False
    assert 'format pomiarów' in result['reason']


@pytest.mark.parametrize('script, reason', [
    ('pass', 'raportu JSON'),
    ("from pathlib import Path; Path(__import__('sys').argv[-1], 'session_bad.json').write_text('{')", 'Expecting'),
    ('raise SystemExit(7)', 'kodem 7'),
])
def test_invalid_child_execution_is_recorded_instead_of_counted_as_success(monkeypatch, tmp_path, script, reason):
    import runner
    prepare_experiment(tmp_path)
    (tmp_path / 'main.py').write_text(script)
    monkeypatch.setattr(runner, 'ROOT', tmp_path)
    directory = tmp_path / 'run_01'
    directory.mkdir()
    result = runner._run_trial(directory, 1, 'vosk',
                               dict(asr='Vosk small-pl-0.22', llm='qwen3.5:2b', tts='Supertonic'),
                               tmp_path / 'assets/voice/Muzyka/1.mp3')
    assert result['success'] is False
    assert reason in result['reason']


@pytest.mark.parametrize('task, tool, arguments, state', [
    (1, 'select_track', {'title': 'Christmas Eve'}, {'music': {'title': 'Christmas Eve', 'is_playing': True}}),
    (3, 'navigate_to', {'street': 'zolnierska', 'number': '47', 'city': 'szczecin'},
     {'navigation': {'destination': 'ul. Żołnierska 47, Szczecin', 'stops': []}}),
])
def test_scenario_success_requires_both_action_and_expected_final_state(task, tool, arguments, state):
    from runner import evaluate_session
    data = {'turns': [{'id': 1, 'status': 'completed'}], 'events': [
        dict(type='tool_start', turn_id=1, run_id='action', name=tool, arguments=arguments),
        dict(type='tool_end', turn_id=1, run_id='action', name=tool, success=True),
        dict(type='app_state', turn_id=None, state=state),
    ]}
    if task == 1:
        data['events'][:0] = music_listing()
    assert evaluate_session(data, task)[0] is True
    data['events'][-1]['state'] = {}
    assert evaluate_session(data, task)[0] is False


def music_listing():
    return [
        dict(type='tool_start', turn_id=1, run_id='list', name='get_track_list', arguments={}),
        dict(type='tool_end', turn_id=1, run_id='list', name='get_track_list', success=True,
             output=json.dumps({'success': True, 'tracks': [{'id': 0, 'title': 'Christmas Eve', 'author': 'Toto'}]})),
    ]


@pytest.mark.parametrize('problem', ['no_list', 'late_list', 'failed_list', 'wrong_turn',
                                      'wrong_run', 'missing_title', 'bad_output', 'play_pause',
                                      'wrong_title', 'duplicate', 'extra_toggle', 'extra_pause',
                                      'extra_resume', 'same_response'])
def test_music_evaluation_requires_list_then_one_matching_selection(problem):
    from runner import evaluate_session
    listing = music_listing()
    action = [dict(type='tool_start', turn_id=1, run_id='play', name='select_track',
                   arguments={'title': 'Christmas Eve'}),
              dict(type='tool_end', turn_id=1, run_id='play', name='select_track', success=True)]
    if problem == 'no_list':
        listing = []
    elif problem == 'failed_list':
        listing[1]['success'] = False
    elif problem == 'wrong_turn':
        for event in listing:
            event['turn_id'] = 2
    elif problem == 'wrong_run':
        listing[1]['run_id'] = 'other'
    elif problem == 'missing_title':
        listing[1]['output'] = json.dumps({'success': True, 'tracks': []})
    elif problem == 'bad_output':
        listing[1]['output'] = 'not JSON'
    elif problem == 'play_pause':
        for event in action:
            event['name'] = 'play_pause'
        action[0]['arguments'] = {}
    elif problem == 'wrong_title':
        action[0]['arguments'] = {'title': 'Chill song'}
    elif problem == 'duplicate':
        action += [dict(event, run_id='second') for event in action]
    elif problem in ('extra_toggle', 'extra_pause', 'extra_resume'):
        name = {'extra_toggle': 'play_pause', 'extra_pause': 'pause_music', 'extra_resume': 'resume_music'}[problem]
        action += [dict(type='tool_start', turn_id=1, run_id='toggle', name=name, arguments={}),
                   dict(type='tool_end', turn_id=1, run_id='toggle', name=name, success=True)]
    elif problem == 'same_response':
        listing.insert(0, dict(type='llm_end', turn_id=1, tools=['get_track_list', 'select_track']))
    data = {'turns': [{'id': 1, 'status': 'completed'}],
            'events': (action + listing if problem == 'late_list' else listing + action) + [
                dict(type='app_state', state={'music': {'title': 'Christmas Eve', 'is_playing': True}})]}
    assert evaluate_session(data, 1)[0] is False


def test_phone_success_requires_call_to_still_be_active():
    from runner import evaluate_session
    data = phone_session()
    data['events'][-1]['state']['contacts']['is_calling'] = False
    assert evaluate_session(data)[0] is False


def test_runner_preflights_all_recordings_before_starting(monkeypatch, tmp_path):
    import runner
    (tmp_path / 'assets/voice/Muzyka').mkdir(parents=True)
    (tmp_path / 'assets/voice/Muzyka/1.mp3').touch()
    monkeypatch.setattr(runner, 'ROOT', tmp_path)
    assert runner.main() == 2
    assert not (tmp_path / 'logs/eksperymenty').exists()


def test_summary_aggregates_all_runs_with_weighted_timings_and_ranks_successes(tmp_path):
    from runner import _save_summary
    runs = []
    for number, success, duration, turn, requests, llm_mean, tokens, known, missing in [
        (1, True, 12, 10, 1, 2, 10, 1, 0),
        (2, True, 21, 20, 3, 6, 50, 3, 0),
        (3, False, 3, 1, 1, 1, None, 0, 1),
    ]:
        runs.append(dict(run=number, success=success, reason='wynik', duration_s=duration,
                         session_id=f'session_{number}', report=f'run_{number:02d}/session.json',
                         metrics={'Cała tura': dict(n=1, mean_s=turn, min_s=turn, max_s=turn),
                                  **{name: dict(n=1, mean_s=turn, min_s=turn, max_s=turn)
                                     for name in ('ASR total', 'LLM total', 'TTS total')},
                                  'Pojedyncze żądanie LLM': dict(n=requests, mean_s=llm_mean, min_s=llm_mean, max_s=llm_mean)},
                         tokens=dict(input_tokens=tokens, output_tokens=None, total_tokens=None,
                                     known_requests=known, missing_requests=missing)))
    summary = dict(task='Zadanie1', repetitions=3, runs=runs)
    _save_summary(tmp_path, summary)
    data = json.loads((tmp_path / 'summary.json').read_text())
    assert data['success_rate_percent'] == pytest.approx(200 / 3)
    assert data['best_run']['run'] == 1
    assert data['worst_run']['run'] == 2
    assert data['best_run']['turn_duration_s'] == 10
    assert data['worst_run']['turn_duration_s'] == 20
    stats = data['statistics']
    assert stats['duration_s'] == dict(n=3, mean=12, min=3, max=21)
    assert stats['metrics']['Pojedyncze żądanie LLM'] == dict(n=5, runs=3, mean_s=4.2, min_s=1, max_s=6)
    assert stats['metrics']['Cała tura']['mean_s'] == pytest.approx(31 / 3)
    for name in ('ASR total', 'LLM total', 'TTS total'):
        assert stats['metrics'][name]['mean_s'] == pytest.approx(31 / 3)
        assert name in (tmp_path / 'summary.txt').read_text()
    assert stats['tokens']['input_tokens'] == dict(n=2, mean=30, min=10, max=50)
    assert stats['token_coverage'] == dict(known_requests=4, missing_requests=1)
    text = (tmp_path / 'summary.txt').read_text()
    for expected in ('66.67%', 'Najlepsza próba: 01', 'Najgorsza próba: 02',
                     'Pojedyncze żądanie LLM', '4.200', 'Tokeny wejściowe'):
        assert expected in text


def test_empty_summary_has_no_fake_zero_measurements_or_ranking(tmp_path):
    from runner import _save_summary
    summary = dict(task='Zadanie1', repetitions=3, runs=[])
    _save_summary(tmp_path, summary)
    data = json.loads((tmp_path / 'summary.json').read_text())
    assert data['success_rate_percent'] is None
    assert data['best_run'] is None
    assert data['worst_run'] is None
    assert data['statistics']['duration_s'] == dict(n=0, mean=None, min=None, max=None)
    assert 'brak danych' in (tmp_path / 'summary.txt').read_text()


def test_failed_runs_count_toward_success_rate_but_not_ranking(tmp_path):
    from runner import _save_summary
    summary = dict(task='Zadanie1', repetitions=3, runs=[
        dict(run=1, success=False, reason='timeout', duration_s=None),
        dict(run=2, success=False, reason='brak call_contact', duration_s=5),
    ])
    _save_summary(tmp_path, summary)
    data = json.loads((tmp_path / 'summary.json').read_text())
    assert data['success_rate_percent'] == 0
    assert data['best_run'] is None and data['worst_run'] is None
    assert data['statistics']['duration_s']['n'] == 1
    assert data['statistics']['duration_s']['mean'] == 5


def test_summary_lists_ten_run_statistics_before_averages_and_success_rate(tmp_path):
    from runner import _save_summary
    runs = [dict(run=i, success=i % 2 == 0, reason='ocena zadania', duration_s=i + 1,
                 metrics={'Cała tura': dict(n=1, mean_s=i, min_s=i, max_s=i)},
                 tokens=dict(input_tokens=i * 10)) for i in range(1, 11)]
    _save_summary(tmp_path, dict(task='Zadanie1', repetitions=10, runs=runs))
    text = (tmp_path / 'summary.txt').read_text()
    positions = [text.index(f'RUN {i:02d} —') for i in range(1, 11)]
    assert positions == sorted(positions)
    aggregate_at = text.index('ŚREDNIE STATYSTYKI Z 10 PRÓB')
    assert positions[-1] < aggregate_at < text.index('Success rate')
    first = text[positions[0]:positions[1]]
    tenth = text[positions[-1]:aggregate_at]
    assert 'Cała tura' in first and '1.000' in first
    assert 'Tokeny wejściowe: 10' in first
    assert 'Cała tura' in tenth and '10.000' in tenth
    assert 'Tokeny wejściowe: 100' in tenth
    data = json.loads((tmp_path / 'summary.json').read_text())
    assert data['statistics']['metrics']['Cała tura']['mean_s'] == 5.5
    assert data['success_rate_percent'] == 50
