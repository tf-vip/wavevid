"""Soniox transcription with timestamps and caching."""
import hashlib
import json
import os
import time
import requests
from pathlib import Path

API_BASE = "https://api.soniox.com/v1"
MODEL = "stt-async-v3"
CACHE_DIR = Path.cwd() / ".transcribe_cache"


def get_api_key() -> str:
    """Get API key from environment or .env file in current directory."""
    key = os.environ.get("SONIOX_API_KEY")
    if key:
        return key

    # Try loading from .env in current working directory
    env_file = Path.cwd() / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("SONIOX_API_KEY="):
                return line.split("=", 1)[1].strip()

    raise RuntimeError("Missing SONIOX_API_KEY. Set env var or create .env file.")


def get_cache_key(audio_path: str) -> str:
    """Generate cache key from file content hash."""
    h = hashlib.md5()
    with open(audio_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def get_cached_transcript(audio_path: str) -> dict | None:
    """Load cached transcript if available."""
    CACHE_DIR.mkdir(exist_ok=True)
    cache_key = get_cache_key(audio_path)
    cache_file = CACHE_DIR / f"{cache_key}.json"

    if cache_file.exists():
        return json.loads(cache_file.read_text())
    return None


def save_to_cache(audio_path: str, transcript: dict):
    """Save transcript to cache."""
    CACHE_DIR.mkdir(exist_ok=True)
    cache_key = get_cache_key(audio_path)
    cache_file = CACHE_DIR / f"{cache_key}.json"
    cache_file.write_text(json.dumps(transcript, ensure_ascii=False))


def upload_audio(session: requests.Session, audio_path: str) -> str:
    """Upload audio file and return file_id."""
    headers = {"Authorization": session.headers["Authorization"]}
    with open(audio_path, "rb") as f:
        files = {"file": (Path(audio_path).name, f)}
        resp = requests.post(f"{API_BASE}/files", headers=headers, files=files)
    resp.raise_for_status()
    return resp.json()["id"]


def create_transcription(session: requests.Session, file_id: str = None, audio_url: str = None) -> str:
    """Create transcription job and return transcription_id."""
    config = {"model": MODEL}
    if file_id:
        config["file_id"] = file_id
    elif audio_url:
        config["audio_url"] = audio_url

    resp = session.post(f"{API_BASE}/transcriptions", json=config)
    resp.raise_for_status()
    return resp.json()["id"]


def wait_for_completion(session: requests.Session, transcription_id: str, timeout: int = 600) -> bool:
    """Poll until transcription is complete."""
    start = time.time()
    poll_interval = 2

    while time.time() - start < timeout:
        resp = session.get(f"{API_BASE}/transcriptions/{transcription_id}")
        resp.raise_for_status()
        status = resp.json()["status"]

        if status == "completed":
            return True
        if status == "error":
            raise RuntimeError(f"Transcription failed: {resp.json()}")

        time.sleep(poll_interval)
        poll_interval = min(poll_interval * 1.5, 10)

    raise TimeoutError("Transcription timed out")


def get_transcript(session: requests.Session, transcription_id: str) -> dict:
    """Get transcript with tokens and timestamps."""
    resp = session.get(f"{API_BASE}/transcriptions/{transcription_id}/transcript")
    resp.raise_for_status()
    return resp.json()


def delete_transcription(session: requests.Session, transcription_id: str):
    """Delete transcription job."""
    session.delete(f"{API_BASE}/transcriptions/{transcription_id}")


def delete_file(session: requests.Session, file_id: str):
    """Delete uploaded file."""
    session.delete(f"{API_BASE}/files/{file_id}")


def transcribe_audio(audio_path: str, progress_callback=None, use_cache: bool = True) -> list[dict]:
    """
    Transcribe audio file and return word-level timestamps.
    Uses caching to avoid re-transcribing the same file.

    Returns list of tokens: [{"text": "word", "start_ms": 100, "end_ms": 200}, ...]
    """
    # Check cache first
    if use_cache:
        cached = get_cached_transcript(audio_path)
        if cached:
            if progress_callback:
                progress_callback("Using cached transcription")
            return cached.get("tokens", [])

    api_key = get_api_key()

    session = requests.Session()
    session.headers["Authorization"] = f"Bearer {api_key}"
    session.headers["Content-Type"] = "application/json"

    if progress_callback:
        progress_callback("Uploading audio to Soniox...")

    file_id = upload_audio(session, audio_path)

    try:
        if progress_callback:
            progress_callback("Creating transcription job...")

        transcription_id = create_transcription(session, file_id=file_id)

        if progress_callback:
            progress_callback("Waiting for transcription...")

        wait_for_completion(session, transcription_id)

        if progress_callback:
            progress_callback("Fetching transcript...")

        result = get_transcript(session, transcription_id)

        # Save to cache
        if use_cache:
            save_to_cache(audio_path, result)

        # Clean up on server
        delete_transcription(session, transcription_id)

        return result.get("tokens", [])

    finally:
        delete_file(session, file_id)


def tokens_to_subtitles(tokens: list[dict], max_chars: int = 60, max_duration_ms: int = 5000, replacements: dict = None) -> list[dict]:
    """
    Convert tokens to subtitle segments.
    Handles Soniox token format where spaces indicate word boundaries.

    Args:
        replacements: dict of {"old": "new"} text replacements to apply

    Returns list of: [{"text": "phrase", "start_ms": 100, "end_ms": 500}, ...]
    """
    if not tokens:
        return []

    replacements = replacements or {}
    subtitles = []
    current_words = []
    current_start = None
    current_end = None

    for token in tokens:
        text = token.get("text", "")
        start = token.get("start_ms", 0)
        end = token.get("end_ms", 0)

        # Skip empty tokens
        if not text:
            continue

        # Start new segment if needed
        if current_start is None:
            current_start = start

        # Check if this is a new word (starts with space) or sub-word
        is_new_word = text.startswith(" ")
        clean_text = text.strip()

        if is_new_word and current_words:
            # Check if we should start a new segment
            current_text = "".join(current_words)
            duration = end - current_start

            if len(current_text) > max_chars or duration > max_duration_ms:
                # Save current segment
                if current_text.strip():
                    final_text = current_text.strip()
                    for old, new in replacements.items():
                        final_text = final_text.replace(old, new)
                    subtitles.append({
                        "text": final_text,
                        "start_ms": current_start,
                        "end_ms": current_end
                    })
                # Start new segment
                current_words = [clean_text]
                current_start = start
                current_end = end
            else:
                # Add space and word to current segment
                current_words.append(" " + clean_text)
                current_end = end
        else:
            # Append token (sub-word or first word)
            if is_new_word:
                current_words.append(clean_text)
            else:
                current_words.append(text)
            current_end = end

    # Don't forget the last segment
    if current_words:
        final_text = "".join(current_words).strip()
        for old, new in replacements.items():
            final_text = final_text.replace(old, new)
        if final_text:
            subtitles.append({
                "text": final_text,
                "start_ms": current_start,
                "end_ms": current_end
            })

    return subtitles
