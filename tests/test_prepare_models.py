import subprocess
import sys
from types import SimpleNamespace
from zipfile import ZipFile

import pytest


def test_models_follow_runner_and_are_pulled_once(monkeypatch, tmp_path):
    import prepare_models

    monkeypatch.setattr(prepare_models, 'ROOT', tmp_path)
    monkeypatch.setattr(prepare_models, 'VARIANTS', (
        ('A', 'vosk', 'test:2b'), ('B', 'whisper-small', 'test:2b'),
        ('C', 'whisper-medium', 'test:4b'),
    ))
    calls, downloads, tts_options = [], [], []
    monkeypatch.setattr(subprocess, 'run', lambda args, **kwargs: calls.append((args, kwargs)))

    def download(size, folder):
        downloads.append(size)
        path = folder / f'ggml-{size}.bin'
        path.write_bytes(b'lmgg' + b'model')
        return str(path)

    def fetch_vosk(url, archive):
        downloads.append(url)
        with ZipFile(archive, 'w') as target:
            for name in prepare_models.VOSK_FILES:
                target.writestr(f'{prepare_models.VOSK_MODEL}/{name}', b'weights')

    monkeypatch.setattr(prepare_models, 'urlretrieve', fetch_vosk)
    monkeypatch.setitem(sys.modules, 'pywhispercpp.utils', SimpleNamespace(download_model=download))
    monkeypatch.setitem(sys.modules, 'supertonic', SimpleNamespace(
        TTS=lambda **kwargs: (tts_options.append(kwargs) or SimpleNamespace(get_voice_style=lambda name: None))))
    prepare_models.prepare(check=False)
    assert [call[0] for call in calls] == [
        ['ollama', 'pull', 'test:2b'], ['ollama', 'pull', 'test:4b']]
    assert all(call[1]['check'] and call[1]['env']['OLLAMA_HOST'] == '127.0.0.1:11434' for call in calls)
    assert downloads == [prepare_models.VOSK_URL, 'small', 'medium']
    assert (tmp_path / 'models' / prepare_models.VOSK_MODEL / 'am/final.mdl').read_bytes() == b'weights'
    assert tts_options == [{'auto_download': True}]
    assert (tmp_path / 'models/whisper/ggml-small.bin').read_bytes().startswith(b'lmgg')


def test_check_refuses_missing_inputs_before_contacting_ollama(monkeypatch, tmp_path):
    import prepare_models

    monkeypatch.setattr(prepare_models, 'ROOT', tmp_path)
    monkeypatch.setattr(subprocess, 'run', lambda *args, **kwargs: pytest.fail('No network before asset validation'))
    with pytest.raises(FileNotFoundError, match='Muzyka/1.mp3'):
        prepare_models.prepare(check=True)


def test_check_uses_cached_models_without_downloads(monkeypatch, tmp_path):
    import prepare_models

    monkeypatch.setattr(prepare_models, 'ROOT', tmp_path)
    monkeypatch.setattr(prepare_models, 'VARIANTS', (('A', 'whisper-small', 'test:2b'),))
    for title in ('Muzyka', 'Telefon', 'Nawigacja'):
        folder = tmp_path / 'assets/voice' / title
        folder.mkdir(parents=True)
        for number in range(1, 4):
            (folder / f'{number}.mp3').write_bytes(b'audio')
    (tmp_path / 'music').mkdir()
    for number in range(1, 4):
        (tmp_path / 'music' / f'{number}.mp3').write_bytes(b'music')
    weights = tmp_path / 'models/whisper/ggml-small.bin'
    weights.parent.mkdir(parents=True)
    weights.write_bytes(b'lmggcached model')
    calls, tts_options = [], []
    monkeypatch.setattr(subprocess, 'run', lambda args, **kwargs: calls.append(args))
    monkeypatch.setitem(sys.modules, 'pywhispercpp.utils', SimpleNamespace(
        download_model=lambda *args: pytest.fail('Check must not download')))
    monkeypatch.setitem(sys.modules, 'supertonic', SimpleNamespace(
        TTS=lambda **kwargs: (tts_options.append(kwargs) or SimpleNamespace(get_voice_style=lambda name: None))))
    prepare_models.prepare(check=True)
    assert calls == [['ollama', 'show', 'test:2b']]
    assert tts_options == [{'auto_download': False}]
    assert weights.read_bytes() == b'lmggcached model'


def test_failed_download_does_not_leave_model_in_final_location(monkeypatch, tmp_path):
    import prepare_models

    monkeypatch.setattr(prepare_models, 'ROOT', tmp_path)
    monkeypatch.setattr(prepare_models, 'VARIANTS', (('A', 'whisper-small', 'test:2b'),))
    monkeypatch.setattr(subprocess, 'run', lambda *args, **kwargs: None)

    def bad_download(size, folder):
        path = folder / f'ggml-{size}.bin'
        path.write_bytes(b'<html>not a model</html>')
        return str(path)

    monkeypatch.setitem(sys.modules, 'pywhispercpp.utils', SimpleNamespace(download_model=bad_download))
    with pytest.raises(ValueError, match='GGML'):
        prepare_models.prepare(check=False)
    assert not (tmp_path / 'models/whisper/ggml-small.bin').exists()
