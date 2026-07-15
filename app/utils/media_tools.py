import logging
from dataclasses import dataclass, field

from langchain_core.tools import tool

from app.utils.filename_policy import slugify_name
from app.utils.generation_defaults import DEFAULT_TAEYUL_REF_IMAGE
from app.utils.gemini_image import ext_from_mime as image_ext_from_mime
from app.utils.gemini_image import generate_image_with_fallback
from app.utils.gemini_tts import generate_tts

log = logging.getLogger(__name__)

_avatar_bytes_cache = None
_ERROR_SUMMARY_LIMIT = 200


def _short_error(e: Exception) -> str:
    """Gemini API 에러는 쿼터 초과 시 수백 줄짜리 JSON 페이로드를 포함할 수 있다.
    이걸 그대로 ToolMessage에 담으면 모델이 그 내용을 답변에 반영해 디스코드
    2000자 제한을 넘길 수 있어, 앞부분만 잘라 짧은 요약으로 돌려준다."""
    text = str(e).replace("\n", " ")
    if len(text) > _ERROR_SUMMARY_LIMIT:
        text = text[:_ERROR_SUMMARY_LIMIT] + "..."
    return text


def load_avatar_bytes() -> bytes:
    global _avatar_bytes_cache
    if _avatar_bytes_cache is None:
        with open(DEFAULT_TAEYUL_REF_IMAGE, "rb") as f:
            _avatar_bytes_cache = f.read()
    return _avatar_bytes_cache


@dataclass
class MediaSink:
    """generate_response() 호출 1건에 대응하는 요청 스코프 수집함.
    tool 결과 바이트를 ToolMessage(텍스트)로 모델에 되돌리지 않고 여기 모아뒀다가
    최종적으로 discord.File 첨부로 변환한다."""

    items: list = field(default_factory=list)
    image_used: bool = False
    tts_used: bool = False


def make_media_tools(sink: MediaSink, gemini_api_key: str, include_image: bool = True) -> list:
    """요청마다 새로 호출해서 만드는 tool 팩토리. sink를 클로저로 캡처하므로
    동시에 처리되는 다른 세션의 결과와 섞이지 않는다.

    include_image=False면 이미지 생성 도구를 LLM에 아예 노출하지 않는다
    (예: Gemini 무료 티어 이미지 모델 쿼터가 0으로 막혀있을 때 임시 비활성화용)."""

    @tool
    async def generate_taeyul_image(prompt: str, profile: str = "taeyul", allow_2d: bool = False) -> str:
        """한태율(taeyul, 기본값)/케토스(ketose)/권진혁(kwonjinhyuk) 중 하나의 정체성을 유지한
        이미지를 생성해 디스코드 메시지에 첨부한다. prompt에는 원하는 장면/포즈/의상 등을 적는다."""
        if sink.image_used:
            return "이미지는 이 응답에서 이미 1장 생성했습니다."
        if not gemini_api_key:
            return "이미지 생성을 사용할 수 없습니다(GEMINI_API_KEY 미설정)."
        sink.image_used = True
        try:
            img_bytes, mime, _ = await generate_image_with_fallback(
                gemini_api_key,
                prompt,
                ref_image_bytes=load_avatar_bytes(),
                profile=profile,
                allow_2d=allow_2d,
            )
        except Exception as e:
            log.warning("이미지 생성 실패: %s", e)
            return f"이미지 생성 실패: {_short_error(e)}"
        filename = f"{slugify_name(prompt)[:60]}.{image_ext_from_mime(mime)}"
        sink.items.append((img_bytes, filename))
        # 파일명(언더바 여러 개 포함 가능)을 텍스트로 노출하면 모델이 그대로 답변에 옮길 때
        # 디스코드 마크다운이 "_..._" 구간을 기울임체로 오해석하는 문제가 있어, 파일명은
        # 절대 텍스트로 돌려주지 않는다. 첨부 자체가 실제 파일명을 그대로 보여준다.
        return "이미지 생성 완료 (자동으로 첨부됩니다)"

    @tool
    async def generate_taeyul_voice(text: str) -> str:
        """text를 한태율 목소리 음성 파일로 만들어 디스코드 메시지에 첨부한다."""
        if sink.tts_used:
            return "음성 파일은 이 응답에서 이미 1개 생성했습니다."
        if not gemini_api_key:
            return "음성 생성을 사용할 수 없습니다(GEMINI_API_KEY 미설정)."
        sink.tts_used = True
        try:
            audio_bytes, ext = await generate_tts(gemini_api_key, text)
        except Exception as e:
            log.warning("음성 생성 실패: %s", e)
            return f"음성 생성 실패: {_short_error(e)}"
        filename = f"{slugify_name(text)[:60]}.{ext}"
        sink.items.append((audio_bytes, filename))
        return "음성 파일 생성 완료 (자동으로 첨부됩니다)"

    tools = [generate_taeyul_voice]
    if include_image:
        tools.insert(0, generate_taeyul_image)
    return tools
