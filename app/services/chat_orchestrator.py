import logging

import discord

from app.utils.discord_reply import build_discord_files, truncate_for_discord
from app.utils.user_label import sanitize_display_label

log = logging.getLogger(__name__)


def evaluate_message_routing(bot, message: discord.Message, is_dm: bool) -> tuple:
    """(should_respond, is_mentioned)를 반환한다. DM은 무조건 통과."""
    if is_dm:
        return True, False

    is_mentioned = bot.user.mentioned_in(message)
    if is_mentioned:
        return True, is_mentioned

    is_allowed_channel = False
    if hasattr(message.channel, 'name') and message.channel.name:
        is_allowed_channel = message.channel.name.startswith("AI-") or message.channel.name == "llm-타임"
    if is_allowed_channel:
        return True, is_mentioned

    # 여기부터는 디스크 I/O가 필요한 조건이라, 멘션/채널명으로 이미 결정됐으면 건너뛴다.
    from app.utils.channel_settings import is_free_response_enabled
    if is_free_response_enabled(message.channel.id):
        return True, is_mentioned

    from app.utils import rp_store
    is_rp_channel = rp_store.is_active(str(message.channel.id))
    return is_rp_channel, is_mentioned


async def handle_message(bot, message: discord.Message, *, is_dm: bool, is_mentioned: bool) -> None:
    async with message.channel.typing():
        try:
            clean_prompt = message.clean_content
            clean_prompt = clean_prompt.replace(f"@{bot.user.display_name}", "").replace(f"@{bot.user.name}", "").strip()

            if not clean_prompt:
                await message.reply("안녕하세요! 질문을 입력해주시면 답변해 드릴게요. 🔮")
                return

            session_id = str(message.channel.id)

            # 멘션/DM처럼 봇에게 직접 말을 건 게 확실하면 RP 응답 여부 판정을 건너뛴다
            # (제3자 대화로 오판돼 무응답이 되는 걸 방지).
            is_direct_address = is_dm or is_mentioned

            ai_reply, attachments = await bot.llm_service.generate_response(
                session_id, clean_prompt, author_id=message.author.id,
                author_name=sanitize_display_label(message.author.display_name),
                is_direct_address=is_direct_address,
            )

            # RP 제3자 대화로 판정돼 응답이 생략된 경우 — 대화 기록엔 남았으니 아무것도 보내지 않는다.
            if ai_reply is None:
                return

            ai_reply = truncate_for_discord(ai_reply)
            files = build_discord_files(attachments) if attachments else []
            if files:
                await message.reply(content=ai_reply, files=files)
            else:
                await message.reply(ai_reply)
        except Exception as e:
            log.exception("LLM 대화 응답 처리 중 에러 발생")
            await message.reply(truncate_for_discord(f"❌ LLM 응답 중 오류가 발생했습니다: {str(e)}"))
