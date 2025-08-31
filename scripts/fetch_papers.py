import arxiv
import datetime
import json
from pathlib import Path

POSTED_FILE = Path("logs/posted_papers.json")
LOG_DIR = Path("logs")

def load_posted_ids():
    """
    これまでに取得した論文のIDを読み込む
    """
    if POSTED_FILE.exists():
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_posted_ids(posted_ids):
    """
    投稿済みIDを保存
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(list(posted_ids), f, ensure_ascii=False, indent=2)

def fetch_papers(query: str = "cs.CL", max_results: int = 3):
    """
    arXiv API から論文を取得する
    Args:
        query (str): 検索クエリ
        max_results (int): 取得する最大件数
    Returns:
        List[dict]: 論文情報（タイトル, 要約, URL, 投稿日など）
    """
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )

    papers = []
    for result in search.results():
        papers.append({
            "id": result.entry_id.split("/")[-1],
            "title": result.title.strip().replace("\n", " "),
            "summary": result.summary.strip().replace("\n", " "),
            "url": result.entry_id,
            "published": result.published.strftime("%Y-%m-%d"),
            "updated": result.updated.strftime("%Y-%m-%d"),
        })
    return papers


def select_papers(num_main: int = 3, num_survey: int = 1):
    """
    注目論文とサーベイ論文を選択
    - 過去に取得していない論文のみ
    """
    posted_ids = load_posted_ids()

    # 自然言語処理の論文を新着から取得
    query = (
        "cs.CL AND ("
        "natural language processing OR llm OR NER OR text simplification OR "
        "difficulty estimation OR readability OR summarization OR "
        "Machine Translation OR slm)"
    )
    all_papers = fetch_papers(query=query, max_results=50)
    new_papers = [p for p in all_papers if p["id"] not in posted_ids]

    # 注目論文: 先頭から num_main 本
    selected = new_papers[:num_main]

    # サーベイ論文: タイトルに "survey" を含むもの
    survey_papers = fetch_papers(query=query + " AND survey", max_results=20)
    survey_candidates = [p for p in survey_papers if p["id"] not in posted_ids]
    survey = survey_candidates[:num_survey]

    # ログ保存
    today = datetime.date.today().isoformat()
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / f"{today}.log"
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(selected + survey, f, ensure_ascii=False, indent=2)

    # 投稿済み更新
    for p in selected + survey:
        posted_ids.add(p["id"])
    save_posted_ids(posted_ids)

    return selected, survey


if __name__ == "__main__":
    selected, survey = select_papers()
    print("=== 注目論文 ===")
    for p in selected:
        print(f"[{p['published']}] {p['title']} ({p['url']})")
    print("\n=== サーベイ論文 ===")
    for p in survey:
        print(f"[{p['published']}] {p['title']} ({p['url']})")