import os

import httpx


class VoiceError(RuntimeError):
    pass


def _required_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    raise VoiceError(f"{names[0]} is not configured")


def transcribe_audio(
    content: bytes,
    filename: str,
    content_type: str,
) -> str:
    api_key = _required_env("GROQ_API_KEY")
    url = os.getenv(
        "GROQ_TRANSCRIPTION_URL",
        "https://api.groq.com/openai/v1/audio/transcriptions",
    )
    try:
        result = httpx.post(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            data={
                "model": os.getenv(
                    "GROQ_WHISPER_MODEL", "whisper-large-v3-turbo"
                ),
                "response_format": "json",
            },
            files={"file": (filename, content, content_type)},
            timeout=60,
        )
        result.raise_for_status()
        text = result.json().get("text", "").strip()
        if not text:
            raise VoiceError("Groq returned an empty transcription")
        return text
    except VoiceError:
        raise
    except Exception as exc:
        raise VoiceError(f"Groq transcription failed: {exc}") from exc


def call_easyvoice_tts(text: str) -> bytes:
    api_key = _required_env("EASYVOICE_API_KEY", "EASY_VOICE_API_KEY")
    url = _required_env("EASYVOICE_API_URL", "EASY_VOICE_API_URL")
    try:
        result = httpx.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "audio/mpeg",
            },
            json={
                "model": os.getenv("EASYVOICE_MODEL", "kokoro-82m"),
                "input": text,
                "voice": os.getenv("EASYVOICE_VOICE", "af_aoede"),
                "response_format": "mp3",
            },
            timeout=60,
        )
        result.raise_for_status()
        return result.content
    except Exception as exc:
        raise VoiceError(f"EasyVoice speech generation failed: {exc}") from exc


def call_elevenlabs_tts(text: str) -> bytes:
    api_key = _required_env("ELEVENLABS_API_KEY", "ELEVEN_LABS_API_KEY")
    voice_id = _required_env("ELEVENLABS_VOICE_ID", "ELEVEN_LABS_VOICE_ID")
    base_url = os.getenv(
        "ELEVENLABS_API_URL", "https://api.elevenlabs.io/v1/text-to-speech"
    ).rstrip("/")
    try:
        result = httpx.post(
            f"{base_url}/{voice_id}",
            params={"output_format": "mp3_44100_128"},
            headers={
                "xi-api-key": api_key,
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
            },
            json={
                "text": text,
                "model_id": os.getenv(
                    "ELEVENLABS_MODEL", "eleven_multilingual_v2"
                ),
            },
            timeout=60,
        )
        result.raise_for_status()
        return result.content
    except Exception as exc:
        raise VoiceError(f"ElevenLabs speech generation failed: {exc}") from exc


def speak(text: str) -> bytes:
    provider = os.getenv("TTS_PROVIDER", "easyvoice").strip().lower()
    if provider == "elevenlabs":
        return call_elevenlabs_tts(text)
    if provider == "easyvoice":
        return call_easyvoice_tts(text)
    raise VoiceError("TTS_PROVIDER must be 'easyvoice' or 'elevenlabs'")
