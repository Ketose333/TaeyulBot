from app.utils.image_rules import avatar_lock_prompt, is_outfit_only_request, normalize_request_prompt


def test_avatar_lock_prompt_taeyul_has_no_profile_boost():
    prompt = avatar_lock_prompt("웃는 얼굴", profile="taeyul")
    assert "동일 인물/캐릭터 정체성을 유지한다" in prompt
    assert "백금발" not in prompt
    assert "흑발" not in prompt


def test_avatar_lock_prompt_ketose_profile_boost_included():
    prompt = avatar_lock_prompt("웃는 얼굴", profile="ketose")
    assert "백금발" in prompt
    assert "청회색 컬러렌즈" in prompt


def test_avatar_lock_prompt_kwonjinhyuk_profile_boost_included():
    prompt = avatar_lock_prompt("웃는 얼굴", profile="kwonjinhyuk")
    assert "흑발" in prompt
    assert "날카로운 눈매" in prompt


def test_avatar_lock_prompt_2d_mode_uses_two_d_guard():
    prompt = avatar_lock_prompt("웃는 얼굴", allow_2d=True)
    assert "2D 모드" in prompt
    assert "2D/chibi 스타일을 허용한다" in prompt


def test_avatar_lock_prompt_real_mode_uses_real_style_guard():
    prompt = avatar_lock_prompt("웃는 얼굴", allow_2d=False)
    assert "실사 모드" in prompt
    assert "2D/카툰/셀셰이딩은 금지한다" in prompt


def test_avatar_lock_prompt_outfit_request_adds_outfit_lock():
    prompt = avatar_lock_prompt("의상만 바꿔줘")
    assert "의상 변경 요청에서는 얼굴/헤어/비율/정체성 변경을 절대 금지한다" in prompt


def test_is_outfit_only_request():
    assert is_outfit_only_request("옷만 바꿔줘")
    assert not is_outfit_only_request("웃는 얼굴로 그려줘")


def test_normalize_request_prompt_drops_noise_and_rewrites():
    result = normalize_request_prompt("자연스러운 실내광, 단순한 배경")
    assert "자연스러운 실내광" not in result
    assert "장식 적은 배경" in result


def test_normalize_request_prompt_empty_returns_default():
    assert normalize_request_prompt("") == "기본값 유지"
