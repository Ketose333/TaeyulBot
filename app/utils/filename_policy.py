import re


def slugify_name(text: str, fallback: str = "file") -> str:
    """텍스트를 파일명으로 쓸 수 있는 slug로 변환한다. 한글은 유지한다."""
    t = (text or "").lower().strip()
    t = re.sub(r"[^a-z0-9가-힣]+", "_", t)
    t = re.sub(r"_+", "_", t).strip("_")
    return t or fallback
