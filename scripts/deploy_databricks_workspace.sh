#!/usr/bin/env bash
set -euo pipefail

APP_NAME="${DATABRICKS_APP_NAME:-homewise-sg}"
WORKSPACE_PATH="${DATABRICKS_WORKSPACE_PATH:-/Workspace/Users/${USER}/homewise-sg}"

if ! command -v databricks >/dev/null 2>&1; then
  echo "Databricks CLI is not installed."
  exit 1
fi

echo "Syncing source to $WORKSPACE_PATH"
databricks workspace mkdirs "$WORKSPACE_PATH"
databricks sync . "$WORKSPACE_PATH" --exclude .venv --exclude data/cache --exclude .git

if ! databricks apps get "$APP_NAME" >/dev/null 2>&1; then
  databricks apps create "$APP_NAME"
fi

echo "Deploying $APP_NAME from workspace path $WORKSPACE_PATH"
databricks apps deploy "$APP_NAME" --source-code-path "$WORKSPACE_PATH"
