from threading import Event

import pytest

import asr
from session_report import SessionReport


def test_unknown_asr_is_rejected_before_opening_input():
    with pytest.raises(ValueError, match='Nieznany ASR'):
        asr.listen(Event(), asr='whisper-typo')


def test_selected_asr_is_reported_in_txt_and_json(tmp_path):
    report = SessionReport(asr_model='whisper-small')
    text_path, _ = report.save(tmp_path)
    assert report.snapshot()['models']['asr'] == 'Whisper small (whisper.cpp)'
    assert 'WebRTC VAD' in text_path.read_text()
    assert 'estymacja Vosk' not in text_path.read_text()


def test_default_asr_is_reported_and_matches_runner_label():
    from experiments import runner
    assert SessionReport().snapshot()['models']['asr'] == asr.model_label(asr.DEFAULT_ASR)
    assert (runner.ASR, runner.ASR_LABEL) == (asr.DEFAULT_ASR, asr.model_label(asr.DEFAULT_ASR))


def test_worker_rejects_mislabeled_report():
    from voice_worker import VoiceWorker
    report = SessionReport(asr_model='vosk')
    with pytest.raises(ValueError, match='zgodny'):
        VoiceWorker(None, report=report, asr='whisper-small')
