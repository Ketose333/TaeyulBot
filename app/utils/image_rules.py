import re

from app.utils.generation_defaults import DEFAULT_IMAGE_MODEL, IMAGE_RULES_PATH


def parse_rules_sections(rules_path: str = IMAGE_RULES_PATH) -> dict:
    """image_rules.md를 `## 섹션명` / `- 항목` 구조로 파싱한다."""
    try:
        with open(rules_path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return {}

    sections: dict = {}
    current = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("## "):
            current = line[3:].strip()
            sections[current] = []
            continue
        if current and line.startswith("- "):
            sections[current].append(line[2:].strip())
    return sections


def is_outfit_only_request(prompt: str) -> bool:
    p = (prompt or "").lower()
    keys = ["의상", "옷", "outfit", "costume", "wardrobe", "착장"]
    return any(k in p for k in keys)


def rules_to_text(lines: list) -> str:
    return "\n".join(f"- {x}" for x in lines if x)


def parse_kv_section(sections: dict, name: str) -> dict:
    out: dict = {}
    for line in sections.get(name, []):
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        out[k.strip().lower()] = v.strip()
    return out


def normalize_request_prompt(prompt: str, rules_path: str = IMAGE_RULES_PATH) -> str:
    p = (prompt or "").strip()
    if not p:
        return "기본값 유지"

    sections = parse_rules_sections(rules_path)
    noise_terms = [x.strip().lower() for x in sections.get("REQUEST_NOISE_DROP", []) if x.strip()]
    noise_contains = [x.strip().lower() for x in sections.get("REQUEST_NOISE_CONTAINS", []) if x.strip()]

    rewrite_pairs = []
    for line in sections.get("REQUEST_CANONICAL_REWRITE", []):
        if "=>" not in line:
            continue
        src, dst = line.split("=>", 1)
        src = re.sub(r"\s+", " ", src.strip().lower())
        dst = dst.strip()
        if src and dst:
            rewrite_pairs.append((src, dst))

    tokens = [t.strip() for t in re.split(r"[\n,]", p) if t.strip()]

    normalized = []
    seen_norm = set()
    for t in tokens:
        norm = re.sub(r"\s+", " ", t.lower()).strip()
        if norm in noise_terms:
            continue

        replaced = t
        if noise_contains:
            for k in noise_contains:
                if not k:
                    continue
                replaced = re.sub(re.escape(k), " ", replaced, flags=re.IGNORECASE)
            replaced = re.sub(r"\s+", " ", replaced).strip(" ,.-:;")
            if not replaced:
                continue
            norm = re.sub(r"\s+", " ", replaced.lower()).strip()
        for src, dst in rewrite_pairs:
            if norm == src:
                replaced = dst
                norm = re.sub(r"\s+", " ", dst.lower()).strip()
                break

        if norm in seen_norm:
            continue
        seen_norm.add(norm)
        normalized.append(replaced)

    joined = ", ".join(normalized).strip(" ,.-:;")
    return joined or "기본값 유지"


def avatar_lock_prompt(
    prompt: str,
    *,
    allow_2d: bool = False,
    model: str = "",
    profile: str = "taeyul",
    rules_path: str = IMAGE_RULES_PATH,
) -> str:
    sections = parse_rules_sections(rules_path)

    selected = []
    selected += sections.get("COMMON_IDENTITY_LOCK", [])
    selected += sections.get("REF_IMAGE_POLICY", [])

    if allow_2d:
        selected += sections.get("TWO_D_STYLE_GUARD", [])
    else:
        selected += sections.get("REAL_STYLE_GUARD", [])

    selected += sections.get("FRAMING_AND_POSE_BASELINE", [])
    selected += sections.get("BACKGROUND_QUALITY_BASELINE", [])

    if DEFAULT_IMAGE_MODEL in (model or ""):
        selected += sections.get("NANO_BANANA_PRO_GUARD", [])
        selected += sections.get("HARD_CASE_AVOIDANCE", [])

    if is_outfit_only_request(prompt):
        selected += sections.get("OUTFIT_ONLY_LOCK", [])

    profile_key = (profile or "").strip().lower()
    profile_boost = []
    if profile_key == "ketose":
        profile_boost = sections.get("REQUEST_PROFILE_BOOST_KETOSE", [])
    elif profile_key == "kwonjinhyuk":
        profile_boost = sections.get("REQUEST_PROFILE_BOOST_KWONJINHYUK", [])

    req = normalize_request_prompt(prompt, rules_path)

    limits = parse_kv_section(sections, "REQUEST_PROFILE_BOOST_LIMIT")
    try:
        default_limit = max(0, int(limits.get("default", "3")))
    except ValueError:
        default_limit = 3
    try:
        rich_limit = max(0, int(limits.get("rich_prompt", "2")))
    except ValueError:
        rich_limit = 2

    req_tokens = [t.strip() for t in re.split(r"[\n,]", req) if t.strip()]
    boost_limit = rich_limit if len(req_tokens) >= 3 else default_limit

    boost_items = []
    if profile_boost and boost_limit > 0:
        seen = {re.sub(r"\s+", " ", t.lower()).strip() for t in req_tokens}
        for b in profile_boost:
            norm = re.sub(r"\s+", " ", b.lower()).strip()
            if norm in seen:
                continue
            boost_items.append(b)
            seen.add(norm)
            if len(boost_items) >= boost_limit:
                break

    if boost_items:
        req = req + "\n" + "\n".join(f"+ {x}" for x in boost_items)

    rules_text = rules_to_text(selected)
    mode = "2D 모드" if allow_2d else "실사 모드"
    return (
        f"[규칙 소스: image_rules.md]\n{rules_text}\n\n"
        f"현재 생성 모드: {mode}\n"
        f"요청(프로필 반영):\n{req}"
    )
