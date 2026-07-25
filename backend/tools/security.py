import os
from datetime import datetime, timezone
import resend


def alert_community_security(hostel_id: str, reason: str, evidence: str = "") -> dict:
    timestamp = datetime.now(timezone.utc).isoformat()
    try:
        api_key = os.getenv("RESEND_API_KEY")
        recipient = os.getenv("SECURITY_EMAIL_TO")
        if not api_key or not recipient:
            raise ValueError("RESEND_API_KEY and SECURITY_EMAIL_TO must be configured")
        resend.api_key = api_key
        email = resend.Emails.send({
            "from": os.getenv("RESEND_FROM_EMAIL", "Housing Scout <onboarding@resend.dev>"),
            "to": [recipient],
            "subject": f"Community Security Alert: {hostel_id}",
            "text": f"Hostel ID: {hostel_id}\nReason: {reason}\nEvidence: {evidence or 'Not supplied'}\nReported at: {timestamp}",
        })
        email_id = email.get("id") if isinstance(email, dict) else getattr(email, "id", None)
        return {"status": "sent", "timestamp": timestamp, "email_id": email_id, "error": None}
    except Exception as exc:
        return {"status": "failed", "timestamp": timestamp, "email_id": None, "error": f"Security email failed: {exc}"}
