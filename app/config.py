import os


def get_discord_token() -> str:
    return os.environ["DISCORD_TOKEN"]


GUILD_ID = os.getenv("GUILD_ID")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY", "")
OWNER_DISCORD_ID = os.getenv("OWNER_DISCORD_ID", "").strip()

def get_rp_safety_style() -> str:
    return (os.getenv("RP_SAFETY_STYLE", "default") or "default").strip().lower()
