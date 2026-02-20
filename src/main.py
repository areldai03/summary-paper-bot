import argparse
from fetch_papers import select_papers
from summarize import summarize_papers_vllm
from post_slack import post_papers_slack


def run_batch():
    """既存の日次バッチ処理: 新着論文を取得→要約→Slack投稿"""
    # 論文を取得
    selected_papers, survey_papers = select_papers(num_main=3, num_survey=1)
    all_papers = selected_papers + survey_papers

    if not all_papers:
        print("新しい論文はありません。")
        return

    # 論文を要約
    summarized_papers = summarize_papers_vllm(all_papers)

    # Slackに投稿
    post_papers_slack(summarized_papers)


def run_bot():
    """Slack Bot を Socket Mode で常駐起動"""
    from slack_bot import start_bot
    start_bot()


def main():
    parser = argparse.ArgumentParser(description="Paper Summarizer Bot")
    parser.add_argument(
        "--bot",
        action="store_true",
        help="Slack Bot モードで起動 (URL を検知して要約を返信)",
    )
    args = parser.parse_args()

    if args.bot:
        run_bot()
    else:
        run_batch()


if __name__ == "__main__":
    main()
