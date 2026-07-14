import logging
from io import BytesIO

import discord

log = logging.getLogger(__name__)

DISCORD_MAX_MESSAGE_LEN = 2000


def truncate_for_discord(text: str, limit: int = DISCORD_MAX_MESSAGE_LEN) -> str:
    """디스코드 메시지 길이 제한(2000자)을 넘기면 400 Bad Request로 전송 자체가 실패하므로
    응답 원인과 무관하게 항상 안전하게 잘라서 보낸다."""
    if len(text) <= limit:
        return text
    suffix = "\n…(생략)"
    return text[: limit - len(suffix)] + suffix


def build_discord_files(attachments) -> list:
    files = []
    for data, name in attachments:
        try:
            files.append(discord.File(BytesIO(data), filename=name))
        except Exception:
            log.exception("첨부 파일 변환 실패: name=%s", name)
    return files
