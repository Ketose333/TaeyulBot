import asyncio
import logging
import os

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from app.bot import create_bot


async def main() -> None:
    bot = create_bot()
    token = os.environ["DISCORD_TOKEN"]
    async with bot:
        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
