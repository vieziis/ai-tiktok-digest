"""
Interactive Telegram bot for AI-generated TikTok digests.

Commands:
  /start | /help   — show this help
  /digest          — trending last 72h (same as daily)
  /today           — trending last 24h
  /fresh           — posted in the last 6h
  /week            — trending last 7 days
  /alltime         — top by raw views, no time limit
  /tag <name>      — fetch from a specific hashtag (e.g. /tag kling)

Pagination: each result set has a "5 more ➡️" button that cycles through
the full fetched list without re-hitting TikTok.
"""
import logging
import os
import random

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

from tiktok_utils import fetch_videos, build_message

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
MS_TOKEN = os.environ.get("TIKTOK_MS_TOKEN", "")
PAGE_SIZE = 5

HELP_TEXT = """
🤖 <b>AI TikTok Bot — Commands</b>

/digest — trending last 72h (daily pick)
/today — trending last 24h
/fresh — posted in the last 6h
/week — trending last 7 days
/alltime — all-time top by views
/tag &lt;name&gt; — specific hashtag (e.g. <code>/tag kling</code>)
/help — show this message

Tap <b>5 more ➡️</b> under any result to cycle through more videos.
""".strip()

MIN_VIEWS = {
    "fresh":   20_000,
    "today":   75_000,
    "digest":  150_000,
    "week":    300_000,
    "alltime": 1_000_000,
    "tag":     30_000,
}

# Per-user cache: { user_id: { videos, offset, title } }
_cache: dict[int, dict] = {}


def more_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("5 more ➡️", callback_data="more")]])


async def send_page(update: Update, user_id: int, is_callback: bool = False) -> None:
    cache = _cache.get(user_id)
    if not cache:
        text = "⚠️ Session expired — run a command again to start fresh."
        if is_callback:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(text)
        else:
            await update.message.reply_text(text)
        return

    videos = cache["videos"]
    offset = cache["offset"]
    title = cache["title"]

    page = videos[offset: offset + PAGE_SIZE]
    if not page:
        text = "✅ That's all the videos for this search. Run a command to start a new one."
        if is_callback:
            await update.callback_query.answer("No more videos!")
            await update.callback_query.message.reply_text(text)
        else:
            await update.message.reply_text(text)
        return

    cache["offset"] += PAGE_SIZE
    has_more = cache["offset"] < len(videos)

    page_num = offset // PAGE_SIZE + 1
    paged_title = f"{title}  (#{page_num})"
    msg = build_message(page, paged_title)

    reply_markup = more_button() if has_more else None

    if is_callback:
        await update.callback_query.answer()
        await update.callback_query.message.reply_html(msg, reply_markup=reply_markup, disable_web_page_preview=False)
    else:
        await update.message.reply_html(msg, reply_markup=reply_markup, disable_web_page_preview=False)


async def handle_more(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    await send_page(update, user_id, is_callback=True)


async def send_digest(
    update: Update,
    title: str,
    max_age_hours: float | None,
    sort_by_score: bool = True,
    hashtags: list[str] | None = None,
    min_views: int = 0,
) -> None:
    await update.message.reply_text("⏳ Fetching videos, this takes ~30s…")
    await update.effective_chat.send_action(ChatAction.TYPING)
    try:
        videos = await fetch_videos(
            MS_TOKEN,
            hashtags=hashtags,
            videos_per_tag=50,
            max_age_hours=max_age_hours,
            min_views=min_views,
        )
        if not videos:
            await update.message.reply_text(
                f"😕 No videos hit the popularity threshold ({min_views:,} views) in this timeframe.\n"
                "Try /digest or /week for a wider window."
            )
            return

        key = (lambda v: v["score"]) if sort_by_score else (lambda v: v["views"])
        sorted_videos = sorted(videos, key=key, reverse=True)

        # Shuffle the top 30 so each call returns a different selection,
        # while still only pulling from the genuinely popular pool.
        pool = sorted_videos[:30]
        random.shuffle(pool)
        remainder = sorted_videos[30:]  # keep tail in score order as fallback
        shuffled = pool + remainder

        user_id = update.effective_user.id
        _cache[user_id] = {"videos": shuffled, "offset": 0, "title": title}

        await send_page(update, user_id, is_callback=False)

    except Exception as exc:
        log.exception("fetch error")
        await update.message.reply_text(f"❌ Error: {exc}")


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_html(HELP_TEXT)


async def cmd_digest(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await send_digest(update, "Trending AI TikToks — Last 72h", max_age_hours=72, min_views=MIN_VIEWS["digest"])


async def cmd_today(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await send_digest(update, "Trending AI TikToks — Last 24h", max_age_hours=24, min_views=MIN_VIEWS["today"])


async def cmd_fresh(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await send_digest(update, "Fresh AI TikToks — Last 6h", max_age_hours=6, min_views=MIN_VIEWS["fresh"])


async def cmd_week(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await send_digest(update, "Trending AI TikToks — Last 7 Days", max_age_hours=168, min_views=MIN_VIEWS["week"])


async def cmd_alltime(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await send_digest(update, "All-Time Top AI TikToks", max_age_hours=None, sort_by_score=False, min_views=MIN_VIEWS["alltime"])


async def cmd_tag(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.args:
        await update.message.reply_text("Usage: /tag <hashtag>  e.g. /tag kling")
        return
    tag = ctx.args[0].lstrip("#").lower()
    await send_digest(update, f"Trending #{tag} TikToks", max_age_hours=72, hashtags=[tag], min_views=MIN_VIEWS["tag"])


def main() -> None:
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler(["start", "help"], cmd_start))
    app.add_handler(CommandHandler("digest", cmd_digest))
    app.add_handler(CommandHandler("today", cmd_today))
    app.add_handler(CommandHandler("fresh", cmd_fresh))
    app.add_handler(CommandHandler("week", cmd_week))
    app.add_handler(CommandHandler("alltime", cmd_alltime))
    app.add_handler(CommandHandler("tag", cmd_tag))
    app.add_handler(CallbackQueryHandler(handle_more, pattern="^more$"))

    log.info("Bot started — polling…")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
