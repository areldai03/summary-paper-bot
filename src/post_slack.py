import os
import requests
import dotenv

# .env または環境変数から取得
dotenv.load_dotenv()
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")

if not SLACK_WEBHOOK_URL:
    raise ValueError("Slack Webhook URL が設定されていません。")


def post_papers_slack(papers):
    """
    論文リストを Slack に投稿
    Args:
        papers (list[dict]): 各論文の slack_summary を含む辞書
    """
    blocks = []
    for i, paper in enumerate(papers):
        if "slack_summary" in paper:
            blocks.append({
                "type": "section",
                # "text": {"type": "mrkdwn", "text": f"*論文番号{i+1}*\n{paper['slack_summary']}"}
                "text": {"type": "mrkdwn", "text": f"{paper['slack_summary']}"}
            })
            blocks.append({"type": "divider"})  # 水平線

    payload = {"blocks": blocks}
    response = requests.post(SLACK_WEBHOOK_URL, json=payload)

    print("投稿内容 (block 形式):")
    for i in range(len(blocks)):
        print(blocks[i])
    if not response.ok:
        print(f"Slack 投稿エラー: {response.status_code} {response.text}")
    else:
        print("Slack 投稿成功")