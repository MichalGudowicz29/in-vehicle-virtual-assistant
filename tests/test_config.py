import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]


def run_with_config(project, working_directory, script):
    environment = {key: value for key, value in os.environ.items()
                   if key not in ('OLLAMA_MODEL', 'ASR_MODEL', 'OLLAMA_NUM_CTX',
                                  'OLLAMA_NUM_PREDICT', 'OLLAMA_REASONING')}
    environment['PYTHONPATH'] = os.pathsep.join([str(project), str(ROOT)])
    return subprocess.run([sys.executable, '-c', script], cwd=working_directory,
                          env=environment, text=True, capture_output=True, timeout=20)


def test_editing_one_env_file_updates_models_in_application_consumers(tmp_path):
    project = tmp_path / 'project'
    project.mkdir()
    (project / 'config.py').write_text((ROOT / 'config.py').read_text())
    working_directory = tmp_path / 'other directory'
    working_directory.mkdir()
    (working_directory / '.env').write_text('OLLAMA_MODEL=wrong:1b\nASR_MODEL=vosk\n')
    script = '''
import json
import config
import asr
from session_report import SessionReport
from voice_worker import VoiceWorker
report = SessionReport()
worker = VoiceWorker(None, report=report)
print(json.dumps(dict(llm=config.OLLAMA_MODEL, asr=asr.resolve_model(),
                     worker_asr=worker.asr, models=report.snapshot()['models'])))
'''
    for llm, asr, label in [('local-one:2b', 'whisper-small', 'Whisper small (whisper.cpp)'),
                            ('local-two:4b', 'whisper-medium', 'Whisper medium (whisper.cpp)')]:
        (project / '.env').write_text(f'OLLAMA_MODEL={llm}\nASR_MODEL={asr}\n')
        result = run_with_config(project, working_directory, script)
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout.splitlines()[-1])
        assert data == dict(llm=llm, asr=asr, worker_asr=asr,
                            models=dict(llm=llm, asr=label, tts='Supertonic'))


@pytest.mark.parametrize('contents, missing', [
    ('ASR_MODEL=vosk\n', 'OLLAMA_MODEL'),
    ('OLLAMA_MODEL=local:2b\n', 'ASR_MODEL'),
    ('OLLAMA_MODEL=local:2b\nASR_MODEL=\n', 'ASR_MODEL'),
])
def test_missing_model_is_reported_instead_of_using_a_hidden_default(tmp_path, contents, missing):
    (tmp_path / 'config.py').write_text((ROOT / 'config.py').read_text())
    (tmp_path / '.env').write_text(contents)
    result = run_with_config(tmp_path, tmp_path, 'import config')
    assert result.returncode != 0
    assert missing in result.stderr
    assert '.env' in result.stderr


@pytest.mark.parametrize('settings, expected', [
    ('', {'num_ctx': None, 'num_predict': None, 'reasoning': None}),
    ('OLLAMA_NUM_CTX=8192\nOLLAMA_NUM_PREDICT=128\nOLLAMA_REASONING=false\n',
     {'num_ctx': 8192, 'num_predict': 128, 'reasoning': False}),
    ('OLLAMA_REASONING=TRUE\n', {'num_ctx': None, 'num_predict': None, 'reasoning': True}),
])
def test_generation_settings_keep_unknown_defaults_and_parse_explicit_values(tmp_path, settings, expected):
    (tmp_path / 'config.py').write_text((ROOT / 'config.py').read_text())
    (tmp_path / '.env').write_text('OLLAMA_MODEL=local\nASR_MODEL=vosk\n' + settings)
    result = run_with_config(tmp_path, tmp_path, 'import config, json; print(json.dumps(config.LLM_GENERATION))')
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected


@pytest.mark.parametrize('name, value', [
    ('OLLAMA_NUM_CTX', '0'), ('OLLAMA_NUM_CTX', '-1'), ('OLLAMA_NUM_CTX', '1.5'),
    ('OLLAMA_NUM_PREDICT', '-2'), ('OLLAMA_NUM_PREDICT', 'many'),
    ('OLLAMA_REASONING', 'yes'), ('OLLAMA_REASONING', '0'),
])
def test_invalid_generation_settings_fail_with_variable_name(tmp_path, name, value):
    (tmp_path / 'config.py').write_text((ROOT / 'config.py').read_text())
    (tmp_path / '.env').write_text(f'OLLAMA_MODEL=local\nASR_MODEL=vosk\n{name}={value}\n')
    result = run_with_config(tmp_path, tmp_path, 'import config')
    assert result.returncode != 0
    assert name in result.stderr


def test_generation_settings_reload_after_environment_override(monkeypatch):
    import importlib
    import config

    try:
        with monkeypatch.context() as environment:
            environment.setenv('OLLAMA_NUM_CTX', '16384')
            environment.setenv('OLLAMA_NUM_PREDICT', '512')
            environment.setenv('OLLAMA_REASONING', 'false')
            importlib.reload(config)
            assert config.LLM_GENERATION == {'num_ctx': 16384, 'num_predict': 512, 'reasoning': False}
    finally:
        importlib.reload(config)
