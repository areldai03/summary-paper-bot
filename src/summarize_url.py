"""
汎用 Web ページ要約モジュール
既存の summarize.py の vLLM + openai_harmony 基盤を再利用し、
論文ではなく一般的な Web ページを要約するプロンプトを使用する
"""

import re

# --- LLM を遅延ロードして summarize.py とモデルインスタンスを共有 ---
_model = None
_encoding = None


def _get_model():
    """モデルを遅延ロードする（初回呼び出し時のみ）"""
    global _model, _encoding
    if _model is None:
        from vllm import LLM
        from openai_harmony import HarmonyEncodingName, load_harmony_encoding

        _model = LLM(model="openai/gpt-oss-20b", trust_remote_code=True)
        _encoding = load_harmony_encoding(HarmonyEncodingName.HARMONY_GPT_OSS)
    return _model, _encoding


def summarize_webpage(page_data: dict) -> str:
    """
    Web ページの情報を受け取り、日本語で要約する

    Args:
        page_data: {"title": str, "text": str, "url": str}

    Returns:
        Slack mrkdwn 形式の要約テキスト
    """
    from vllm import SamplingParams
    from openai_harmony import (
        Conversation,
        Message,
        Role,
        SystemContent,
        DeveloperContent,
    )

    model, encoding = _get_model()

    title = page_data["title"]
    text = page_data["text"]
    url = page_data["url"]

    user_prompt = f"""
以下のWebページの内容を、Slackでサクッと読めるように日本語で要約してください。

【要約のルール】
- 専門的な用語やニュアンスは残しつつ、冗長な表現は削ぎ落としてください。
- 1文は短く（体言止めも可）、テンポよく読めるように改行を多めにしてください。
- 箇条書きの文頭は「• 」を使用してください。
- 必ず以下の【出力フォーマット】に忠実に従って出力してください。
- フォーマットの見出し以外で、本文中にアスタリスク（*）は絶対に使用しないでください（Slackの装飾崩れを防ぐため）。

【出力フォーマット】
*💡 一言まとめ*
（記事の核心や結論を1〜2文で記載）

*📝 概要・背景*
• （なぜこの記事が書かれたか、前提となる情報などを箇条書き）
• （...）

*🎯 重要なポイント*
• （最も重要な事実、結果、主張などを3〜5個の箇条書きで）
• （...）
• （...）

---
ページタイトル: {title}
本文:
{text}
"""

    # Harmony 形式でメッセージを組み立てる
    convo = Conversation.from_messages(
        [
            Message.from_role_and_content(Role.SYSTEM, SystemContent.new()),
            Message.from_role_and_content(
                Role.DEVELOPER,
                DeveloperContent.new().with_instructions(
                    "あなたは、Web ページの内容を日本語で簡潔に要約するアシスタントです。"
                ),
            ),
            Message.from_role_and_content(Role.USER, user_prompt),
        ]
    )

    prefill_ids = encoding.render_conversation_for_completion(convo, Role.ASSISTANT)
    stop_token_ids = encoding.stop_tokens_for_assistant_actions()

    sampling_params = SamplingParams(
        max_tokens=2048,
        temperature=0.7,
        top_k=50,
        top_p=0.9,
        stop_token_ids=stop_token_ids,
    )

    outputs = model.generate(
        prompt_token_ids=[prefill_ids],
        sampling_params=sampling_params,
    )

    gen = outputs[0].outputs[0]
    output_tokens = gen.token_ids

    # Harmony 形式にパースして整形
    entries = encoding.parse_messages_from_completion_tokens(
        output_tokens, Role.ASSISTANT
    )
    summary_texts = []
    for e in entries:
        if e.channel == "final":
            if hasattr(e, "content"):
                for c in e.content:
                    if hasattr(c, "text"):
                        summary_texts.append(c.text)

    summary_text = "\n".join(summary_texts)

    # Slack mrkdwn 用の整形
    summary_text = re.sub(r"\*{2}", "*", summary_text)
    summary_text = re.sub(r"(^|\n)[ \t]*-", r"\1• ", summary_text)

    # Slack 用に整形して返す
    slack_text = f"📝 *{title}*\n<{url}|🔗 元ページ>\n\n{summary_text.strip()}"
    return slack_text


if __name__ == "__main__":
    sample = {
        "title": "Test Page",
        "text": (
            "This is a sample web page about machine learning. "
            "Machine learning is a subset of artificial intelligence. "
            "It involves training models on data to make predictions."
        ),
        "url": "https://example.com",
    }
    result = summarize_webpage(sample)
    print(result)
