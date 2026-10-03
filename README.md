# 🔔 Facebook Page Telegram Notifier

A lightweight, browserless Python program that monitors Facebook pages specified in [`sources.yaml`](file:///home/nguynie/Noti_App/sources.yaml) and sends real-time notifications to your Telegram chat.

---

## ✨ Features

- **24/7 Dual-Trigger Cloud Architecture**: Pre-configured with **GitHub Actions** and external zero-delay webhook dispatch ([`cron-job.org`](docs/cloud_setup.md)) ensuring scans run every 30 minutes without delays.
- **Session Health & Admin Alerts**: Detects expired Facebook cookies or security checkpoints and notifies you via Telegram.
- **Workflow Keepalive**: Prevents GitHub from auto-disabling scheduled cron workflows after 60 days of repo inactivity.
- **No Browser Agent Required**: Uses lightweight HTTP requests instead of heavy headless browsers (Playwright/Puppeteer/Selenium), consuming < 30MB RAM.
- **Dual State Storage**: Tracks post IDs in [`seen_posts.json`](file:///home/nguynie/Noti_App/seen_posts.json) and local SQLite ([`seen_posts.db`](file:///home/nguynie/Noti_App/seen_posts.db)) so you never receive duplicate notifications.
- **First-Run Baseline**: Automatically records existing posts on the first scan so your Telegram is not flooded with historical posts.

---

## ☁️ 24/7 Free Cloud Setup (Max 30m–1h Latency)

For the detailed step-by-step setup guide with screenshots and zero-delay webhooks, see:
👉 **[Detailed Cloud Setup Guide (docs/cloud_setup.md)](docs/cloud_setup.md)**

### Quick Summary:
1. **GitHub Secrets**: Add `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, and `FB_COOKIES` in **Settings > Secrets and variables > Actions**.
2. **Workflow Permissions**: Enable **Read and write permissions** in **Settings > Actions > General > Workflow permissions**.
3. **Zero-Delay Trigger**: Create a free job on [cron-job.org](https://cron-job.org) targeting `https://api.github.com/repos/<USER>/Noti_App/dispatches` with `event_type: check-pages-webhook` every 30 minutes.

---

## 💻 Local Testing & Usage Commands

If you want to test or run locally on your laptop:

### 1. Configure `.env`
Edit [`.env`](file:///home/nguynie/Noti_App/.env):
```env
TELEGRAM_BOT_TOKEN="your_bot_token"
TELEGRAM_CHAT_ID="your_chat_id"
FB_COOKIES="c_user=...; xs=...; datr=...;"
CHECK_INTERVAL_SECONDS=300
REQUEST_DELAY_SECONDS=3
AUTO_BASELINE_FIRST_RUN=true
```

### 2. Verify Connections
- **Test Telegram bot connection**:
  ```bash
  python3 main.py --test-telegram
  ```
- **Test Facebook scraper on a page**:
  ```bash
  python3 main.py --test-scraper
  ```

### 3. Local Run Commands
- **Run a single scan cycle**:
  ```bash
  python3 main.py --once
  ```
- **Run as a continuous local daemon**:
  ```bash
  python3 main.py --daemon
  ```
- **View statistics**:
  ```bash
  python3 main.py --stats
  ```
