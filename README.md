# Voice Bot

Send any audio/video file to the bot and it replies with a Telegram voice message (OGG/OPUS via ffmpeg).

## Deploy on Sevalla
1. Push this folder to a GitHub repo.
2. Sevalla -> Applications -> Add application -> pick the repo, build type: Dockerfile.
3. Set the application type to a background worker (no port/domain needed, the bot uses long polling).
4. Environment variables: BOT_TOKEN (required). Optional: ALLOWED_USERS, LOCAL_API_URL, MAX_FILE_MB, OPUS_BITRATE, CONCURRENCY.
5. Run only ONE instance, otherwise Telegram returns a getUpdates conflict error.
