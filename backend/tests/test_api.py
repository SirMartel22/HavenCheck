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

    @patch("app.GemmaClient.ask")
    def test_general_and_hostel_chat_histories_are_isolated(self, ask):
        ask.side_effect = [
            ("General reply", []),
            ("Hostel reply", []),
        ]
        hostel = self.client.post(
            "/hostels",
            json={
                "name": "Scoped Chat Lodge",
                "location": "Tanke",
                "priceNaira": 150000,
                "amenities": ["borehole"],
                "description": "A test listing.",
            },
        ).json()["data"]["hostel"]

        general_result = self.client.post(
            "/agent",
            json={"message": "General question", "sessionId": "scoped-session"},
        )
        hostel_result = self.client.post(
            "/agent",
            json={
                "message": "Hostel question",
                "sessionId": "scoped-session",
                "hostelId": hostel["id"],
            },
        )
        self.assertEqual(general_result.status_code, 200)
        self.assertEqual(hostel_result.status_code, 200)

        general_history = self.client.get(
            "/chat/history", params={"sessionId": "scoped-session"}
        ).json()["data"]["messages"]
        hostel_history = self.client.get(
            "/chat/history",
            params={"sessionId": "scoped-session", "hostelId": hostel["id"]},
        ).json()["data"]["messages"]

        self.assertEqual(
            [item["content"] for item in general_history],
            ["General question", "General reply"],
        )
        self.assertEqual(
            [item["content"] for item in hostel_history],
            ["Hostel question", "Hostel reply"],
        )

    @patch.dict(
        "os.environ",
        {"AGENT_RECENT_MESSAGE_LIMIT": "2"},
    )
    @patch("app.GemmaClient.ask", return_value=("Short reply", []))
    def test_agent_only_receives_bounded_recent_history(self, ask):
        for number in range(3):
            result = self.client.post(
                "/agent",
                json={
                    "message": f"Memory message {number}",
                    "sessionId": "bounded-memory-session",
                },
            )
            self.assertEqual(result.status_code, 200)

        model_history = ask.call_args.kwargs["history"]
        self.assertEqual(len(model_history), 2)
        self.assertEqual(
            [item["content"] for item in model_history],
            ["Short reply", "Memory message 2"],
        )

    @patch("app.GemmaClient.ask")
    def test_conversation_search_is_forced_to_active_session(self, ask):
        call_number = 0

        def answer(_message, dispatcher, history):
            nonlocal call_number
            call_number += 1
            if call_number < 3:
                return ("Stored reply", [])
            search_result = dispatcher(
                "searchConversationMemory",
                {"query": "private-needle", "role": "user"},
            )
            self.assertEqual(search_result["count"], 1)
            self.assertEqual(
                search_result["matches"][0]["content"],
                "My private-needle preference",
            )
            return ("I found your earlier message.", [])

        ask.side_effect = answer
        self.client.post(
            "/agent",
            json={
                "message": "My private-needle preference",
                "sessionId": "memory-owner",
            },
        )
        self.client.post(
            "/agent",
            json={
                "message": "Another private-needle message",
                "sessionId": "different-session",
            },
        )
        result = self.client.post(
            "/agent",
            json={
                "message": "What did I say earlier?",
                "sessionId": "memory-owner",
            },
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(
            result.json()["data"]["reply"],
            "I found your earlier message.",
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

    def test_openapi_documents_real_content_types_and_responses(self):
        schema = self.client.get("/openapi.json").json()

        create_content = schema["paths"]["/hostels"]["post"]["requestBody"]["content"]
        self.assertEqual(
            set(create_content),
            {
                "application/json",
                "multipart/form-data",
                "application/x-www-form-urlencoded",
            },
        )
        json_schema = create_content["application/json"]["schema"]
        self.assertIn("name", json_schema["properties"])
        self.assertIn("priceNaira", json_schema["properties"])
        self.assertNotIn("$ref", json_schema)
        photo_schema = create_content["multipart/form-data"]["schema"]["properties"]["photo"]
        self.assertEqual(photo_schema, {"type": "string", "format": "binary"})

        speak_responses = schema["paths"]["/voice/speak"]["post"]["responses"]
        self.assertIn("audio/mpeg", speak_responses["200"]["content"])
        transcribe_schema = schema["paths"]["/voice/transcribe"]["post"]["responses"]["200"]
        self.assertIn("application/json", transcribe_schema["content"])

    def test_openapi_documents_public_names_and_session_requirement(self):
        schema = self.client.get("/openapi.json").json()
        agent_request = schema["components"]["schemas"]["AgentRequest"]
        self.assertIn("sessionId", agent_request["properties"])
        self.assertIn("hostelId", agent_request["properties"])

        history_parameters = schema["paths"]["/chat/history"]["get"]["parameters"]
        self.assertEqual(
            {item["name"] for item in history_parameters},
            {"sessionId", "hostelId"},
        )


if __name__ == "__main__":
    unittest.main()
