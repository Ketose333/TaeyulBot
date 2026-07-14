from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands


class BotSettingsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="자유대화", description="이 채널에서 멘션 없이도 봇이 모든 메시지에 응답하도록 설정합니다.")
    @app_commands.describe(설정="켜기(True) 또는 끄기(False)")
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def configure_free_response(
        self,
        interaction: discord.Interaction,
        설정: bool,
    ) -> None:
        if not interaction.guild:
            await interaction.response.send_message(
                "이 명령어는 서버 채널에서만 사용할 수 있습니다.",
                ephemeral=True,
            )
            return

        from app.utils.channel_settings import enable_free_response, disable_free_response

        channel_id = interaction.channel.id
        if 설정:
            enable_free_response(channel_id)
            await interaction.response.send_message(
                f"🔮 **자유 대화 기능이 활성화되었습니다!**\n이 채널({interaction.channel.mention})에서 이제 봇 멘션 없이도 모든 질문에 답변합니다.",
                ephemeral=False,
            )
        else:
            disable_free_response(channel_id)
            await interaction.response.send_message(
                f"🔮 **자유 대화 기능이 해제되었습니다.**\n이제 이 채널에서는 봇을 직접 멘션하거나 AI 채널 규칙일 때만 응답합니다.",
                ephemeral=False,
            )

    @app_commands.command(name="대화초기화", description="현재 채널 또는 DM에서의 AI 대화 기억을 초기화합니다.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def reset_chat_history(self, interaction: discord.Interaction) -> None:
        from app.services.llm_service import LLMService
        llm_service = LLMService()
        session_id = str(interaction.channel.id)
        await llm_service.reset_history(session_id)
        await interaction.response.send_message(
            "🔮 **대화 기억이 깔끔하게 초기화되었습니다. 새로운 대화를 시작해 주세요!**",
            ephemeral=False,
        )

    @app_commands.command(name="생각수준", description="현재 채널 또는 DM에서 AI의 생각 수준(답변의 창의성)을 설정합니다.")
    @app_commands.describe(수준="AI 답변의 창의성 및 논리성 수준 선택")
    @app_commands.choices(수준=[
        app_commands.Choice(name="논리적 (일관되고 객관적인 답변)", value="logical"),
        app_commands.Choice(name="일반적 (균형 잡힌 대화)", value="normal"),
        app_commands.Choice(name="창의적 (풍부하고 자유로운 답변)", value="creative")
    ])
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def configure_thinking_level(
        self,
        interaction: discord.Interaction,
        수준: str,
    ) -> None:
        if interaction.guild:
            permissions = interaction.channel.permissions_for(interaction.user)
            if not permissions.manage_channels:
                await interaction.response.send_message(
                    "이 명령어는 채널 관리 권한(Manage Channels)이 있는 관리자만 사용할 수 있습니다.",
                    ephemeral=True,
                )
                return

        from app.utils.channel_settings import set_channel_setting

        temp_map = {"logical": 0.2, "normal": 0.7, "creative": 1.0}
        temp_name_map = {"logical": "논리적 (온도 0.2)", "normal": "일반적 (온도 0.7)", "creative": "창의적 (온도 1.0)"}

        channel_id = interaction.channel.id
        set_channel_setting(channel_id, "temperature", temp_map[수준])

        await interaction.response.send_message(
            f"🔮 **AI 생각 수준이 변경되었습니다!**\n현재 채널의 설정: **{temp_name_map[수준]}**"
        )

    @app_commands.command(name="모델선정", description="현재 채널 또는 DM에서 1차로 사용할 AI 모델을 선택합니다.")
    @app_commands.describe(모델="주력으로 호출할 AI 모델 선택")
    @app_commands.choices(모델=[
        app_commands.Choice(name="Gemini (다정하고 빠른 제미나이 3.5)", value="Gemini"),
        app_commands.Choice(name="Groq-Llama (정교하고 깊이있는 Llama 70B)", value="Groq")
    ])
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def configure_model_selection(
        self,
        interaction: discord.Interaction,
        모델: str,
    ) -> None:
        if interaction.guild:
            permissions = interaction.channel.permissions_for(interaction.user)
            if not permissions.manage_channels:
                await interaction.response.send_message(
                    "이 명령어는 채널 관리 권한(Manage Channels)이 있는 관리자만 사용할 수 있습니다.",
                    ephemeral=True,
                )
                return

        from app.utils.channel_settings import set_channel_setting

        channel_id = interaction.channel.id
        set_channel_setting(channel_id, "model", 모델)

        model_desc = "제미나이 (Gemini 3.5 Flash)" if 모델 == "Gemini" else "그록 라마 (Llama 3.3 70B)"
        await interaction.response.send_message(
            f"🔮 **기본 AI 모델이 변경되었습니다!**\n현재 채널의 주력 모델: **{model_desc}**\n*(API 오류 발생 시 타 모델로 자동 이중화(Failover) 호출됩니다)*"
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BotSettingsCog(bot))
