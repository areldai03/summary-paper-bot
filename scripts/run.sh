#!/bin/bash
#SBATCH --job-name=arxiv_nlp_bot
#SBATCH --output=logs/slurm-%x-%j.out
#SBATCH --time=00:30:00           # 最大実行時間
#SBATCH --partition=hestia       # 利用するパーティション名
#SBATCH --gres=gpu:1              # GPU が必要なら指定
#SBATCH --cpus-per-task=8         # CPU コア数
#SBATCH --mem=16G                 # メモリ

uv run python3 src/main.py