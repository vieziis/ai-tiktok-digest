import asyncio
import os
import sys
from collections import defaultdict

import httpx
from TikTokApi import TikTokApi

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
MS_TOKEN = os.environ.get("TIKTOK_MS_TOKEN", "")

HASHTAGS = ["ai", "artificialintelligence", "chatgpt", "machinelearning"]
VIDEOS_PER_TAG = 20
TOP_N = 5


def tiktok_url(video_id: str, username: str) -> str:
    return f"https://www.tiktok.com/@{username}/video/{video_id}"


def fmt_number(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


async def fetch_videos() -> list[dict]:
    seen_ids: set[str] = set()
    results: list[dict] = []

    async with TikTokApi() as api:
        await api.create_sessions(
            ms_tokens=[MS_TOKEN] if MS_TOKEN else [],
            num_sessions=1,
            sleep_after=3,
            headless=True,
        )

        for tag in HASHTAGS:
            try:
                hashtag = api.hashtag(name=tag)
                async for video in hashtag.videos(count=VIDEOS_PER_TAG):
                    vid_id = video.id
                    if vid_id in seen_ids:
                        continue
                    seen_ids.add(vid_id)

                    stats = video.stats or {}
                    author = video.author
                    results.append(
                        {
                            "id": vid_id,
                            "desc": (video.desc or "").strip() or "(no description)",
                            "username": getattr(author, "username", "unknown"),
                            "views": stats.get("playCount", 0),
                            "likes": stats.get("diggCount", 0),
                            "tag": tag,
                        }
                    )
            except Exception as exc:
                print(f"[WARN] Failed to fetch #{tag}: {exc}", file=sys.stderr)

    return results


def build_message(videos: list[dict]) -> str:
    lines = ["🤖 *Daily AI TikTok Digest*\n"]
    for i, v in enumerate(videos, 1):
        url = tiktok_url(v["id"], v["username"])
        desc = v["desc"][:120] + ("…" if len(v["desc"]) > 120 else "")
        lines.append(
            f"*{i}\\. {desc}*\n"
            f"👤 @{v['username']}\n"
            f"👁 {fmt_number(v['views'])}  ❤️ {fmt_number(v['likes'])}\n"
            f"🔗 [Watch on TikTok]({url})\n"
        )
    return "\n".join(lines)


def send_telegram(text: str) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "MarkdownV2",
        "disable_web_page_preview": False,
    }
    resp = httpx.post(url, json=payload, timeout=30)
    resp.raise_for_status()
    print("Message sent successfully.")


async def main() -> None:
    print("Fetching TikTok videos…")
    videos = await fetch_videos()

    if not videos:
        print("No videos found — check MS_TOKEN and network access.", file=sys.stderr)
        sys.exit(1)

    top = sorted(videos, key=lambda v: v["views"], reverse=True)[:TOP_N]
    print(f"Top {len(top)} videos selected from {len(videos)} fetched.")

    message = build_message(top)
    send_telegram(message)


if __name__ == "__main__":
    asyncio.run(main())
