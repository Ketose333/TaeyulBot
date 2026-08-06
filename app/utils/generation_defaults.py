import os

# Gemini 이미지/TTS 생성 기본값. 값 자체는 openclaw 한태율 페르소나 워크스페이스의
# utility/common/generation_defaults.py 원본과 동일하게 유지한다.
DEFAULT_IMAGE_MODEL = "nano-banana-pro-preview"
DEFAULT_IMAGE_FALLBACK_MODEL = "gemini-2.5-flash-image"
DEFAULT_IMAGE_ASPECT_RATIO = "1:1"

DEFAULT_TTS_MODEL = "gemini-2.5-flash-preview-tts"
DEFAULT_TTS_VOICE = "Fenrir"

_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AVATAR_DIR = os.path.join(_APP_DIR, "assets", "avatars")
DEFAULT_TAEYUL_REF_IMAGE = os.path.join(AVATAR_DIR, "taeyul.png")
IMAGE_RULES_PATH = os.path.join(_APP_DIR, "persona", "image_rules.md")
