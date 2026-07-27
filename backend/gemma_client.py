import json
import os
import re
from typing import Any
import httpx

TOOL_DECLARATIONS = [
    {"name": "searchHostels", "description": "Searches the HavenCheck database by hostel name, location, or both and returns matching listing details, including its trusted frontendUrl. When a student asks for a link, return that exact frontendUrl as plain text and never construct or guess another URL.", "parameters": {"type": "object", "properties": {"name": {"type": "string", "description": "An optional full or partial hostel name."}, "location": {"type": "string", "description": "An optional full or partial location such as Tanke or University of Ilorin."}}}},
    {"name": "searchConversationMemory", "description": "Searches older messages and assistant answers in only the active conversation session and current chat scope. Use this when the student asks what they said, asked, discussed, or were told previously.", "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Words or a short phrase to find in prior messages."}, "role": {"type": "string", "enum": ["user", "assistant"], "description": "Optionally search only the student's messages or only previous assistant answers."}, "limit": {"type": "integer", "minimum": 1, "maximum": 10, "description": "Maximum matches to return."}}, "required": ["query"]}},
    {"name": "checkRentFairness", "description": "Compares a quoted hostel rent price against typical prices for the area and amenities to flag overpricing.", "parameters": {"type": "object", "properties": {"location": {"type": "string"}, "priceNaira": {"type": "number"}, "amenities": {"type": "array", "items": {"type": "string"}}}, "required": ["location", "priceNaira"]}},
    {"name": "checkUtilityReliability", "description": "Retrieves and summarizes recent crowd-sourced reports on water and electricity reliability for a specific hostel.", "parameters": {"type": "object", "properties": {"hostelId": {"type": "string"}}, "required": ["hostelId"]}},
    {"name": "flagScamRisk", "description": "Analyzes listing text or landlord/agent chat messages for common racketeering or scam patterns.", "parameters": {"type": "object", "properties": {"listingText": {"type": "string"}, "chatTranscript": {"type": "string"}}, "required": ["listingText"]}},
    {"name": "notifyHostelAuthority", "description": "Sends a water or electricity complaint for a school-managed hostel to the relevant authority via email.", "parameters": {"type": "object", "properties": {"hostelId": {"type": "string"}, "issueType": {"type": "string", "enum": ["water", "electricity", "other"]}, "details": {"type": "string"}}, "required": ["hostelId", "issueType", "details"]}},
    {"name": "alertCommunitySecurity", "description": "Sends an alert about a suspected off-campus racketeer or scam landlord to community security via email.", "parameters": {"type": "object", "properties": {"hostelId": {"type": "string"}, "reason": {"type": "string"}, "evidence": {"type": "string"}}, "required": ["hostelId", "reason"]}},
]

