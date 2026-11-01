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
            turns=[dict(id=1, status='completed')], events=events, duration_s=1.5)
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
