import arxiv
import datetime
import json
from pathlib import Path


def fetch_papers(query: str = "natural language processing", max_results: int = 3):
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


def save_papers(papers, log_dir: str = "logs"):
    """
    取得した論文をログとして保存する
    Args:
        papers (List[dict]): 論文情報のリスト
        log_dir (str): ログ保存ディレクトリ
    """
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    today = datetime.date.today().isoformat()
    out_file = Path(log_dir) / f"{today}.log"

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(papers, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    papers = fetch_papers(query="cs.CL OR cs.LG", max_results=5)
    save_papers(papers)
    for p in papers:
        print(f"[{p['published']}] {p['title']} ({p['url']})")