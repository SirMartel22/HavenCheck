import json
import sys
import httpx

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
MESSAGES = [
    "Is 150000 naira for a room in Tanke fair? It has borehole and prepaid meter.",
    "Has bd616ac1-3824-5a90-ae8a-ba1a0929c261 had water or electricity problems?",
    "Is this suspicious: Pay the inspection fee now before viewing. Address later. Today only!",
]

for index, message in enumerate(MESSAGES, start=1):
    try:
        response = httpx.post(
            f"{BASE_URL}/agent",
            json={"message": message, "sessionId": f"curl-agent-sample-{index}"},
            timeout=60,
        )
        print(json.dumps(response.json(), indent=2))
    except Exception as exc:
        print(f"Request failed: {exc}")
