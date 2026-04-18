import time
from TikTokApi import TikTokApi

DEFAULT_HASHTAGS = [
    "aigenerated", "aiart", "aivideo", "kling", "hailuo",
    "runwayml", "soraai", "midjourney", "aianimation", "wouldyourather",
]


def tiktok_url(video_id: str, username: str) -> str:
    return f"https://www.tiktok.com/@{username}/video/{video_id}"


def fmt_number(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def hours_ago(ts: int) -> str:
    h = int((time.time() - ts) / 3600)
    if h < 1:
        return "< 1h ago"
    if h < 24:
        return f"{h}h ago"
    return f"{h // 24}d ago"


def trending_score(views: int, likes: int, created_at: int) -> float:
    age_hours = max((time.time() - created_at) / 3600, 1)
    like_ratio = likes / max(views, 1)
    return (views / age_hours) * (1 + like_ratio)


def html_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


async def fetch_videos(
    ms_token: str,
    hashtags: list[str] | None = None,
    videos_per_tag: int = 30,
    max_age_hours: float | None = 72,
) -> list[dict]:
    tags = hashtags or DEFAULT_HASHTAGS
    seen_ids: set[str] = set()
    results: list[dict] = []
    cutoff = (time.time() - max_age_hours * 3600) if max_age_hours else None

    async with TikTokApi() as api:
        await api.create_sessions(
            ms_tokens=[ms_token] if ms_token else [],
            num_sessions=1,
            sleep_after=3,
            headless=True,
        )
        for tag in tags:
            try:
                hashtag = api.hashtag(name=tag)
                async for video in hashtag.videos(count=videos_per_tag):
                    vid_id = video.id
                    if vid_id in seen_ids:
                        continue
                    seen_ids.add(vid_id)

                    d = video.as_dict
                    created_at = d.get("createTime", 0)
                    if cutoff and created_at and created_at < cutoff:
                        continue

                    stats = d.get("stats", {})
                    author = d.get("author", {})
                    views = stats.get("playCount", 0)
                    likes = stats.get("diggCount", 0)
                    results.append({
                        "id": vid_id,
                        "desc": (d.get("desc") or "").strip() or "(no description)",
                        "username": author.get("uniqueId", "unknown"),
                        "views": views,
                        "likes": likes,
                        "created_at": created_at,
                        "score": trending_score(views, likes, created_at or time.time()),
                        "tag": tag,
                    })
            except Exception as exc:
                print(f"[WARN] #{tag}: {exc}")

    return results


def build_message(videos: list[dict], title: str) -> str:
    lines = [f"🎬 <b>{html_escape(title)}</b>\n"]
    for i, v in enumerate(videos, 1):
        url = tiktok_url(v["id"], v["username"])
        desc = v["desc"][:120] + ("…" if len(v["desc"]) > 120 else "")
        age = hours_ago(v["created_at"]) if v.get("created_at") else ""
        lines.append(
            f"<b>{i}. {html_escape(desc)}</b>\n"
            f"👤 @{html_escape(v['username'])}  🕐 {age}\n"
            f"👁 {fmt_number(v['views'])}  ❤️ {fmt_number(v['likes'])}\n"
            f'🔗 <a href="{url}">Watch on TikTok</a>\n'
        )
    return "\n".join(lines)
