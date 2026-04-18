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
"""
import asyncio
import logging
import os

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from tiktok_utils import fetch_videos, build_message, DEFAULT_HASHTAGS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
MS_TOKEN = os.environ.get("TIKTOK_MS_TOKEN", "")
TOP_N = 5

HELP_TEXT = """
🤖 <b>AI TikTok Bot — Commands</b>

/digest — trending last 72h (daily pick)
/today — trending last 24h
/fresh — posted in the last 6h
/week — trending last 7 days
/alltime — all-time top by views
/tag &lt;name&gt; — specific hashtag (e.g. <code>/tag kling</code>)
/help — show this message
""".strip()


async def send_digest(update: Update, title: str, max_age_hours: float | None, sort_by_score: bool = True, hashtags: list[str] | None = None) -> None:
    await update.message.reply_text("⏳ Fetching videos, this takes ~30s…")
    await update.effective_chat.send_action(ChatAction.TYPING)
    try:
        videos = await fetch_videos(MS_TOKEN, hashtags=hashtags, videos_per_tag=30, max_age_hours=max_age_hours)
        if not videos:
            await update.message.reply_text("😕 No videos found for that timeframe. Try a wider window.")
            return
        key = (lambda v: v["score"]) if sort_by_score else (lambda v: v["views"])
        top = sorted(videos, key=key, reverse=True)[:TOP_N]
        msg = build_message(top, title)
        await update.message.reply_html(msg, disable_web_page_preview=False)
    except Exception as exc:
        log.exception("fetch error")
        await update.message.reply_text(f"❌ Error: {exc}")


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_html(HELP_TEXT)


async def cmd_digest(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await send_digest(update, "Trending AI TikToks — Last 72h", max_age_hours=72)


async def cmd_today(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await send_digest(update, "Trending AI TikToks — Last 24h", max_age_hours=24)


async def cmd_fresh(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await send_digest(update, "Fresh AI TikToks — Last 6h", max_age_hours=6)


async def cmd_week(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await send_digest(update, "Trending AI TikToks — Last 7 Days", max_age_hours=168)


async def cmd_alltime(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await send_digest(update, "All-Time Top AI TikToks", max_age_hours=None, sort_by_score=False)


async def cmd_tag(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.args:
        await update.message.reply_text("Usage: /tag <hashtag>  e.g. /tag kling")
        return
    tag = ctx.args[0].lstrip("#").lower()
    await send_digest(update, f"Trending #{tag} TikToks", max_age_hours=72, hashtags=[tag])


def main() -> None:
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler(["start", "help"], cmd_start))
    app.add_handler(CommandHandler("digest", cmd_digest))
    app.add_handler(CommandHandler("today", cmd_today))
    app.add_handler(CommandHandler("fresh", cmd_fresh))
    app.add_handler(CommandHandler("week", cmd_week))
    app.add_handler(CommandHandler("alltime", cmd_alltime))
    app.add_handler(CommandHandler("tag", cmd_tag))

    log.info("Bot started — polling…")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
