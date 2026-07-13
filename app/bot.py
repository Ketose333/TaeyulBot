import os
import logging

import discord
from discord.ext import commands

log = logging.getLogger(__name__)


class TaeyulBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        # /리더보드에서 서버 멤버를 식별하기 위해 필요 (privileged — Developer Portal에서 토글)
        intents.members = True
        # Gatekeeper 및 메시지 수신 연동을 위한 메시지 콘텐츠 권한 활성화
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self) -> None:
        await self.load_extension("app.commands.horoscope")

        # 재시작 후에도 버튼·드랍다운이 살아있도록 persistent view 등록
        from app.commands.horoscope import CompatibilityInviteView, FortuneView, StatsView, RankingView
        self.add_view(FortuneView.for_persistence())
        self.add_view(StatsView())
        self.add_view(RankingView())
        self.add_view(CompatibilityInviteView())

        # 글로벌 동기화 — User-Installable App으로 모든 서버·DM에서 사용 가능
        await self.tree.sync()
        log.info("슬래시 커맨드 글로벌 동기화 완료 (전파까지 최대 1시간 소요)")

        # 개발 중 즉시 반영이 필요하면 GUILD_ID 설정
        guild_id = os.getenv("GUILD_ID")
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log.info("개발용 길드 즉시 동기화 완료 (GUILD_ID=%s)", guild_id)

    async def on_ready(self) -> None:
        await self.change_presence(activity=discord.Game(name="한태율 | /운세순위"))
        log.info("봇 준비 완료: %s (ID: %s)", self.user, self.user.id)
        from app.utils.user_store import set_zodiac, get_zodiac
        if not get_zodiac(self.user.id):
            set_zodiac(self.user.id, "쌍둥이자리")

    async def on_message(self, message: discord.Message) -> None:
        # [필터 규칙 1] 봇 본인이 작성했거나 시스템/타사 봇 계정의 메시지는 즉시 무시
        if message.author.bot:
            return

        # [필터 규칙 2] 기존 프리픽스 명령어 체계(!도움말 등)를 사용 중이라면 개입 차단
        if message.content.startswith('!'):
            return

        # [필터 규칙 3] 디스코드 자체 슬래시 커맨드(/운세 등) 입력은 시스템이 처리하므로 무시
        if message.content.startswith('/'):
            return

        # [필터 규칙 4] DM 채널인지 체크 (DM 채널은 무조건 통과)
        is_dm = isinstance(message.channel, discord.DMChannel)

        if not is_dm:
            # 일반 채널일 경우 조건부 개입
            # 조건 A: 봇 계정이 명확하게 태그(@한태율) 되었는가?
            is_mentioned = self.user.mentioned_in(message)
            
            # 조건 B: 특정 전용 채널 혹은 AI 전용 스레드 이름 규칙(예: "AI-대화")에 부합하는가?
            is_allowed_channel = False
            if hasattr(message.channel, 'name') and message.channel.name:
                is_allowed_channel = message.channel.name.startswith("AI-") or message.channel.name == "llm-타임"

            # 둘 다 부합하지 않으면 무시
            if not (is_mentioned or is_allowed_channel):
                return

        # ------------------ [ 조건 통과: LLM 연동 작동 ] ------------------
        async with message.channel.typing():
            try:
                # 프롬프트에서 봇 멘션 부분 제거 (@한태율)
                clean_prompt = message.clean_content
                clean_prompt = clean_prompt.replace(f"@{self.user.display_name}", "").replace(f"@{self.user.name}", "").strip()

                # 빈 메시지 방지
                if not clean_prompt:
                    await message.reply("안녕하세요! 질문을 입력해주시면 답변해 드릴게요. 🔮")
                    return

                # 세션 ID 설정
                session_id = str(message.channel.id)

                # LLM 서비스 로딩 및 호출
                from app.services.llm_service import LLMService
                if not hasattr(self, 'llm_service'):
                    self.llm_service = LLMService()
                
                ai_reply = await self.llm_service.generate_response(session_id, clean_prompt)
                
                # 답장 전송
                await message.reply(ai_reply)
            except Exception as e:
                log.exception("LLM 대화 응답 처리 중 에러 발생")
                await message.reply(f"❌ LLM 응답 중 오류가 발생했습니다: {str(e)}")


def create_bot() -> TaeyulBot:
    return TaeyulBot()
