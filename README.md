# Daily AI TikTok Digest → Telegram

Fetches the top AI-related TikTok videos every morning and sends a digest to a Telegram chat.

## What it does

1. Pulls up to 20 videos each from `#ai`, `#artificialintelligence`, `#chatgpt`, and `#machinelearning`
2. Deduplicates and sorts by view count
3. Sends the top 5 to Telegram with description, creator, views, likes, and a direct link

Runs automatically at **08:00 UTC daily** via GitHub Actions, or manually via **workflow_dispatch**.

---

## Setup

### 1. Create a Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` and follow the prompts
3. Copy the **API token** it gives you (format: `123456789:ABCdef...`)

### 2. Get your Telegram Chat ID

**Personal chat:**
1. Message your bot once (so it knows about you)
2. Visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
3. Find `"chat":{"id": <number>}` — that number is your Chat ID

**Group chat:**
1. Add your bot to the group
2. Send any message in the group
3. Use the same `getUpdates` URL — Chat IDs for groups are negative numbers (e.g. `-100123456789`)

### 3. Get a TikTok `ms_token`

TikTokApi requires a valid TikTok session cookie to bypass bot detection.

1. Open [tiktok.com](https://www.tiktok.com) in your browser while logged in
2. Open DevTools → Application (Chrome) or Storage (Firefox) → Cookies
3. Find the cookie named **`msToken`** on `tiktok.com`
4. Copy its value — it's a long string (~120–150 chars)

> **Note:** `ms_token` expires. If the workflow starts returning no videos, refresh it here.

### 4. Add GitHub Secrets

Go to your repo → **Settings → Secrets and variables → Actions → New repository secret** and add:

| Secret name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Your bot token from BotFather |
| `TELEGRAM_CHAT_ID` | Your chat or group ID |
| `TIKTOK_MS_TOKEN` | The `msToken` cookie value |

### 5. Push and enable

Push this repo to GitHub. The workflow will run automatically each morning, or you can trigger it manually from the **Actions** tab → **Daily AI TikTok Digest** → **Run workflow**.

---

## Local testing

```bash
pip install -r requirements.txt
playwright install chromium

export TELEGRAM_BOT_TOKEN="your_token"
export TELEGRAM_CHAT_ID="your_chat_id"
export TIKTOK_MS_TOKEN="your_ms_token"

python fetch_digest.py
```

## Files

| File | Purpose |
|---|---|
| `fetch_digest.py` | Main script — fetches TikTok, formats, sends Telegram |
| `requirements.txt` | Python dependencies |
| `.github/workflows/daily_digest.yml` | GitHub Actions workflow |
