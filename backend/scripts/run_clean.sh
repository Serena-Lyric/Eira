#!/usr/bin/env bash
# 干净启动后端：杀净 8000 端口残留进程 → 清 __pycache__ → 无 --reload 启动
# 用法：bash backend/scripts/run_clean.sh
set -euo pipefail

cd "$(dirname "$0")/.."   # → backend/

echo "[1/3] 杀净 8000 端口残留进程..."
# Windows (git-bash)：找出监听 8000 的 PID 并连同子进程树杀掉
if command -v netstat >/dev/null 2>&1; then
  PIDS=$(netstat -ano 2>/dev/null | grep ":8000" | grep LISTEN | awk '{print $5}' | sort -u || true)
  for pid in $PIDS; do
    echo "  - taskkill PID $pid (含子进程树)"
    taskkill //F //PID "$pid" //T 2>/dev/null || true
  done
fi
sleep 1

echo "[2/3] 清理 __pycache__（避免 stale 字节码）..."
find app -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true

echo "[3/3] 启动后端（无 --reload，确保单进程跑当前磁盘代码）..."
export EIRA_JWT__SECRET="${EIRA_JWT__SECRET:-dev-secret}"
export EIRA_OSS__SECRET="${EIRA_OSS__SECRET:-eira-secret}"
export EIRA_DB_DSN="${EIRA_DB_DSN:-postgresql+asyncpg://eira:eira@localhost:5432/eira}"
export EIRA_REDIS_URL="${EIRA_REDIS_URL:-redis://localhost:6379/0}"
export EIRA_OSS_ENDPOINT="${EIRA_OSS_ENDPOINT:-http://localhost:9000}"

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
