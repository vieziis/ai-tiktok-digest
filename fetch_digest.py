import asyncio
import os
import sys

import httpx
from tiktok_utils import fetch_videos, build_message

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
MS_TOKEN = os.environ.get("TIKTOK_MS_TOKEN", "")
TOP_N = 5


def send_telegram(text: str) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    resp = httpx.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }, timeout=30)
    resp.raise_for_status()
    print("Message sent successfully.")


async def main() -> None:
    print("Fetching TikTok videos…")
    videos = await fetch_videos(MS_TOKEN, max_age_hours=72, min_views=500_000)

    if not videos:
        print("No recent videos found.", file=sys.stderr)
        sys.exit(1)

    top = sorted(videos, key=lambda v: v["score"], reverse=True)[:TOP_N]
    print(f"Top {len(top)} selected from {len(videos)} recent videos.")
    send_telegram(build_message(top, "Trending AI-Generated TikToks"))


if __name__ == "__main__":
    asyncio.run(main())
