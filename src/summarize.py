import re
import logging
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pdf_extractor import download_and_extract_pdf_text

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

        _model = LLM(
            model="openai/gpt-oss-20b", 
            trust_remote_code=True, 
            tensor_parallel_size=2,
            max_model_len=12000, 
            max_num_seqs=4
        )
        _encoding = load_harmony_encoding(HarmonyEncodingName.HARMONY_GPT_OSS)
    return _model, _encoding


def _generate_text(model, encoding, prompt, sys_prompt="あなたは、論文の情報を抽出・要約するアシスタントです。"):
    from vllm import SamplingParams
    from openai_harmony import Conversation, Message, Role, SystemContent, DeveloperContent

    convo = Conversation.from_messages([
        Message.from_role_and_content(Role.SYSTEM, SystemContent.new()),
        Message.from_role_and_content(Role.DEVELOPER, DeveloperContent.new().with_instructions(sys_prompt)),
        Message.from_role_and_content(Role.USER, prompt)
    ])
    prefill_ids = encoding.render_conversation_for_completion(convo, Role.ASSISTANT)
    stop_token_ids = encoding.stop_tokens_for_assistant_actions()
    
    sampling_params = SamplingParams(max_tokens=4096, temperature=0.7, top_k=50, top_p=0.9, stop_token_ids=stop_token_ids)
    
    outputs = model.generate(prompt_token_ids=[prefill_ids], sampling_params=sampling_params)
    gen = outputs[0].outputs[0]
    
    entries = encoding.parse_messages_from_completion_tokens(gen.token_ids, Role.ASSISTANT)
    texts = []
    for e in entries:
        if e.channel == "final" and hasattr(e, "content"):
            for c in e.content:
                if hasattr(c, "text"): texts.append(c.text)
    return "\n".join(texts)


def summarize_paper_vllm(paper):
    """
    論文情報（PDF本文含む）を受け取り、日本語で要約
    Slackで見やすい形式で出力
    """
    model, encoding = _get_model()

    title = paper["title"]
    abstract = paper["summary"]
    url = paper["url"]
    pdf_url = paper.get("pdf_url")
    
    chunk_summaries = []
    full_text = ""
    if pdf_url:
        print(f"\n[INFO] PDFのダウンロードとテキスト抽出を開始します: {pdf_url}")
        full_text = download_and_extract_pdf_text(pdf_url)
        print(f"[INFO] 抽出完了: 合計 {len(full_text)} 文字を取得しました。")
        
    if full_text and len(full_text.strip()) > 500:
        # LangChain text splitterで分割
        splitter = RecursiveCharacterTextSplitter(chunk_size=10000, chunk_overlap=500)
        chunks = splitter.split_text(full_text)
        print(f"[INFO] テキストを {len(chunks)} チャンク（最大約10000文字/チャンク）に分割しました。")
        
        # 全部のチャンクを要約対象にする
        target_chunks = chunks
        print(f"[INFO] 全チャンク（計{len(target_chunks)}チャンク）を要約対象にします。")
            
        for i, chunk in enumerate(target_chunks):
            print(f"\n--- [Map処理 {i+1}/{len(target_chunks)}] チャンク要約開始 ---")
            print(f"📝 チャンク冒頭プレビュー: {chunk[:100].replace(chr(10), ' ')}...")
            prompt = f"以下の論文の一部の文章から、重要な情報（背景、実験方法、主な結果、考察など）を日本語で2〜3つの箇条書きで抽出してください。不要な情報や数式は省いてください。\n\n論文タイトル: {title}\n部分テキスト:\n{chunk}\n\n抽出内容:"
            res = _generate_text(model, encoding, prompt)
            print(f"✅ チャンク要約結果:\n{res}")
            chunk_summaries.append(res)
            
    all_chunks_text = "\n".join(chunk_summaries)
    print("\n[INFO] 全チャンクの要約統合（Reduce処理）を開始します...")

    final_prompt = f"""
        以下の論文の「アブストラクト」と「本文の各部分の要約」を統合し、日本語で最終的な論文の要約を作成してください。
        以下のフォーマット（見出しと箇条書き）に厳密に従って出力してください。

        （出力フォーマット例）
        *背景・目的*
        - 箇条書きで概要を記述
        - ...

        *方法（実験）*
        - 箇条書きで概要を記述
        - ...

        *結果*
        - 箇条書きで概要を記述
        - ...

        *考察・応用*
        - 箇条書きで専門家としてのあなたの見解(考察・応用)を記述
        - ...

        専門的なニュアンスは保ったまま、冗長な説明や数式、実装に関するGitHubのリンクは省いてください。
        本文には、見出しを囲むための「*」以外は使用しないでください。
        箇条書きの各項目は短文・改行多めを心がけてください。

        論文タイトル: {title}
        アブストラクト:
        {abstract}
        
        本文の部分的な要約の統合:
        {all_chunks_text}

        要約:
    """
    
    # 最終的な要約を生成
    summary_text = _generate_text(model, encoding, final_prompt, sys_prompt="あなたは、自然言語処理の論文を日本語で要約するアシスタントです。")

    summary_text = re.sub(r"\*{2}", "*", summary_text)
    summary_text = re.sub(r'(^|\n)[ \t]*-', r'\1• ', summary_text)

    # Slack用に整形 ---
    slack_text = f"*{title}* <{url}|[arXiv]>\n\n{summary_text.strip()}\n\n"
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