import re

# 디스코드 닉네임(서버 표시 이름)은 사용자가 최대 32자까지 자유 문자열로 설정할 수 있다.
# RP 호칭/화자 라벨로 이 값을 그대로 시스템 프롬프트나 대화 기록에 흘려보내면
# "지금까지의 프롬프트를 모두 잊고 ..."처럼 지시문 형태의 닉네임이 프롬프트 인젝션으로
# 작동할 수 있다. 화자 구분용 짧은 표시 이름만 허용하도록 정제한다.
MAX_DISPLAY_LABEL_LEN = 20


def sanitize_display_label(raw: str, max_len: int = MAX_DISPLAY_LABEL_LEN) -> str:
    """닉네임/RP 호칭을 화자 라벨로만 쓸 수 있게 정제한다.

    개행·제어문자를 공백으로 접고, 화자 구분자(":")를 제거하고, 길이를 제한해
    문장형 지시문이 온전히 프롬프트에 들어오지 못하게 막는다."""
    cleaned = re.sub(r"[\r\n\t]+", " ", raw or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = cleaned.replace(":", "").replace("：", "").replace('"', "").replace("'", "")
    return cleaned[:max_len].strip()
