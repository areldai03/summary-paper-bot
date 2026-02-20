import re
import logging

logger = logging.getLogger(__name__)

# --- モデルを遅延ロード（import 時にはロードしない） ---
_model = None
_encoding = None


def _get_model():
    """初回呼び出し時にのみモデルをロードする"""
    global _model, _encoding
    if _model is None:
        from vllm import LLM
        from openai_harmony import HarmonyEncodingName, load_harmony_encoding

        _model = LLM(model="openai/gpt-oss-20b", trust_remote_code=True)
        _encoding = load_harmony_encoding(HarmonyEncodingName.HARMONY_GPT_OSS)
    return _model, _encoding


def summarize_paper_vllm(paper):
    """
    論文情報を受け取り、日本語で要約
    Slackで見やすい形式で出力
    """
    from vllm import SamplingParams
    from openai_harmony import (
        Conversation, Message, Role, SystemContent, DeveloperContent,
    )

    model, encoding = _get_model()

    title = paper["title"]
    abstract = paper["summary"]
    url = paper["url"]

    user_prompt = f"""
        以下の論文を日本語で要約してください。

        - 背景・目的、方法（実験）、結果の順で整理してください。
        - 箇条書きで示す際に，文頭に "- " を付与してください。
        - 各項目は *太字の見出し*(*背景・目的*のように) をつけてまとめてください。
        - ただし、本文には * を含めないでください。
        - 短文，改行多めの形式にしてください。
        - 専門的なニュアンスは保ったまま、冗長な説明は省いてください。
        - 実装に関するGitHubのリンクは無視してください。

        論文タイトル: {title}
        アブストラクト: {abstract}

        要約:
    """

    # --- 1) Harmony形式でメッセージを組み立てる ---
    convo = Conversation.from_messages(
        [
            Message.from_role_and_content(Role.SYSTEM, SystemContent.new()),
            Message.from_role_and_content(Role.DEVELOPER, DeveloperContent.new().with_instructions("あなたは、自然言語処理の論文を日本語で要約するアシスタントです。"),
            ),
            Message.from_role_and_content(Role.USER, user_prompt),
        ]
    )

    prefill_ids = encoding.render_conversation_for_completion(convo, Role.ASSISTANT)
    stop_token_ids = encoding.stop_tokens_for_assistant_actions()

    # --- 2) サンプリングパラメータ ---
    sampling_params = SamplingParams(
        max_tokens=2048,
        temperature=0.7,
        top_k=50,
        top_p=0.9,
        stop_token_ids=stop_token_ids,
    )

    # --- 3) vLLM推論 ---
    outputs = model.generate(
        prompt_token_ids=[prefill_ids],
        sampling_params=sampling_params,
    )

    gen = outputs[0].outputs[0]
    text = gen.text
    output_tokens = gen.token_ids

    # --- 4) Harmony形式にパースして整形 ---
    entries = encoding.parse_messages_from_completion_tokens(output_tokens, Role.ASSISTANT)
    summary_texts = []
    for e in entries:
        if e.channel == "final":  # finalだけ抽出
            if hasattr(e, "content"):
                for c in e.content:
                    if hasattr(c, "text"):
                        summary_texts.append(c.text)

    summary_text = "\n".join(summary_texts)

    summary_text = re.sub(r"\*{2}", "*", summary_text)
    summary_text = re.sub(r'(^|\n)[ \t]*-', r'\1• ', summary_text)

    # --- 5) Slack用に整形 ---
    slack_text = f"*{title}* <{url}|[link]>\n\n{summary_text.strip()}\n\n"
    return slack_text


def summarize_papers_vllm(papers):
    summarized = []
    for p in papers:
        slack_summary = summarize_paper_vllm(p)
        summarized.append({**p, "slack_summary": slack_summary})
    return summarized


def unload_model():
    """モデルを GPU メモリから解放"""
    global _model, _encoding
    if _model is not None:
        del _model
        _model = None
    _encoding = None
    import torch, gc
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    logger.info("モデルを解放しました")


if __name__ == "__main__":
    sample_paper = {
        "title": "Large Language Models for NLP",
        "summary": (
            "Natural language processing (NLP) has made significant progress in recent years, "
            "particularly with the advent of large language models (LLMs). "
            "These models achieve state-of-the-art results in many NLP tasks."
        ),
        "url": "http://arxiv.org/abs/2508.12345",
    }

    slack_ready = summarize_paper_vllm(sample_paper)
    print(slack_ready)