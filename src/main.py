from fetch_papers import select_papers
from summarize import summarize_papers_vllm
from post_slack import post_papers_slack

def main():
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

if __name__ == "__main__":
    main()
