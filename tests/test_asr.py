import json
import threading
import unittest
from unittest.mock import patch

import asr


class FakeRecognizer:
    def AcceptWaveform(self, data):
        return True

    def Result(self):
        return json.dumps({"text": "włącz muzykę"})


class FakeInputStream:
    def __init__(self, callback, **kwargs):
        self.callback = callback

    def __enter__(self):
        self.callback(b"audio", 1, None, None)
        return self

    def __exit__(self, *args):
        return False


class ListenTests(unittest.TestCase):
    def test_returns_first_completed_transcript_without_keyboard_input(self):
        with (
            patch.object(asr, "Model"),
            patch.object(asr.sd, "query_devices", return_value={"default_samplerate": 16000}),
            patch.object(asr, "KaldiRecognizer", return_value=FakeRecognizer()),
            patch.object(asr.sd, "RawInputStream", FakeInputStream),
        ):
            result = asr.listen(threading.Event())

        self.assertEqual(result, "włącz muzykę")


if __name__ == "__main__":
    unittest.main()
