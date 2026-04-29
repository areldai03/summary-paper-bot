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
    論文リストを Slack に投稿（親メッセージに一覧、スレッドに要約）
    親メッセージには各要約へのリンク [summary] を付与する
    """
    if not papers:
        return

    try:
        response = client.chat_postMessage(
            channel=SLACK_CHANNEL_ID,
            text=f"*本日の新着論文 ({len(papers)}件)*\nスレッドに要約を投稿しています...",
            unfurl_links=False,
            unfurl_media=False
        )
        thread_ts = response["ts"]
        print("Slack 親メッセージ（仮）投稿成功")

        reply_links = []
        for i, paper in enumerate(papers):
            if "slack_summary" in paper:
                blocks = [
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": f"{paper['slack_summary']}"}
                    }
                ]
                
                if i < len(papers) - 1:
                    blocks.append({"type": "divider"})
                
                reply_res = client.chat_postMessage(
                    channel=SLACK_CHANNEL_ID,
                    blocks=blocks,
                    thread_ts=thread_ts,
                    unfurl_links=False,
                    unfurl_media=False
                )
                
                permalink_res = client.chat_getPermalink(
                    channel=SLACK_CHANNEL_ID, 
                    message_ts=reply_res["ts"]
                )
                reply_links.append(permalink_res["permalink"])
            else:
                reply_links.append(None)
                
        print("Slack スレッドへの要約投稿成功")

        main_text = f"*本日の新着論文 ({len(papers)}件)*\n\n"
        for i, paper in enumerate(papers):
            title = paper.get('title', f'論文 {i+1}')
            summary_link = f" <{reply_links[i]}|[summary]>" if reply_links[i] else ""
            main_text += f"•  {title}{summary_link}\n"
            
        client.chat_update(
            channel=SLACK_CHANNEL_ID,
            ts=thread_ts,
            text=main_text
        )
        print("Slack 親メッセージの更新（リンク追加）成功")

    except SlackApiError as e:
        print(f"Slack 投稿エラー: {e.response['error']}")