import asyncio
import logging
import os
import tempfile

from aiogram import Bot, Dispatcher, F
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile, Message

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("voice-bot")

TOKEN = os.environ["BOT_TOKEN"]
# Optional: self-hosted Bot API server URL (lets the bot handle files up to 2 GB)
LOCAL_API_URL = os.getenv("LOCAL_API_URL", "").strip()
# Optional: comma-separated Telegram user IDs allowed to use the bot (empty = everyone)
ALLOWED = {int(x) for x in os.getenv("ALLOWED_USERS", "").split(",") if x.strip()}
MAX_MB = int(os.getenv("MAX_FILE_MB", "20" if not LOCAL_API_URL else "200"))
BITRATE = os.getenv("OPUS_BITRATE", "32k")
CONCURRENCY = int(os.getenv("CONCURRENCY", "5"))
FFMPEG_TIMEOUT = int(os.getenv("FFMPEG_TIMEOUT", "300"))

session = None
if LOCAL_API_URL:
    session = AiohttpSession(api=TelegramAPIServer.from_base(LOCAL_API_URL, is_local=True))

bot = Bot(TOKEN, session=session)
dp = Dispatcher()
sem = asyncio.Semaphore(CONCURRENCY)


async def to_ogg(src: str, dst: str) -> bool:
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-i", src,
        "-vn", "-map_metadata", "-1",
        "-c:a", "libopus", "-b:a", BITRATE, "-application", "voip",
        "-ar", "48000", "-ac", "1", dst,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        return await asyncio.wait_for(proc.wait(), FFMPEG_TIMEOUT) == 0
    except asyncio.TimeoutError:
        proc.kill()
        return False


def allowed(m: Message) -> bool:
    return not ALLOWED or (m.from_user and m.from_user.id in ALLOWED)


async def deny(m: Message):
    uid = m.from_user.id if m.from_user else "unknown"
    await m.reply(
        "You are not allowed to use this bot.\n"
        "Please ask the admin to add you.\n\n"
        f"Your user ID: {uid}"
    )


@dp.message(CommandStart())
async def start(m: Message):
    if not allowed(m):
        await deny(m)
        return
    await m.answer("Send me any audio or video file and I will return it as a voice message.")


@dp.message(F.audio | F.voice | F.video | F.video_note | F.document)
async def handle(m: Message):
    if not allowed(m):
        await deny(m)
        return
    media = m.audio or m.voice or m.video or m.video_note or m.document
    if media.file_size and media.file_size > MAX_MB * 1024 * 1024:
        await m.reply(f"File is larger than {MAX_MB} MB.")
        return

    async with sem:
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "input")
            dst = os.path.join(tmp, "output.ogg")
            try:
                await bot.download(media, destination=src)
            except Exception:
                log.exception("download failed")
                await m.reply("Could not download this file.")
                return

            if not await to_ogg(src, dst):
                await m.reply("This file is not a valid audio/video or conversion failed.")
                return

            await m.reply_voice(FSInputFile(dst))


async def main():
    me = await bot.get_me()
    log.info("Started as @%s", me.username)
    await dp.start_polling(bot, allowed_updates=["message"])


if __name__ == "__main__":
    asyncio.run(main())
