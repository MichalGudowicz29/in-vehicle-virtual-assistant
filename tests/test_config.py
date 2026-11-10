import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]


def run_with_config(project, working_directory, script):
    environment = {key: value for key, value in os.environ.items()
                   if key not in ('OLLAMA_MODEL', 'ASR_MODEL')}
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
