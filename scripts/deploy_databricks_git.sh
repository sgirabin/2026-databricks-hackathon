#!/usr/bin/env bash
set -euo pipefail

APP_NAME="${DATABRICKS_APP_NAME:-homewise-sg}"
GIT_REPO_URL="${GIT_REPO_URL:-https://github.com/sgirabin/2026-databricks-hackathon}"
GIT_BRANCH="${GIT_BRANCH:-main}"

if ! command -v databricks >/dev/null 2>&1; then
  echo "Databricks CLI is not installed. Install it first, then run: databricks auth login --host https://<workspace-url>"
  exit 1
fi

if databricks apps get "$APP_NAME" >/dev/null 2>&1; then
  echo "App $APP_NAME already exists. Deploying from Git."
else
  echo "Creating app $APP_NAME"
  databricks apps create "$APP_NAME" --json "{\"git_repository\":{\"url\":\"$GIT_REPO_URL\",\"provider\":\"gitHub\"}}"
fi

echo "Deploying $APP_NAME from $GIT_REPO_URL@$GIT_BRANCH"
databricks apps deploy "$APP_NAME" --json "{\"git_source\":{\"branch\":\"$GIT_BRANCH\"}}"
