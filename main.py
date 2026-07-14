import asyncio
import logging

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from app.bot import create_bot
from app.config import get_discord_token


async def main() -> None:
    bot = create_bot()
    token = get_discord_token()
    async with bot:
        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
