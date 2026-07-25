import os
import unittest
from unittest.mock import Mock, patch

from voice import (
    call_easyvoice_tts,
    call_elevenlabs_tts,
    speak,
    transcribe_audio,
)


class VoiceProviderTests(unittest.TestCase):
    @patch("voice.httpx.post")
    def test_groq_transcription(self, post):
        response = Mock()
        response.json.return_value = {"text": "hello from audio"}
        response.raise_for_status.return_value = None
        post.return_value = response
        with patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}, clear=False):
            result = transcribe_audio(b"audio", "sample.webm", "audio/webm")
        self.assertEqual(result, "hello from audio")
        self.assertIn("audio/transcriptions", post.call_args.args[0])

    @patch("voice.httpx.post")
    def test_easyvoice_returns_mp3_bytes(self, post):
        response = Mock(content=b"easyvoice-mp3")
        response.raise_for_status.return_value = None
        post.return_value = response
        env = {
            "EASYVOICE_API_KEY": "test-key",
            "EASYVOICE_API_URL": "https://easyvoice.example/v1/audio/speech",
        }
        with patch.dict(os.environ, env, clear=False):
            result = call_easyvoice_tts("Hello")
        self.assertEqual(result, b"easyvoice-mp3")
        self.assertEqual(
            post.call_args.args[0],
            "https://easyvoice.example/v1/audio/speech",
        )

    @patch("voice.httpx.post")
    def test_elevenlabs_returns_mp3_bytes(self, post):
        response = Mock(content=b"elevenlabs-mp3")
        response.raise_for_status.return_value = None
        post.return_value = response
        env = {
            "ELEVENLABS_API_KEY": "test-key",
            "ELEVENLABS_VOICE_ID": "voice-id",
        }
        with patch.dict(os.environ, env, clear=False):
            result = call_elevenlabs_tts("Hello")
        self.assertEqual(result, b"elevenlabs-mp3")
        self.assertTrue(post.call_args.args[0].endswith("/voice-id"))

    @patch("voice.call_easyvoice_tts", return_value=b"easyvoice")
    @patch("voice.call_elevenlabs_tts", return_value=b"elevenlabs")
    def test_provider_switch(self, elevenlabs, easyvoice):
        with patch.dict(os.environ, {"TTS_PROVIDER": "easyvoice"}, clear=False):
            self.assertEqual(speak("Hello"), b"easyvoice")
        easyvoice.assert_called_once_with("Hello")

        with patch.dict(os.environ, {"TTS_PROVIDER": "elevenlabs"}, clear=False):
            self.assertEqual(speak("Hello"), b"elevenlabs")
        elevenlabs.assert_called_once_with("Hello")


if __name__ == "__main__":
    unittest.main()
