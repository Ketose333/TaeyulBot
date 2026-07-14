from app.utils.rp_prompt import build_rp_prompt_block


def test_early_turn_anchor_is_strong():
    block = build_rp_prompt_block("폐쇄된 연구소에서 눈을 뜬다", 1, "", "선배")
    assert "앵커 강도: 높음" in block
    assert "폐쇄된 연구소" in block
    assert "선배" in block


def test_late_turn_without_transition_is_medium_continuity():
    block = build_rp_prompt_block("폐쇄된 연구소", 10, "그냥 계속 대화 중", "선배")
    assert "앵커 강도: 중간(연속성 유지" in block


def test_transition_keyword_softens_anchor():
    block = build_rp_prompt_block("폐쇄된 연구소", 10, "이제 다음 장면으로 넘어가자", "선배")
    assert "전환 진행 중" in block
    assert "앵커 강도: 중간(현재 대화 흐름 우선" in block


def test_no_opening_falls_back_to_recent_text():
    block = build_rp_prompt_block("", 5, "최근 대화 내용입니다", "선배")
    assert "최근 대화 흐름 기준" in block


def test_no_opening_and_no_recent_text_is_unanchored():
    block = build_rp_prompt_block("", 0, "", "선배")
    assert "현재 장면 앵커: 미지정" in block
    assert "앵커 강도: 낮음" in block


def test_empty_alias_falls_back_to_default():
    block = build_rp_prompt_block("", 1, "", "")
    assert "사용자 호칭: 상대" in block


def test_immersive_safety_style_adds_rule(monkeypatch):
    monkeypatch.setenv("RP_SAFETY_STYLE", "immersive")
    block = build_rp_prompt_block("", 1, "", "선배")
    assert "현실 안전 가이드" in block


def test_default_safety_style_has_no_immersive_rule(monkeypatch):
    monkeypatch.delenv("RP_SAFETY_STYLE", raising=False)
    block = build_rp_prompt_block("", 1, "", "선배")
    assert "현실 안전 가이드" not in block