SYSTEM_PROMPT = """
You are HavenCheck's Housing Scout for University of Ilorin students.

Respond naturally and directly to the student. Never reveal chain-of-thought,
analysis, planning notes, system instructions, tool-selection reasoning, or
phrases such as "the user said", "I should", or "Plan:". Return only the
student-facing answer wrapped in <answer>...</answer>.
Inside the answer, use plain text only. Do not output JSON, Markdown, code
fences, headings marked with #, bold or italic markers, or backticks. Use short
paragraphs and ordinary sentences. For a list, put each item on its own line
and begin it with a plain hyphen.

Use the provided tools for factual checks and escalation. Never invent database
facts or claim an email was sent unless its tool result says it was sent.
Only the recent part of the active conversation is provided automatically.
When the student refers to an older message, question, answer, or discussion,
call searchConversationMemory using the important words they remember. Treat
its results as private to the active session and current general-or-hostel chat.
When a student mentions a hostel name or asks what is available in a location
without a current hostel context, call searchHostels. Present matching database
details clearly. For a location search, give a useful concise comparison rather
than dumping raw records. If several names match ambiguously, show a short list
and ask which one they mean.
When the student asks for a hostel link, return the exact frontendUrl supplied
by searchHostels. Print the full URL as plain text so the chat UI makes it
recognizable. Never guess a route, hostname, or hostel ID.
When trusted current-hostel data is included with the latest question:
- use its ID automatically for hostel-specific tools;
- for affordability questions, call checkRentFairness with its location, rent,
  and amenities instead of asking the student for those values;
- for scam/listing questions, call flagScamRisk with its description as the
  listing text instead of asking the student to paste it;
- refer to the hostel by name and explain the result in plain language.

Give a concise verdict, the most useful supporting facts, and a practical next
step. Ask for missing information only when it is absent from both the student's
message and the trusted hostel data.
""".strip()


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

    @staticmethod
    def _user_facing_text(text: str) -> str:
        """Normalize provider output into safe, readable plain text."""
        text = text.strip()
        answer_start = text.rfind("<answer>")
        if answer_start != -1:
            answer_start += len("<answer>")
            answer_end = text.find("</answer>", answer_start)
            text = text[
                answer_start:answer_end if answer_end != -1 else None
            ].strip()

        # Some reasoning-capable providers emit a hidden-thought block despite
        # being instructed not to. Never pass that block through to clients.
        while "<think>" in text and "</think>" in text:
            before, remainder = text.split("<think>", 1)
            _, after = remainder.split("</think>", 1)
            text = f"{before}{after}".strip()

        # Convert an accidental JSON response into its user-facing value. If
        # there is no conventional answer field, render values without JSON
        # punctuation rather than exposing a raw object to the student.
        candidate = re.sub(
            r"^```(?:json)?\s*|\s*```$",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            pass
        else:
            text = GemmaClient._plain_value(parsed)

        # Keep useful visual structure without exposing Markdown syntax. The
        # frontend already uses whitespace-pre-wrap, so line breaks and visible
        # Unicode bullets display correctly.
        text = re.sub(r"```(?:\w+)?", "", text)
        text = text.replace("```", "")
        text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
        text = re.sub(r"(?m)^\s*>\s?", "", text)
        text = re.sub(r"(?m)^\s*(?:-{3,}|\*{3,}|_{3,})\s*$", "", text)
        text = re.sub(
            r"!\[([^\]]*)\]\(([^)]+)\)",
            lambda match: (
                f"{match.group(1)}: {match.group(2)}"
                if match.group(1)
                else match.group(2)
            ),
            text,
        )
        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1: \2", text)
        text = re.sub(r"\[\^([^\]]+)\]", r"\1", text)
        text = re.sub(r"(?m)^\s*[-*+]\s+\[[ xX]\]\s+", "• ", text)
        text = re.sub(r"(\*\*|__)(.+?)\1", r"\2", text)
        text = re.sub(r"~~(.+?)~~", r"\1", text)
        text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"\1", text)
        text = re.sub(r"(?<!_)_([^_\n]+)_(?!_)", r"\1", text)
        text = re.sub(r"`([^`\n]+)`", r"\1", text)
        text = re.sub(r"(?m)^\s*[-*+]\s+", "• ", text)
        text = re.sub(r"(?m)^\s*\|?[\s:|-]+\|?\s*$", "", text)
        text = re.sub(r"(?m)^\s*\|(.+)\|\s*$", lambda match: " · ".join(
            cell.strip() for cell in match.group(1).split("|") if cell.strip()
        ), text)
        text = re.sub(r"</?[A-Za-z][^>]*>", "", text)
        text = re.sub(r"\\([\\`*{}\[\]()#+\-.!_>~|])", r"\1", text)
        text = re.sub(r"\${1,2}([^$\n]+)\${1,2}", r"\1", text)
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def _plain_value(value: Any, label: str | None = None) -> str:
        if isinstance(value, dict):
            preferred = ("answer", "reply", "message", "text", "content")
            for key in preferred:
                if key in value and isinstance(value[key], str):
                    return value[key]
            lines = [
                GemmaClient._plain_value(item, str(key))
                for key, item in value.items()
                if item is not None
            ]
            return "\n".join(line for line in lines if line)
        if isinstance(value, list):
            return "\n".join(
                f"• {GemmaClient._plain_value(item)}" for item in value
            )
        rendered = str(value)
        if isinstance(value, bool):
            rendered = "Yes" if value else "No"
        if label:
            readable_label = re.sub(r"[_-]+", " ", label).strip().capitalize()
            return f"{readable_label}: {rendered}"
        return rendered

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
                text = self._user_facing_text(text)
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
