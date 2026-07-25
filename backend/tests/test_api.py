import os
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite:///./test_api.db"

from fastapi.testclient import TestClient  # noqa: E402
from db import engine  # noqa: E402
from app import app  # noqa: E402


class ApiContractTests(unittest.TestCase):
    client = TestClient(app)

    @classmethod
    def setUpClass(cls):
        from db import Base
        Base.metadata.create_all(bind=engine)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        engine.dispose()
        Path("test_api.db").unlink(missing_ok=True)

    def assert_envelope(self, body):
        self.assertEqual(set(body), {"message", "data", "action", "error"})

    def test_health_has_complete_envelope(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assert_envelope(response.json())
        self.assertIsNone(response.json()["action"])
        self.assertIsNone(response.json()["error"])

    def test_not_found_has_complete_envelope(self):
        response = self.client.get("/hostels/does-not-exist")
        self.assertEqual(response.status_code, 404)
        self.assert_envelope(response.json())
        self.assertEqual(set(response.json()["error"]), {"code", "details"})

    def test_validation_error_has_complete_envelope(self):
        response = self.client.post("/agent", json={})
        self.assertEqual(response.status_code, 422)
        self.assert_envelope(response.json())
        self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")

    def test_agent_requires_session_id_with_400(self):
        response = self.client.post("/agent", json={"message": "Hello"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["details"], "sessionId is required")

    def test_history_requires_session_id_with_400(self):
        response = self.client.get("/chat/history")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["details"], "sessionId is required")

    @patch("app.GemmaClient.ask")
    def test_agent_history_is_scoped_to_session(self, ask):
        ask.side_effect = [
            ("Reply for session A", []),
            ("Reply for session B", []),
        ]
        first = self.client.post(
            "/agent",
            json={"message": "Private message A", "sessionId": "session-a"},
        )
        second = self.client.post(
            "/agent",
            json={"message": "Private message B", "sessionId": "session-b"},
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)

        history_a = self.client.get(
            "/chat/history", params={"sessionId": "session-a"}
        ).json()["data"]["messages"]
        history_b = self.client.get(
            "/chat/history", params={"sessionId": "session-b"}
        ).json()["data"]["messages"]
        self.assertEqual(
            [item["content"] for item in history_a],
            ["Private message A", "Reply for session A"],
        )
        self.assertEqual(
            [item["content"] for item in history_b],
            ["Private message B", "Reply for session B"],
        )
        second_call_history = ask.call_args_list[1].kwargs["history"]
        self.assertNotIn(
            "Private message A",
            [item["content"] for item in second_call_history],
        )

    @patch("app.transcribe_audio", return_value="Transcribed speech")
    def test_voice_transcribe(self, _transcribe):
        result = self.client.post(
            "/voice/transcribe",
            files={"audio": ("recording.webm", b"audio", "audio/webm")},
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json(), {"text": "Transcribed speech"})

    @patch("app.speak", return_value=b"mp3-audio")
    def test_voice_speak_has_stable_audio_response(self, _speak):
        result = self.client.post("/voice/speak", json={"text": "Hello"})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.headers["content-type"], "audio/mpeg")
        self.assertEqual(result.content, b"mp3-audio")

    @patch("app.speak", return_value=b"voice-chat-mp3")
    @patch("app.GemmaClient.ask", return_value=("Voice chat reply", []))
    @patch("app.transcribe_audio", return_value="Voice chat question")
    def test_voice_chat_orchestrates_and_saves_history(
        self, _transcribe, _ask, _speak
    ):
        result = self.client.post(
            "/voice/chat",
            data={"sessionId": "voice-session", "speakReply": "true"},
            files={"audio": ("recording.webm", b"audio", "audio/webm")},
        )
        self.assertEqual(result.status_code, 200)
        data = result.json()["data"]
        self.assertEqual(data["transcript"], "Voice chat question")
        self.assertEqual(data["reply"], "Voice chat reply")
        self.assertEqual(data["audioContentType"], "audio/mpeg")
        self.assertIsNotNone(data["audioBase64"])

        history = self.client.get(
            "/chat/history", params={"sessionId": "voice-session"}
        ).json()["data"]["messages"]
        self.assertEqual(
            [item["content"] for item in history],
            ["Voice chat question", "Voice chat reply"],
        )

    def test_voice_chat_requires_session_id(self):
        result = self.client.post(
            "/voice/chat",
            files={"audio": ("recording.webm", b"audio", "audio/webm")},
        )
        self.assertEqual(result.status_code, 400)

    def test_unknown_route_has_complete_envelope(self):
        response = self.client.get("/not-a-route")
        self.assertEqual(response.status_code, 404)
        self.assert_envelope(response.json())


if __name__ == "__main__":
    unittest.main()
