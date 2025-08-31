# arXiv NLP Bot

arXiv の cs.CL（自然言語処理）領域から新着論文を収集し、要約（vLLM: openai/gpt-oss-20b）して Slack に投稿します。重複投稿防止と日次ログを備えています。

## 機能
- 論文収集: cs.CL をベースに新着を取得（注目: N 件、サーベイ: M 件）
- フィルタ: 既投稿 ID を除外（logs/posted_papers.json）
- 要約: vLLM + Harmony で日本語要約（Slack 読みやすさ最適化）
- 投稿: Slack Incoming Webhook へ一括投稿
- ログ: 日付ごとに取得結果を保存（logs/YYYY-MM-DD.log）

## 構成
- main.py: 実行エントリ（取得→要約→投稿）
- fetch_papers.py: arXiv 取得/選別、重複管理
- summarize.py: vLLM による要約
- post_slack.py: Slack Webhook 投稿
- run.sh: Slurm 用ジョブスクリプト
- logs/: ログと posted_papers.json

## 必要要件
- OS: Linux
- Python: 3.10+
- 推奨: NVIDIA GPU（vLLM 推論用）
- 依存パッケージ（例）
  - arxiv
  - vllm
  - openai-harmony
  - python-dotenv
  - requests

インストール例（venv または uv など任意の方法で）
```
# uv のインストール（未導入の場合）
curl -LsSf https://astral.sh/uv/install.sh | sh
# 必要なら PATH 追加（例）
export PATH="$HOME/.local/bin:$PATH"

# 依存パッケージをインストール（プロジェクトルートで）
uv sync
```
## 定期実行（cron）
毎日 9:00 に実行する例（リポジトリ直下で .env を読む想定）
```
0 9 * * * cd /path/to/repo && /usr/bin/env -S bash -lc 'sbatch scripts/run.sh' >> logs/cron.out 2>&1