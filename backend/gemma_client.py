import json
import os
from typing import Any
import httpx

TOOL_DECLARATIONS = [
    {"name": "checkRentFairness", "description": "Compares a quoted hostel rent price against typical prices for the area and amenities to flag overpricing.", "parameters": {"type": "object", "properties": {"location": {"type": "string"}, "priceNaira": {"type": "number"}, "amenities": {"type": "array", "items": {"type": "string"}}}, "required": ["location", "priceNaira"]}},
    {"name": "checkUtilityReliability", "description": "Retrieves and summarizes recent crowd-sourced reports on water and electricity reliability for a specific hostel.", "parameters": {"type": "object", "properties": {"hostelId": {"type": "string"}}, "required": ["hostelId"]}},
    {"name": "flagScamRisk", "description": "Analyzes listing text or landlord/agent chat messages for common racketeering or scam patterns.", "parameters": {"type": "object", "properties": {"listingText": {"type": "string"}, "chatTranscript": {"type": "string"}}, "required": ["listingText"]}},
    {"name": "notifyHostelAuthority", "description": "Sends a water or electricity complaint for a school-managed hostel to the relevant authority via email.", "parameters": {"type": "object", "properties": {"hostelId": {"type": "string"}, "issueType": {"type": "string", "enum": ["water", "electricity", "other"]}, "details": {"type": "string"}}, "required": ["hostelId", "issueType", "details"]}},
    {"name": "alertCommunitySecurity", "description": "Sends an alert about a suspected off-campus racketeer or scam landlord to community security via email.", "parameters": {"type": "object", "properties": {"hostelId": {"type": "string"}, "reason": {"type": "string"}, "evidence": {"type": "string"}}, "required": ["hostelId", "reason"]}},
]

SYSTEM_PROMPT = "You are Housing Scout for off-campus Unilorin students. Use the provided tools for factual checks and escalation. Never invent database facts or claim an email was sent unless its tool result says sent. Give a concise, clear verdict and practical next step."


class GemmaError(RuntimeError):
    pass


class GemmaClient:
    def __init__(self):
        self.api_key = os.getenv("GEMMA_API_KEY")
        model = os.getenv("GEMMA_MODEL", "gemma-3-27b-it")
        self.url = os.getenv("GEMMA_API_URL", f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent")

    def _post(self, payload: dict) -> dict:
        if not self.api_key:
            raise GemmaError("GEMMA_API_KEY is not configured")
        try:
            response = httpx.post(self.url, params={"key": self.api_key}, json=payload, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            raise GemmaError(f"Gemma request failed: {exc}") from exc

    @staticmethod
    def _parts(response: dict) -> list[dict]:
        try:
            return response["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError, TypeError) as exc:
            raise GemmaError("Gemma returned an unexpected response") from exc

    def ask(self, message: str, dispatcher) -> tuple[str, list[dict]]:
        contents: list[dict] = [{"role": "user", "parts": [{"text": message}]}]
        calls_made: list[dict] = []
        for _ in range(4):
            payload = {"systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]}, "contents": contents, "tools": [{"functionDeclarations": TOOL_DECLARATIONS}]}
            response = self._post(payload)
            parts = self._parts(response)
            calls = [part["functionCall"] for part in parts if "functionCall" in part]
            if not calls:
                text = "".join(part.get("text", "") for part in parts).strip()
                return text or "I could not produce a reply.", calls_made
            contents.append({"role": "model", "parts": parts})
            result_parts = []
            for call in calls:
                name, args = call.get("name"), call.get("args", {})
                try:
                    result = dispatcher(name, args)
                except Exception as exc:
                    result = {"error": f"Tool failed safely: {exc}"}
                calls_made.append({"name": name, "arguments": args, "result": result, "error": result.get("error") if isinstance(result, dict) else None})
                result_parts.append({"functionResponse": {"name": name, "response": {"result": result}}})
            contents.append({"role": "user", "parts": result_parts})
        raise GemmaError("Gemma exceeded the maximum tool-call rounds")

    def explain_scam_flags(self, text: str, flags: list[str]) -> list[str]:
        prompt = f"Give exactly one short reason for each scam flag as a JSON string array. Flags: {json.dumps(flags)}. Text: {text[:4000]}"
        response = self._post({"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json"}})
        raw = "".join(p.get("text", "") for p in self._parts(response))
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
