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


def test_runner_starts_three_processes_and_saves_configuration_and_results(monkeypatch, tmp_path):
    import runner
    project = tmp_path / 'project with spaces'
    (project / 'assets/voice').mkdir(parents=True)
    (project / 'assets/voice/Telefon.mp3').write_bytes(b'test input')
    script = '''
import argparse, json, os
from pathlib import Path
parser = argparse.ArgumentParser()
parser.add_argument('--audio-file')
parser.add_argument('--report-dir', type=Path)
parser.add_argument('--asr')
args = parser.parse_args()
args.report_dir.mkdir(parents=True, exist_ok=True)
run = int(args.report_dir.name[-2:])
with Path('order.txt').open('a') as order:
    order.write(str(run))
events = []
if run != 2:
    events = [dict(type='tool_start', turn_id=1, run_id='call', name='call_contact',
                   arguments=dict(name='Robert Lewandowski', number_type='mobile')),
              dict(type='tool_end', turn_id=1, run_id='call', name='call_contact', success=run == 1)]
data = dict(session_id=f'session_{run}', models=dict(asr='Vosk small-pl-0.22', llm=os.environ['OLLAMA_MODEL'], tts='Supertonic'),
            input_source=dict(type='audiofile', path=args.audio_file),
            turns=[dict(id=1, status='completed')], events=events, duration_s=1.5,
            metrics={'Cała tura': dict(n=1, mean_s=float(run), min_s=float(run), max_s=float(run))}, tokens={})
(args.report_dir / f'session_{run}.json').write_text(json.dumps(data))
(args.report_dir / f'session_{run}.txt').write_text('session report')
print('Child process finished')
'''
    (project / 'main.py').write_text(script)
    monkeypatch.setattr(runner, 'ROOT', project)
    monkeypatch.setattr(runner.config, 'ASR_MODEL', 'vosk')
    monkeypatch.setattr(runner.config, 'OLLAMA_MODEL', 'test/model:2b')
    assert runner.main() == 1  # One success, two task failures.
    assert (project / 'order.txt').read_text() == '123'
    experiment, = (project / 'logs/eksperymenty').iterdir()
    assert len(list(experiment.glob('run_*/session_*.json'))) == 3
    summary = json.loads((experiment / 'summary.json').read_text())
    assert [run['success'] for run in summary['runs']] == [True, False, False]
    assert summary['success_count'] == 1
    assert summary['repetitions'] == 3
    assert summary['success_rate_percent'] == pytest.approx(100 / 3)
    assert summary['statistics']['metrics']['Cała tura']['mean_s'] == 2
    assert summary['best_run']['run'] == summary['worst_run']['run'] == 1
    configuration = (experiment / 'config.txt').read_text()
    for value in ('Robert Lewandowski', 'mobile', 'call_contact', 'test/model:2b', 'vosk', '3', 'Telefon.mp3'):
        assert value in configuration
    assert (experiment / 'run_01/console.log').read_text().strip() == 'Child process finished'
    assert '1/3' in (experiment / 'summary.txt').read_text()


def test_runner_records_timeout_and_continues_all_three_trials(monkeypatch, tmp_path):
    import runner
    (tmp_path / 'assets/voice').mkdir(parents=True)
    (tmp_path / 'assets/voice/Telefon.mp3').touch()
    (tmp_path / 'main.py').write_text('import time; time.sleep(5)')
    monkeypatch.setattr(runner, 'ROOT', tmp_path)
    monkeypatch.setattr(runner, 'TIMEOUT_S', .1)
    assert runner.main() == 1
    experiment, = (tmp_path / 'logs/eksperymenty').iterdir()
    summary = json.loads((experiment / 'summary.json').read_text())
    assert len(summary['runs']) == 3
    assert all(not run['success'] and 'limit' in run['reason'] for run in summary['runs'])


@pytest.mark.parametrize('problem, script, reason', [
    ('missing', 'pass', 'raportu JSON'),
    ('malformed', "from pathlib import Path; Path(__import__('sys').argv[-1], 'session_bad.json').write_text('{')", 'Expecting'),
    ('nonzero', "raise SystemExit(7)", 'kodem 7'),
])
def test_invalid_child_execution_is_recorded_instead_of_counted_as_success(monkeypatch, tmp_path, problem, script, reason):
    import runner
    (tmp_path / 'assets/voice').mkdir(parents=True)
    (tmp_path / 'assets/voice/Telefon.mp3').touch()
    (tmp_path / 'main.py').write_text(script)
    monkeypatch.setattr(runner, 'ROOT', tmp_path)
    assert runner.main() == 1
    experiment, = (tmp_path / 'logs/eksperymenty').iterdir()
    summary = json.loads((experiment / 'summary.json').read_text())
    assert summary['success_count'] == 0
    assert len(summary['runs']) == 3
    assert all(reason in run['reason'] for run in summary['runs'])


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
