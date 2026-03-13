FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure logs appear immediately in Cloud Run
ENV PYTHONUNBUFFERED=1

# ---------------------------------------------------------------------------
# Cloud Run deployment notes
#
# Required environment variables:
#   DISCORD_BOT_TOKEN     - Discord bot token
#   BASE_API_URL          - FPL API base URL
#   GCS_BUCKET            - GCS bucket name for persistent state
#   NEWS_INTERVAL_MINUTES - (optional) news check interval, default 30
#
# This bot holds a persistent WebSocket connection to Discord.
# Always set --min-instances=1 and --max-instances=1:
#
#   gcloud run deploy fantasyesbot \
#     --image gcr.io/YOUR_PROJECT/fantasyesbot \
#     --min-instances=1 --max-instances=1 \
#     --set-env-vars DISCORD_BOT_TOKEN=...,BASE_API_URL=...,GCS_BUCKET=...
#
# To put the bot to sleep (off-season cost saving):
#   gcloud run services update fantasyesbot --min-instances=0 --max-instances=0
#
# To wake it back up:
#   gcloud run services update fantasyesbot --min-instances=1 --max-instances=1
# ---------------------------------------------------------------------------

CMD ["python", "bot.py"]
