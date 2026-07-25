import re
from collections.abc import Callable


PATTERNS = {
    "upfront_payment_pressure": re.compile(
        r"\b(pay|transfer|send).{0,30}\b(now|before viewing|inspection|deposit|commitment fee)\b", re.I
    ),
    "urgency_pressure": re.compile(r"\b(urgent|immediately|today only|last chance|another person is paying)\b", re.I),
    "vague_address": re.compile(r"\b(address later|location later|cannot share (the )?address|undisclosed location)\b", re.I),
    "no_verifiable_identity": re.compile(r"\b(no id|no identification|don't need my id|cannot video call|no documents)\b", re.I),
}


def flag_scam_risk(
    listing_text: str,
    chat_transcript: str | None = None,
    reason_provider: Callable[[str, list[str]], list[str]] | None = None,
) -> dict:
    text = "\n".join(filter(None, [listing_text, chat_transcript]))
    flags = [name for name, pattern in PATTERNS.items() if pattern.search(text)]
    risk_level = "high" if len(flags) >= 3 else "medium" if flags else "low"
    default_reasons = {
        "upfront_payment_pressure": "Payment is requested before a safe viewing or verification step.",
        "urgency_pressure": "Urgency language may be intended to prevent careful verification.",
        "vague_address": "The property address is withheld or unclear.",
        "no_verifiable_identity": "The sender resists identity or document verification.",
    }
    reasons = [default_reasons[flag] for flag in flags]
    if reason_provider and flags:
        try:
            enhanced = reason_provider(text, flags)
            if enhanced:
                reasons = enhanced
        except Exception:
            pass
    return {"risk_level": risk_level, "flags": flags, "reasons": reasons, "error": None}
