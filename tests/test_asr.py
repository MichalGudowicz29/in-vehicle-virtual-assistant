import json
import threading
import unittest
from unittest.mock import patch

import asr


class FakeRecognizer:
    def __init__(self):
        self.received_audio = []

    def AcceptWaveform(self, data):
        self.received_audio.append(data)
        return True

    def Result(self):
        return json.dumps({"text": "włącz muzykę"})


class FakeInputStream:
    def __init__(self, callback, **kwargs):
        self.callback = callback
        self.kwargs = kwargs

    def __enter__(self):
        self.callback(b"fake audio", 1, None, None)
        return self

    def __exit__(self, *args):
        return False


class ListenTests(unittest.TestCase):
    def test_listen_returns_recognized_text(self):
        fake_recognizer = FakeRecognizer()

        with (
            patch.object(asr, "_get_model"),
            patch.object(
                asr.sd,
                "query_devices",
                return_value={"default_samplerate": 16000},
            ),
            patch.object(
                asr,
                "KaldiRecognizer",
                return_value=fake_recognizer,
            ),
            patch.object(
                asr.sd,
                "RawInputStream",
                FakeInputStream,
            ),
        ):
            result = asr.listen(threading.Event())

        self.assertEqual(result, "włącz muzykę")
        self.assertEqual(fake_recognizer.received_audio, [b"fake audio"])


if __name__ == "__main__":
    unittest.main()
