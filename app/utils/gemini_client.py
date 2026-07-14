import base64
import json
import urllib.error
import urllib.request


def _blocking_post(url: str, body: dict, *, error_prefix: str) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        payload = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{error_prefix} ({e.code}): {payload}") from e


def extract_inline_data(payload: dict, *, default_mime: str, not_found_message: str) -> tuple:
    candidates = payload.get("candidates", [])
    for c in candidates:
        parts = c.get("content", {}).get("parts", [])
        for p in parts:
            inline = p.get("inlineData") or p.get("inline_data")
            if inline and inline.get("data"):
                mime = (inline.get("mimeType") or inline.get("mime_type") or default_mime).lower()
                return base64.b64decode(inline["data"]), mime
    raise RuntimeError(not_found_message)
