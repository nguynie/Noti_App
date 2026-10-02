# 🔔 Facebook Page Telegram Notifier

A lightweight, browserless Python program that monitors Facebook pages specified in [`sources.yaml`](file:///home/nguynie/Noti_App/sources.yaml) and sends real-time notifications to your Telegram chat.

---

## ✨ Features

- **24/7 Without Keeping Your Laptop On**: Pre-configured with a **GitHub Actions** workflow that runs automatically in the cloud every 20 minutes for free.
- **No Browser Agent Required**: Uses lightweight HTTP requests instead of heavy headless browsers (Playwright/Puppeteer/Selenium), consuming < 30MB RAM.
- **Dual State Storage**: Tracks post IDs in [`seen_posts.json`](file:///home/nguynie/Noti_App/seen_posts.json) and local SQLite ([`seen_posts.db`](file:///home/nguynie/Noti_App/seen_posts.db)) so you never receive duplicate notifications.
- **First-Run Baseline**: Automatically records existing posts on the first scan so your Telegram is not flooded with historical posts.

---

## ☁️ 24/7 Free Cloud Setup (GitHub Actions)

You can run this 24/7 on GitHub's cloud servers without needing your laptop to stay awake.

### Step 1: Create a Private GitHub Repository
1. Go to [github.com/new](https://github.com/new).
2. Choose **Private** (so your sources and configuration stay private).
3. Push this project to your repository:
   ```bash
   git init
   git add .
   git commit -m "Initial commit for Facebook Telegram Notifier"
   git branch -M main
   git remote add origin https://github.com/<YOUR_USERNAME>/<YOUR_REPO_NAME>.git
   git push -u origin main
   ```

### Step 2: Add Secrets to GitHub
1. In your GitHub repository, navigate to:
   **Settings** > **Secrets and variables** > **Actions** > **New repository secret**
2. Add the following secrets:
   - `TELEGRAM_BOT_TOKEN`: Your token from [@BotFather](https://t.me/BotFather)
   - `TELEGRAM_CHAT_ID`: Your Telegram ID from [@userinfobot](https://t.me/userinfobot)
   - `FB_COOKIES`: *(Optional)* Your Facebook cookie string

### Step 3: Enable Workflow Permissions
1. In your GitHub repository, navigate to:
   **Settings** > **Actions** > **General** > **Workflow permissions**
2. Select **Read and write permissions** (this allows the bot to save `seen_posts.json` so it remembers which posts were already notified).
3. Click **Save**.

That's it! GitHub Actions will now automatically check your Facebook pages every 20 minutes and notify your Telegram chat 24/7. You can also trigger an immediate check anytime by clicking **Run workflow** in the **Actions** tab on GitHub.

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
