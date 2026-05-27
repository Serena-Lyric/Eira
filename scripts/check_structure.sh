#!/usr/bin/env bash
set -euo pipefail
required=(
  apps/web-user
  apps/web-admin
  packages/ui-shared
  backend
  deploy
  scripts
  docs/superpowers/specs
  docs/superpowers/plans
  docs/superpowers/validations
)
for d in "${required[@]}"; do
  if [[ ! -d "$d" ]]; then
    echo "missing: $d"
    exit 1
  fi
done
echo "structure ok"
