"""
Slack Bot (Socket Mode)
メンションされたメッセージから URL を検知し、
Web ページの内容を取得・要約してスレッドに返信する
（モデルはメンション時に初めてロードする）
"""

import os
import logging
from datetime import datetime
from pathlib import Path
import threading
import queue

import dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from fetch_url import extract_urls, fetch_webpage_text
from summarize import unload_model

# --- ログ設定（コンソール + ファイル） ---
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

log_file = LOG_DIR / f"bot-{datetime.now().strftime('%Y-%m-%d')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding="utf-8"),
    ],
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

# メインスレッドで実行するためのキュー
_task_queue = queue.Queue()


@app.event("app_mention")
def handle_mention(event, say, client):
    """
    Bot へのメンションを検知し、URL が含まれていれば
    即座に「要約を開始します」と返信してからモデルをロード→要約→結果返信
    """
    logger.info(f"app_mention イベント受信: {event}")

    text = event.get("text", "")
    channel = event.get("channel", "")
    ts = event.get("ts", "")
    user = event.get("user", "unknown")

    logger.info(f"メンション from user={user}, channel={channel}, text={text}")

    # URL を抽出
    urls = extract_urls(text)
    if not urls:
        logger.info("URL なし — ヘルプメッセージを返信")
        say(text="URL が見つかりませんでした。要約したい URL を含めてメンションしてください。", thread_ts=ts)
        return

    logger.info(f"URL 検出: {urls}")

    # メンション時にモデルをロード（遅延ロード）
    from summarize_url import summarize_webpage

    for url in urls:
        # タスクをキューに入れてメインスレッドで処理
        _task_queue.put({
            "url": url,
            "channel": channel,
            "ts": ts,
            "client": client,
        })

def _safe_reaction(client, channel, timestamp, reaction_name):
    """Slack API のエラーを無視して安全にリアクションを追加する"""
    try:
        client.reactions_add(
            name=reaction_name,
            channel=channel,
            timestamp=timestamp
        )
    except Exception as e:
        # リアクションの失敗はボットの本質的な動作を妨げないため、ログ出力のみにする
        import logging
        logging.warning(f"Failed to add reaction {reaction_name}: {e}")

def _process_task(task):
    """メインスレッドで要約処理を実行"""
    url = task["url"]
    channel = task["channel"]
    ts = task["ts"]
    client = task["client"]

    try:
        logger.info(f"Fetching URL: {url}")
        # _safe_reaction(client, channel, ts, "hourglass_flowing_sand")
        client.chat_postMessage(
            channel=channel, thread_ts=ts,
            text=f"📖 要約を開始します。モデルをロード中..."
        )

        from fetch_url import fetch_webpage_text
        page_data = fetch_webpage_text(url)

        if page_data.get("error"):
            client.chat_postMessage(
                channel=channel, thread_ts=ts,
                text=f"❌ ページ取得に失敗: {page_data['error']}"
            )
            return

        from summarize_url import summarize_webpage
        summary = summarize_webpage(page_data)

        client.chat_postMessage(channel=channel, thread_ts=ts, text=summary)
        # _safe_reaction(client, channel, ts, "white_check_mark")

        from summarize import unload_model
        unload_model()
        logger.info("要約完了・モデル解放")

    except Exception as e:
        logger.error(f"Error processing URL: {url}", exc_info=True)
        try:
            client.chat_postMessage(
                channel=channel, thread_ts=ts,
                text=f"❌ 要約に失敗しました: {e}"
            )
        except Exception:
            logger.error("エラー通知の送信にも失敗", exc_info=True)


@app.event("message")
def handle_message(event, say):
    """メンション以外のメッセージは無視（イベント登録のみ必要）"""
    pass


def _remove_reaction(client, channel: str, timestamp: str, name: str):
    """リアクションを安全に削除する（存在しなくてもエラーにしない）"""
    try:
        client.reactions_remove(channel=channel, timestamp=timestamp, name=name)
    except Exception:
        pass


def start_bot():
    """Slack Bot を Socket Mode で起動（メインスレッドでタスク処理）"""
    logger.info("🚀 Slack Bot を起動します (Socket Mode)")
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)

    # Socket Mode をバックグラウンドスレッドで起動
    handler.connect()

    # メインスレッドでタスクキューを処理
    logger.info("メインスレッドでタスク待機中...")
    while True:
        try:
            task = _task_queue.get(timeout=1)
            _process_task(task)
        except queue.Empty:
            continue
        except KeyboardInterrupt:
            logger.info("Bot を停止します")
            handler.close()
            break


if __name__ == "__main__":
    start_bot()
