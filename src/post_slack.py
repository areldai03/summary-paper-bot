import os
import dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

dotenv.load_dotenv()
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_CHANNEL_ID = os.environ.get("SLACK_CHANNEL_ID")

if not SLACK_BOT_TOKEN or not SLACK_CHANNEL_ID:
    raise ValueError("Slack Bot Token または Channel ID が設定されていません。")

client = WebClient(token=SLACK_BOT_TOKEN)

def post_papers_slack(papers):
    """
    論文リストを Slack に投稿（親メッセージに一覧、スレッドに summary）
    親メッセージには各 summary へのリンクを付与する
    """
    if not papers:
        return

    try:
        # 1. 親メッセージ（仮）の投稿
        response = client.chat_postMessage(
            channel=SLACK_CHANNEL_ID,
            text=f"本日の新着論文 ({len(papers)}件) を取得中...",
            unfurl_links=False,
            unfurl_media=False
        )
        thread_ts = response["ts"]
        print("Slack 親メッセージ（仮）投稿成功")

        reply_links = []
        
        # 2. スレッドへの summary 投稿
        for i, paper in enumerate(papers):
            if "slack_summary" in paper:
                title = paper.get('title', f'論文 {i+1}')
                url = paper.get('url', '')
                
                # タイトル部分
                title_text = f"*<{url}|{title}>*" if url else f"*{title}*"
                
                blocks = [
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": title_text}
                    }
                ]
                
                # 著者情報（絵文字なし）
                authors = paper.get('authors')
                if authors:
                    blocks.append({
                        "type": "context",
                        "elements": [
                            {"type": "mrkdwn", "text": f"*Authors:* {authors}"}
                        ]
                    })
                
                # summary 本文
                blocks.append({
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"{paper['slack_summary']}"}
                })

                # 論文ごとに divider を追加
                blocks.append({
                    "type": "divider"
                })
                
                # Slackに送信（フォールバックテキストも変更）
                reply_res = client.chat_postMessage(
                    channel=SLACK_CHANNEL_ID,
                    text=f"summary: {title}", 
                    blocks=blocks,
                    thread_ts=thread_ts,
                    unfurl_links=False,
                    unfurl_media=False
                )
                
                # リンクを取得して保存
                permalink_res = client.chat_getPermalink(
                    channel=SLACK_CHANNEL_ID, 
                    message_ts=reply_res["ts"]
                )
                reply_links.append(permalink_res["permalink"])
            else:
                reply_links.append(None)
                
        print("Slack スレッドへの summary 投稿成功")

        # 3. 親メッセージの更新（綺麗なリストUI）
        list_text = ""
        for i, paper in enumerate(papers):
            title = paper.get('title', f'論文 {i+1}')
            summary_link = f" <{reply_links[i]}|[summary]> " if reply_links[i] else ""
            list_text += f"• {title}{summary_link}\n"

        main_blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"本日の新着論文 ({len(papers)}件)",
                    "emoji": False # 余計な絵文字変換を防ぐ
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": list_text}
            }
        ]
            
        client.chat_update(
            channel=SLACK_CHANNEL_ID,
            ts=thread_ts,
            text=f"本日の新着論文 ({len(papers)}件)", 
            blocks=main_blocks
        )
        print("Slack 親メッセージの更新（リンク追加）成功")

    except SlackApiError as e:
        print(f"Slack 投稿エラー: {e.response['error']}")