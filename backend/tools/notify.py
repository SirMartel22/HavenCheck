import os
from datetime import datetime, timezone
import resend


def notify_hostel_authority(hostel_id: str, issue_type: str, details: str) -> dict:
    timestamp = datetime.now(timezone.utc).isoformat()
    try:
        api_key = os.getenv("RESEND_API_KEY")
        recipient = os.getenv("AUTHORITY_EMAIL_TO")
        if not api_key or not recipient:
            raise ValueError("RESEND_API_KEY and AUTHORITY_EMAIL_TO must be configured")
        resend.api_key = api_key
        email = resend.Emails.send({
            "from": os.getenv("RESEND_FROM_EMAIL", "Housing Scout <onboarding@resend.dev>"),
            "to": [recipient],
            "subject": f"Hostel Authority Alert: {hostel_id}",
            "text": f"Hostel ID: {hostel_id}\nIssue type: {issue_type}\nDetails: {details}\nReported at: {timestamp}",
        })
        email_id = email.get("id") if isinstance(email, dict) else getattr(email, "id", None)
        return {"status": "sent", "timestamp": timestamp, "email_id": email_id, "error": None}
    except Exception as exc:
        return {"status": "failed", "timestamp": timestamp, "email_id": None, "error": f"Authority email failed: {exc}"}
