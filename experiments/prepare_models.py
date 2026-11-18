"""Prepare the runner's models; --check validates inputs before a series.

    uv run python -m experiments.prepare_models [--check]
"""

import argparse
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from urllib.request import urlretrieve
from zipfile import ZipFile

from asr import ASR_MODELS, MANUAL_ASR, WHISPER_MODELS
from experiments.runner import ROOT, SCENARIOS, RECORDINGS, VARIANTS


VOSK_MODEL = 'vosk-model-small-pl-0.22'
VOSK_URL = f'https://alphacephei.com/vosk/models/{VOSK_MODEL}.zip'
VOSK_FILES = ('am/final.mdl', 'conf/model.conf', 'conf/mfcc.conf',
              'graph/HCLr.fst', 'graph/Gr.fst', 'ivector/final.ie')


def _require_file(path):
    if not path.is_file() or path.stat().st_size == 0:
        raise FileNotFoundError(f'Brak lub pusty plik: {path}. Skopiuj go z komputera lokalnego.')


def _check_whisper(path):
    _require_file(path)
    with path.open('rb') as source:
        if source.read(4) != b'lmgg':
            raise ValueError(f'Niepoprawny nagłówek GGML: {path}; usuń wadliwy plik i pobierz ponownie.')


def _download_vosk(folder):
    target = folder / VOSK_MODEL
    if not target.exists():
        folder.mkdir(parents=True, exist_ok=True)
        # Publish only a completed extraction; interrupted setup can be retried.
        with TemporaryDirectory(dir=folder) as temporary:
            archive = Path(temporary) / 'model.zip'
            urlretrieve(VOSK_URL, archive)
            with ZipFile(archive) as source:
                source.extractall(temporary)
            (Path(temporary) / VOSK_MODEL).replace(target)
    for name in VOSK_FILES:
        _require_file(target / name)


def prepare(*, check=False):
    # Runner variants plus the default ASR of manual (microphone) use.
    asrs = list(dict.fromkeys([*(asr for _, asr, _ in VARIANTS), MANUAL_ASR]))
    llms = list(dict.fromkeys(llm for _, _, llm in VARIANTS))
    for asr in asrs:
        if asr not in ASR_MODELS:
            raise ValueError(f'Nieznany ASR w runner.VARIANTS: {asr}')
    for llm in llms:
        if not llm.strip() or 'cloud' in llm.lower():
            raise ValueError(f'Wymagany lokalny model Ollama: {llm!r}')
    if check:
        for scenario in SCENARIOS.values():
            for number in range(1, RECORDINGS + 1):
                _require_file(ROOT / 'assets/voice' / scenario['title'] / f'{number}.mp3')
        for number in range(1, 4):
            _require_file(ROOT / 'music' / f'{number}.mp3')
        if 'vosk' in asrs:
            for name in VOSK_FILES:
                _require_file(ROOT / 'models' / VOSK_MODEL / name)
        for asr in asrs:
            if asr in WHISPER_MODELS:
                _check_whisper(ROOT / 'models/whisper' / f'ggml-{WHISPER_MODELS[asr]}.bin')
    for llm in llms:
        print(f'Ollama: {llm}', flush=True)
        subprocess.run(['ollama', 'show' if check else 'pull', llm], check=True,
                       env=dict(os.environ, OLLAMA_HOST='127.0.0.1:11434'))
    if not check:
        from pywhispercpp.utils import download_model

        folder = ROOT / 'models/whisper'
        folder.mkdir(parents=True, exist_ok=True)
        if 'vosk' in asrs:
            _download_vosk(ROOT / 'models')
        for asr in asrs:
            if asr not in WHISPER_MODELS:
                continue
            size = WHISPER_MODELS[asr]
            path = folder / f'ggml-{size}.bin'
            if not path.exists():
                # Publish only a completed download; interrupted setup can be retried.
                with TemporaryDirectory(dir=folder) as temporary:
                    downloaded = Path(download_model(size, Path(temporary)))
                    _check_whisper(downloaded)
                    downloaded.replace(path)
            _check_whisper(path)
    from supertonic import TTS

    TTS(auto_download=not check).get_voice_style('M2')
    print('Modele sprawdzone.' if check else 'Modele przygotowane.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Sprawdź modele i pliki wejściowe bez pobierania.')
    args = parser.parse_args()
    try:
        prepare(check=args.check)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f'Przygotowanie modeli nieudane: {error}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
