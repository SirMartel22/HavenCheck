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
        self.google_api_key = os.getenv("GEMMA_API_KEY")
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        
        google_model = os.getenv("GEMMA_MODEL", "gemma-2-27b-it")
        self.google_url = os.getenv("GEMMA_API_URL", f"https://generativelanguage.googleapis.com/v1beta/models/{google_model}:generateContent")
        
        openrouter_model = os.getenv("OPENROUTER_MODEL", "google/gemma-2-27b-it:free")
        self.openrouter_url = os.getenv("OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions")
        self.openrouter_model = openrouter_model

    def _post_google(self, payload: dict) -> dict:
        if not self.google_api_key:
            raise GemmaError("GEMMA_API_KEY is not configured")
        try:
            response = httpx.post(self.google_url, params={"key": self.google_api_key}, json=payload, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            raise GemmaError(f"Google Gemma request failed: {exc}") from exc

    def _post_openrouter(self, payload: dict) -> dict:
        if not self.openrouter_api_key:
            raise GemmaError("OPENROUTER_API_KEY is not configured")
        try:
            headers = {
                "Authorization": f"Bearer {self.openrouter_api_key}",
                "HTTP-Referer": "https://housing-scout.local",
                "X-Title": "Housing Scout",
            }
            response = httpx.post(self.openrouter_url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            raise GemmaError(f"OpenRouter request failed: {exc}") from exc

    @staticmethod
    def _parts(response: dict, provider: str = "google") -> list[dict]:
        try:
            if provider == "google":
                return response["candidates"][0]["content"]["parts"]
            elif provider == "openrouter":
                # Convert OpenRouter format to Google format
                content = response["choices"][0]["message"]["content"]
                return [{"text": content}]
        except (KeyError, IndexError, TypeError) as exc:
            raise GemmaError(f"{provider} returned an unexpected response") from exc

    def ask(
        self,
        message: str,
        dispatcher,
        history: list[dict[str, str]] | None = None,
    ) -> tuple[str, list[dict]]:
        # Use Google API for full tool-calling flow (most reliable)
        contents: list[dict] = [
            {
                "role": "model" if item["role"] == "assistant" else "user",
                "parts": [{"text": item["content"]}],
            }
            for item in (history or [])
        ]
        if not contents:
            contents = [{"role": "user", "parts": [{"text": message}]}]
        calls_made: list[dict] = []
        for _ in range(4):
            payload = {"systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]}, "contents": contents, "tools": [{"functionDeclarations": TOOL_DECLARATIONS}]}
            try:
                response = self._post_google(payload)
            except Exception as exc:
                # Try OpenRouter as fallback
                try:
                    openrouter_messages = [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        *[
                            {
                                "role": item["role"],
                                "content": item["content"],
                            }
                            for item in (history or [{"role": "user", "content": message}])
                        ],
                    ]
                    response = self._post_openrouter({"model": self.openrouter_model, "messages": openrouter_messages, "temperature": 1})
                    provider = "openrouter"
                except:
                    raise GemmaError(f"Both APIs failed for ask(): {exc}") from exc
            else:
                provider = "google"
            
            parts = self._parts(response, provider)
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
        
        try:
            response = self._post_google({"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json"}})
            provider = "google"
        except Exception as exc:
            try:
                response = self._post_openrouter({"model": self.openrouter_model, "messages": [{"role": "user", "content": prompt}], "temperature": 1})
                provider = "openrouter"
            except:
                raise GemmaError(f"explain_scam_flags failed on both APIs: {exc}") from exc
        
        raw = "".join(p.get("text", "") for p in self._parts(response, provider))
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
