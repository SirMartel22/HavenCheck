import os
import unittest
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///./test_api.db"

from fastapi.testclient import TestClient  # noqa: E402
from db import engine  # noqa: E402
from main import app  # noqa: E402


class ApiContractTests(unittest.TestCase):
    client = TestClient(app)

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

    def test_unknown_route_has_complete_envelope(self):
        response = self.client.get("/not-a-route")
        self.assertEqual(response.status_code, 404)
        self.assert_envelope(response.json())


if __name__ == "__main__":
    unittest.main()
