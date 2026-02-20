"""
URLからWebページの本文テキストを取得するモジュール
"""

import re
import requests
from bs4 import BeautifulSoup
import trafilatura

# User-Agent を設定してブロックを回避
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# テキストの最大文字数（LLM のコンテキスト制限に合わせてトランケート）
MAX_TEXT_LENGTH = 6000


def extract_urls(text: str) -> list[str]:
    """
    テキストからURLを抽出する
    Slack は URL を <URL> や <URL|label> の形式で送ってくるので、両方に対応
    """
    # Slack 形式: <https://example.com> or <https://example.com|label>
    slack_urls = re.findall(r'<(https?://[^|>]+)(?:\|[^>]*)?>',  text)
    if slack_urls:
        return slack_urls

    # 通常の URL パターン（フォールバック）
    plain_urls = re.findall(r'https?://[^\s<>\"\']+', text)
    return plain_urls


def fetch_webpage_text(url: str, max_length: int = MAX_TEXT_LENGTH) -> dict:
    """
    URLからWebページの本文テキストを取得する

    Args:
        url: 取得対象のURL
        max_length: 返すテキストの最大文字数

    Returns:
        dict: {"title": str, "text": str, "url": str}
              エラー時は {"title": "", "text": "", "url": url, "error": str}
    """
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        return {"title": "", "text": "", "url": url, "error": str(e)}

    content_type = response.headers.get("Content-Type", "")

    # PDF の場合は未対応として返す
    if "application/pdf" in content_type:
        return {
            "title": "",
            "text": "",
            "url": url,
            "error": "PDF ファイルは現在未対応です。",
        }

    html = response.text

    # --- 1) trafilatura で本文抽出を試みる（精度が高い） ---
    text = trafilatura.extract(html, include_comments=False, include_tables=True) or ""

    # --- 2) trafilatura で取れなければ BeautifulSoup にフォールバック ---
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.string.strip() if soup.title and soup.title.string else url

    if not text.strip():
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
            tag.decompose()

        # <article> → <main> → <body> の順で取得
        for container in [soup.find("article"), soup.find("main"), soup.find("body")]:
            if container:
                text = container.get_text(separator="\n", strip=True)
                break
        else:
            text = soup.get_text(separator="\n", strip=True)

    # 連続する空行を圧縮
    text = re.sub(r'\n{3,}', '\n\n', text)

    # テキスト長を制限
    if len(text) > max_length:
        text = text[:max_length] + "\n\n...(以下省略)"

    return {"title": title, "text": text, "url": url}


if __name__ == "__main__":
    # テスト
    test_url = "https://arxiv.org/abs/2301.12345"
    result = fetch_webpage_text(test_url)
    print(f"Title: {result['title']}")
    print(f"Text length: {len(result['text'])}")
    print(result["text"][:500])
