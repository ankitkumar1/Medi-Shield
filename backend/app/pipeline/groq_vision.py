"""Optional Groq vision classifier. Used only when GROQ_API_KEY is set."""

import base64
import json
import urllib.error
import urllib.request
from io import BytesIO

from PIL import Image

from app.config import settings

DOC_TYPES = {
    "CLAIM_FORM",
    "ID_DOCUMENT",
    "DISCHARGE_SUMMARY",
    "PRESCRIPTION",
    "POLICY_AMENDMENT",
    "UNKNOWN",
}

ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"


def groq_enabled() -> bool:
    return bool(settings.groq_api_key.strip())


def classify_image(path: str) -> dict | None:
    """Return a classifier result, or None so the caller can use local OCR."""
    if not groq_enabled():
        return None
    if path.lower().endswith(".pdf"):
        return None

    image = Image.open(path).convert("RGB")
    image.thumbnail((1280, 1280))
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=70)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    prompt = (
        "Classify this insurance document as exactly one of "
        "CLAIM_FORM, ID_DOCUMENT, DISCHARGE_SUMMARY, PRESCRIPTION, "
        "POLICY_AMENDMENT, UNKNOWN. "
        'Reply with JSON: {"doc_type": "...", "confidence": 0.0, "reason": "..."}.'
    )
    payload = {
        "model": settings.groq_model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{encoded}"},
                    },
                ],
            }
        ],
    }
    request = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {settings.groq_api_key.strip()}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None

    try:
        content = body["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        return None

    doc_type = str(parsed.get("doc_type", "UNKNOWN")).upper().replace(" ", "_")
    if doc_type not in DOC_TYPES:
        doc_type = "UNKNOWN"
    try:
        confidence = float(parsed.get("confidence", 0.5))
    except (TypeError, ValueError):
        confidence = 0.5
    confidence = min(1.0, max(0.0, confidence))
    reason = str(parsed.get("reason") or "Classified by Groq vision.")
    tags = ["groq"] if confidence >= 0.6 else ["groq", "human_review"]
    return {
        "doc_type": doc_type,
        "confidence": round(confidence, 2),
        "routing_tags": tags,
        "reason": reason,
        "provider": "groq",
        "model": settings.groq_model,
    }
