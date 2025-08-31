import os
import requests
import dotenv

# .env または環境変数から取得
dotenv.load_dotenv()
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")

if not SLACK_WEBHOOK_URL:
    raise ValueError("Slack Webhook URL が設定されていません。")

def post_to_slack(text: str):
    """
    Slack にメッセージを投稿
    Args:
        text (str): 投稿テキスト
    """
    payload = {
        "text": text
    }
    response = requests.post(SLACK_WEBHOOK_URL, json=payload)
    if not response.ok:
        print(f"Slack 投稿エラー: {response.status_code} {response.text}")
    else:
        print("Slack 投稿成功")


def post_papers_slack(papers):
    """
    論文リストを Slack に投稿
    Args:
        papers (list[dict]): 各論文の slack_summary を含む辞書
    """
    messages = []
    for i, paper in enumerate(papers):
        if "slack_summary" in paper:
            messages.append(f'論文番号{i+1}\n{paper["slack_summary"]}\n---\n')
    
    final_message = "".join(messages)
    print("投稿内容:\n", final_message)
    post_to_slack(final_message)
    


    

