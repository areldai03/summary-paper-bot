#!/bin/bash
#SBATCH --job-name=slack_bot
#SBATCH --output=logs/slurm-%x-%j.out
#SBATCH --time=04:00:00           # Bot 常駐用（4時間）
#SBATCH --partition=varuna
#SBATCH --gres=gpu:2
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G

cd /home/maekawa/summary-paper-bot
uv run python3 src/main.py --bot
