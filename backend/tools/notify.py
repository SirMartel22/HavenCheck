import os
from datetime import datetime, timezone
import httpx


def notify_hostel_authority(hostel_id: str, issue_type: str, details: str) -> dict:
    timestamp = datetime.now(timezone.utc).isoformat()
    try:
        email_url = os.getenv("EMAIL_URL")
        recipient = os.getenv("AUTHORITY_EMAIL_TO")
        if not email_url or not recipient:
            raise ValueError("EMAIL_URL and AUTHORITY_EMAIL_TO must be configured")
        
        # Ensure the URL has a scheme, defaulting to https
        url = email_url if email_url.startswith(("http://", "https://")) else f"https://{email_url}"
        
        subject = f"Hostel Authority Alert: {hostel_id}"
        text = f"Hostel ID: {hostel_id}\nIssue type: {issue_type}\nDetails: {details}\nReported at: {timestamp}"
        html = f"<strong>Hostel ID:</strong> {hostel_id}<br><strong>Issue type:</strong> {issue_type}<br><strong>Details:</strong> {details}<br><strong>Reported at:</strong> {timestamp}"
        
        response = httpx.post(url, json={
            "to": recipient,
            "subject": subject,
            "text": text,
            "html": html
        }, timeout=15)
        response.raise_for_status()
        
        email_id = f"sent_{os.urandom(4).hex()}"
        return {"status": "sent", "timestamp": timestamp, "email_id": email_id, "error": None}
    except Exception as exc:
        return {"status": "failed", "timestamp": timestamp, "email_id": None, "error": f"Authority email failed: {exc}"}
