import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from session_report import SessionReport


def test_report_measures_turns_requests_tools_and_partial_token_coverage(monkeypatch, tmp_path):
    monkeypatch.setattr('session_report.perf_counter', lambda: 100.0)
    report = SessionReport()
    turn = report.begin_turn()
    for kind, at, data in [
        ('speech_start', 100, {}), ('speech_end', 102.1, {}),
        ('transcription_ready', 102.45, {'text': 'Zadzwoń do Anny'}),
        ('agent_start', 102.46, {}),
        ('llm_start', 102.465, {'run_id': 'm1'}),
        ('llm_end', 103.1, {'run_id': 'm1', 'tools': ['get_contacts'], 'usage': {'input_tokens': 10, 'output_tokens': 2, 'total_tokens': 12}}),
        ('tool_start', 103.11, {'run_id': 't1', 'name': 'get_contacts', 'arguments': {}}),
        ('tool_end', 103.14, {'run_id': 't1', 'name': 'get_contacts', 'success': True}),
        ('llm_start', 103.15, {'run_id': 'm2'}),
        ('llm_end', 103.9, {'run_id': 'm2', 'usage': None}),
        ('agent_end', 103.91, {'text': 'Mobilny czy służbowy?'}),
        ('tts_start', 103.92, {}), ('tts_end', 104.2, {}),
        ('audio_start', 104.23, {}), ('audio_end', 105.8, {}),
    ]:
        report.emit(kind, turn_id=turn, at=at, **data)
    monkeypatch.setattr('session_report.perf_counter', lambda: 105.8)
    report.end_turn(turn, 'completed')
    text_path, json_path = report.save(tmp_path)
    data = json.loads(json_path.read_text())
    assert data['counts'] == {'completed': 1, 'failed': 0, 'interrupted': 0}
    assert data['metrics']['Czas mowy']['mean_s'] == pytest.approx(2.1)
    assert data['metrics']['Pojedyncze żądanie LLM']['n'] == 2
    assert data['metrics']['Pojedyncze żądanie LLM']['mean_s'] == pytest.approx(.6925)
    assert data['metrics']['Narzędzie: get_contacts']['mean_s'] == pytest.approx(.03)
    assert data['metrics']['Cała tura']['mean_s'] == pytest.approx(5.8)
    assert data['tokens'] == {'input_tokens': 10, 'output_tokens': 2, 'total_tokens': 12, 'known_requests': 1, 'missing_requests': 1}
    text = text_path.read_text()
    for expected in ['ASR: Vosk', 'LLM: gpt-4o-mini', 'TTS: Supertonic', 'TURA 1', '+02.450', 'Zadzwoń do Anny', 'get_contacts [OK]', 'Mobilny czy służbowy?', 'STATYSTYKI SESJI', 'estymacja Vosk']:
        assert expected in text


def test_missing_timings_are_not_zero_and_open_turn_is_interrupted(tmp_path):
    report = SessionReport()
    turn = report.begin_turn()
    report.emit('transcription_ready', turn_id=turn, text='test')
    report.emit('llm_start', turn_id=turn, run_id='unfinished')
    _, path = report.save(tmp_path)
    data = json.loads(path.read_text())
    assert data['counts']['interrupted'] == 1
    assert 'Czas mowy' not in data['metrics']
    assert 'Pojedyncze żądanie LLM' not in data['metrics']
    assert data['tokens']['missing_requests'] == 1


def test_overlapping_tools_are_paired_by_run_id_and_writes_are_thread_safe(monkeypatch):
    monkeypatch.setattr('session_report.perf_counter', lambda: 0)
    report = SessionReport()
    turn = report.begin_turn()
    report.emit('tool_start', turn_id=turn, at=1, run_id='a', name='search_track')
    report.emit('tool_start', turn_id=turn, at=2, run_id='b', name='search_track')
    report.emit('tool_end', turn_id=turn, at=3, run_id='b', name='search_track', success=False)
    report.emit('tool_end', turn_id=turn, at=5, run_id='a', name='search_track', success=True)
    with ThreadPoolExecutor(4) as pool:
        list(pool.map(lambda i: report.emit('touch', action=str(i)), range(100)))
    data = report.snapshot()
    assert data['metrics']['Narzędzie: search_track'] == {'n': 2, 'mean_s': 2.5, 'min_s': 1, 'max_s': 4}
    assert len([e for e in data['events'] if e['type'] == 'touch']) == 100


def test_empty_listening_is_not_a_turn(tmp_path):
    report = SessionReport()
    report.discard_empty_turn(report.begin_turn())
    text, data = report.save(tmp_path)
    assert json.loads(data.read_text())['turns'] == []
    assert 'brak danych' in text.read_text()


def test_warning_without_speech_is_session_history_not_a_voice_turn():
    report = SessionReport()
    turn = report.begin_turn()
    report.emit('asr_warning', turn_id=turn, warning='input overflow')
    report.discard_empty_turn(turn)
    data = report.snapshot()
    assert data['turns'] == []
    assert data['events'][0]['turn_id'] is None
    assert data['events'][0]['warning'] == 'input overflow'


def test_file_source_is_in_header_and_json_without_changing_metric_definitions(tmp_path):
    path = tmp_path / 'Telefon.mp3'
    report = SessionReport(audio_file=path)
    turn = report.begin_turn()
    report.emit('speech_start', turn_id=turn, at=report.started_timer)
    report.emit('speech_end', turn_id=turn, at=report.started_timer + 2)
    report.emit('transcription_ready', turn_id=turn, at=report.started_timer + 2.5, text='Zadzwoń')
    text_path, json_path = report.save(tmp_path)
    data = json.loads(json_path.read_text())
    assert data['input_source'] == {'type': 'audiofile', 'path': str(path)}
    assert 'Wejście: audiofile' in text_path.read_text().split('TURA 1')[0]
    assert str(path) in text_path.read_text()
    assert data['metrics']['Koniec mowy → transkrypcja']['mean_s'] == .5
    assert SessionReport().snapshot()['input_source'] == {'type': 'microphone'}
