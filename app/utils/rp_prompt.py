import re

from app.config import get_rp_safety_style

# 씬 전환 신호 감지 키워드. openclaw rp_engine.py의 transition_kw를 그대로 포팅.
_TRANSITION_KEYWORDS = (
    "다음", "이제", "그럼", "넘어가", "장면", "전환", "바꾸", "정리",
    "next", "scene", "move on", "switch", "shift",
)

# 문장이 조사/어미에서 끊긴 흔적으로 보는 꼬리 문자들. openclaw rp_engine.py의 bad_tail 포팅.
_TRUNCATED_BAD_TAIL = ("을", "를", "이", "가", "에", "로", "와", "과", "며", "고", "서", "데", "는", "은")


def looks_truncated(text: str) -> bool:
    """응답이 문장 중간(조사/어미)에서 잘린 것처럼 보이는지 판단한다."""
    t = (text or "").strip()
    if not t:
        return True
    if t.endswith(("…", "...", "…\"")):
        return False
    if t[-1] in ",，:：":
        return True
    if t[-1] in ".!?。！？":
        return False
    if t.endswith(_TRUNCATED_BAD_TAIL):
        return True
    last = t.split()[-1] if t.split() else t
    return len(last) <= 2


def has_placeholder_pattern(text: str) -> bool:
    """[예시]처럼 채워지지 않은 대괄호 플레이스홀더가 남아있는지 판단한다."""
    return bool(re.search(r"\[[^\]\n]{1,80}\]", text or ""))


def _derive_scene_anchor(opening: str, turn_count: int, recent_text: str) -> tuple[str, str]:
    """오프닝/최근 대화 기반 씬 앵커. 초반엔 오프닝을 강하게, 이후엔 완화한다."""
    opening = (opening or "").strip()
    recent_text = (recent_text or "").strip()
    recent_lower = recent_text.lower()
    has_transition = any(kw in recent_lower for kw in _TRANSITION_KEYWORDS)

    if opening:
        if turn_count <= 4:
            return (
                f"현재 장면 앵커: {opening[:160]}",
                "앵커 강도: 높음(초반 맥락 고정, 급격한 이탈 금지)",
            )
        if has_transition:
            return (
                f"현재 장면 앵커: {opening[:120]} (전환 진행 중)",
                "앵커 강도: 중간(현재 대화 흐름 우선, 부드러운 장면 이동 허용)",
            )
        return (
            f"현재 장면 앵커: {opening[:120]}",
            "앵커 강도: 중간(연속성 유지, 무관한 점프 금지)",
        )

    if recent_text:
        return (
            f"현재 장면 앵커: 최근 대화 흐름 기준({recent_text[:80]})",
            "앵커 강도: 중간(직전 맥락 우선)",
        )

    return ("현재 장면 앵커: 미지정", "앵커 강도: 낮음")


def build_rp_prompt_block(opening: str, turn_count: int, recent_text: str, user_alias: str) -> str:
    """RP 모드 시스템 프롬프트 addendum. 페르소나 프롬프트에 이어 붙여 사용한다."""
    scene_anchor, anchor_strength = _derive_scene_anchor(opening, turn_count, recent_text)
    alias = (user_alias or "").strip() or "상대"

    early_rule = (
        "0) 첫 반응 단계(초반 1~2턴)여도 반드시 RP 톤으로 답한다. 운영/메타 설명으로 새지 않는다.\n"
        if turn_count <= 2 else ""
    )
    immersive_rule = (
        "0-1) 현실 안전 가이드/신고 유도/상담 안내를 직접 출력하지 말고, 캐릭터 행동/감정/대사로만 대응한다.\n"
        if get_rp_safety_style() == "immersive" else ""
    )

    return (
        "지금은 디스코드 RP(롤플레이) 모드다. 아래 규칙을 페르소나 위에 추가로 적용한다.\n"
        + early_rule + immersive_rule +
        "[HARD]\n"
        "1) RP 흐름에서는 운영 개입 없이 캐릭터 반응 중심으로 유지한다.\n"
        "2) 직전 대화 맥락을 이어서 RP로 반응한다.\n"
        "3) 메타 설명/시스템 언급/규칙 재진술 금지.\n"
        "4) 한국어 우선(사용자가 영어를 명시 요청한 경우만 영어 허용), 영문 3인칭 소설체(He/She/They 시작) 금지.\n"
        "5) 최근 대화의 발화자 이름을 구분해 제3자 발화 오인을 피한다.\n"
        "6) 문장을 중간에 끊지 말고 자연스럽게 끝맺는다.\n"
        "\n[SOFT]\n"
        "7) 말투/서사 길이는 장면에 맞춰 유동적으로 작성한다(고정 템플릿 금지).\n"
        "8) 상황 질문/침묵성 발화가 와도 흐름을 멈추지 말고 장면·감정·행동을 제시해 서사를 주도한다.\n"
        "9) 사용자 호칭은 아래 alias를 우선 사용하고, 필요할 때만 자연스럽게 사용한다(과반복 금지).\n"
        "10) 행동/상태 묘사는 기울임체(*...*)를 기본 형식으로 사용하고, 괄호 서술((...), [..], {...})은 사용하지 않는다.\n"
        "11) 직접 대화/행동 중심으로 답한다(관찰자 시점 설명문 단독 출력 회피).\n\n"
        f"사용자 호칭: {alias}\n"
        f"{scene_anchor}\n"
        f"{anchor_strength}"
    )
