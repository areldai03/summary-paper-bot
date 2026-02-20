"""
Slack Bot (Socket Mode)
チャンネル内のメッセージから URL を検知し、
Web ページの内容を取得・要約してスレッドに返信する
"""

import os
import logging

import dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from fetch_url import extract_urls, fetch_webpage_text
from summarize_url import summarize_webpage

# --- ログ設定 ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# --- 環境変数の読み込み ---
dotenv.load_dotenv()

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")

if not SLACK_BOT_TOKEN:
    raise ValueError(
        "SLACK_BOT_TOKEN が設定されていません。"
        ".env ファイルに SLACK_BOT_TOKEN=xoxb-... を追加してください。"
    )
if not SLACK_APP_TOKEN:
    raise ValueError(
        "SLACK_APP_TOKEN が設定されていません。"
        ".env ファイルに SLACK_APP_TOKEN=xapp-... を追加してください。"
    )

# --- Slack App の初期化 ---
app = App(token=SLACK_BOT_TOKEN)


@app.event("message")
def handle_message(event, say, client):
    """
    チャンネル内のメッセージを監視し、URL が含まれていれば
    Web ページの内容を取得・要約してスレッドに返信する
    """
    # Bot 自身のメッセージは無視
    if event.get("bot_id") or event.get("subtype"):
        return

    text = event.get("text", "")
    channel = event.get("channel", "")
    ts = event.get("ts", "")  # スレッド返信用のタイムスタンプ

    # URL を抽出
    urls = extract_urls(text)
    if not urls:
        return

    logger.info(f"URL detected in channel={channel}: {urls}")

    for url in urls:
        try:
            # 処理中であることをリアクションで通知
            client.reactions_add(
                channel=channel,
                timestamp=ts,
                name="hourglass_flowing_sand",  # ⏳
            )

            # 1. Web ページの内容を取得
            logger.info(f"Fetching URL: {url}")
            page_data = fetch_webpage_text(url)

            if page_data.get("error"):
                say(
                    text=f"⚠️ URL の取得に失敗しました: {url}\n`{page_data['error']}`",
                    thread_ts=ts,
                )
                _remove_reaction(client, channel, ts, "hourglass_flowing_sand")
                continue

            if not page_data["text"].strip():
                say(
                    text=f"⚠️ ページの本文を取得できませんでした: {url}",
                    thread_ts=ts,
                )
                _remove_reaction(client, channel, ts, "hourglass_flowing_sand")
                continue

            # 2. LLM で要約
            logger.info(f"Summarizing: {page_data['title']}")
            summary = summarize_webpage(page_data)

            # 3. スレッドに返信
            say(text=summary, thread_ts=ts)

            # リアクションを完了に差し替え
            _remove_reaction(client, channel, ts, "hourglass_flowing_sand")
            client.reactions_add(
                channel=channel,
                timestamp=ts,
                name="white_check_mark",  # ✅
            )

            logger.info(f"Summary posted for: {url}")

        except Exception:
            logger.exception(f"Error processing URL: {url}")
            _remove_reaction(client, channel, ts, "hourglass_flowing_sand")
            say(
                text=f"⚠️ 要約処理中にエラーが発生しました: {url}",
                thread_ts=ts,
            )


def _remove_reaction(client, channel: str, timestamp: str, name: str):
    """リアクションを安全に削除する（存在しなくてもエラーにしない）"""
    try:
        client.reactions_remove(channel=channel, timestamp=timestamp, name=name)
    except Exception:
        pass


def start_bot():
    """Socket Mode で Bot を起動する"""
    logger.info("🚀 Slack Bot を起動します (Socket Mode)")
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()


if __name__ == "__main__":
    start_bot()
