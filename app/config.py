import os


def get_discord_token() -> str:
    return os.environ["DISCORD_TOKEN"]


GUILD_ID = os.getenv("GUILD_ID")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY", "")
OWNER_DISCORD_ID = os.getenv("OWNER_DISCORD_ID", "").strip()

# Gemini 무료 티어의 이미지 생성 모델(nano-banana-pro-preview 등) 쿼터가 0으로 막혀 있고
# 결제 계정을 연결하지 않기로 해서, 대안이 정해지기 전까지 이미지 생성을 임시로 끈다.
# 음성 생성(TTS)은 별도 모델이라 영향 없음. LLM 도구(llm_service.py)와 슬래시 커맨드
# (commands/media.py) 양쪽에서 참조하는 단일 플래그.
ENABLE_IMAGE_GENERATION = False

def get_rp_safety_style() -> str:
    return (os.getenv("RP_SAFETY_STYLE", "default") or "default").strip().lower()
