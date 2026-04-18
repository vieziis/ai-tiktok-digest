import asyncio
import os
import sys
import time

import httpx
from TikTokApi import TikTokApi

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
MS_TOKEN = os.environ.get("TIKTOK_MS_TOKEN", "")

# Hashtags used by AI-generated viral content creators
HASHTAGS = [
    "aigenerated",
    "aiart",
    "aivideo",
    "kling",
    "hailuo",
    "runwayml",
    "soraai",
    "midjourney",
    "aianimation",
    "wouldyourather",
]
VIDEOS_PER_TAG = 30
TOP_N = 5
MAX_AGE_HOURS = 72  # only keep videos posted in the last 3 days


def tiktok_url(video_id: str, username: str) -> str:
    return f"https://www.tiktok.com/@{username}/video/{video_id}"


def fmt_number(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def trending_score(views: int, likes: int, created_at: int) -> float:
    """Views-per-hour since posted, boosted by like ratio."""
    age_hours = max((time.time() - created_at) / 3600, 1)
    like_ratio = likes / max(views, 1)
    return (views / age_hours) * (1 + like_ratio)


async def fetch_videos() -> list[dict]:
    seen_ids: set[str] = set()
    results: list[dict] = []
    cutoff = time.time() - MAX_AGE_HOURS * 3600

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

                    d = video.as_dict
                    created_at = d.get("createTime", 0)

                    # Skip videos older than MAX_AGE_HOURS
                    if created_at and created_at < cutoff:
                        continue

                    stats = d.get("stats", {})
                    author = d.get("author", {})
                    views = stats.get("playCount", 0)
                    likes = stats.get("diggCount", 0)

                    results.append(
                        {
                            "id": vid_id,
                            "desc": (d.get("desc") or "").strip() or "(no description)",
                            "username": author.get("uniqueId", "unknown"),
                            "views": views,
                            "likes": likes,
                            "created_at": created_at,
                            "score": trending_score(views, likes, created_at or time.time()),
                            "tag": tag,
                        }
                    )
            except Exception as exc:
                print(f"[WARN] Failed to fetch #{tag}: {exc}", file=sys.stderr)

    return results


def html_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def hours_ago(ts: int) -> str:
    h = int((time.time() - ts) / 3600)
    if h < 1:
        return "< 1h ago"
    if h < 24:
        return f"{h}h ago"
    return f"{h // 24}d ago"


def build_message(videos: list[dict]) -> str:
    lines = ["🎬 <b>Trending AI-Generated TikToks</b>\n"]
    for i, v in enumerate(videos, 1):
        url = tiktok_url(v["id"], v["username"])
        desc = v["desc"][:120] + ("…" if len(v["desc"]) > 120 else "")
        age = hours_ago(v["created_at"]) if v["created_at"] else ""
        lines.append(
            f"<b>{i}. {html_escape(desc)}</b>\n"
            f"👤 @{html_escape(v['username'])}  🕐 {age}\n"
            f"👁 {fmt_number(v['views'])}  ❤️ {fmt_number(v['likes'])}\n"
            f'🔗 <a href="{url}">Watch on TikTok</a>\n'
        )
    return "\n".join(lines)


def send_telegram(text: str) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    resp = httpx.post(url, json=payload, timeout=30)
    resp.raise_for_status()
    print("Message sent successfully.")


async def main() -> None:
    print("Fetching TikTok videos…")
    videos = await fetch_videos()

    if not videos:
        print("No recent videos found — the ms_token may have expired or no videos posted in the last 72h.", file=sys.stderr)
        sys.exit(1)

    top = sorted(videos, key=lambda v: v["score"], reverse=True)[:TOP_N]
    print(f"Top {len(top)} trending videos selected from {len(videos)} recent videos.")

    message = build_message(top)
    send_telegram(message)


if __name__ == "__main__":
    asyncio.run(main())
