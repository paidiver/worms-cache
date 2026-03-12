#!/usr/bin/env bash
set -euo pipefail

OWNER="paidiver"
REPO="worms-cache"
CHART_DIR="deployment/charts"

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "${REPO_ROOT}"

PAGES_BRANCH="gh-pages"
CHART_REPO_URL="https://${OWNER}.github.io/${REPO}/"
export CR_TOKEN="${GHCR_TOKEN}"

VERSION="0.0.2-debug.$(date +%Y%m%d%H%M%S)"

command -v helm >/dev/null || echo "helm is not installed"
command -v cr >/dev/null || echo "cr is not installed"
command -v yq >/dev/null || echo "yq is not installed"

helm repo add bitnami https://charts.bitnami.com/bitnami >/dev/null 2>&1 || true
helm repo update >/dev/null

yq -i ".version = \"${VERSION}\"" "${CHART_DIR}/Chart.yaml"
yq -i ".appVersion = \"${VERSION}\"" "${CHART_DIR}/Chart.yaml"

helm dependency build "${CHART_DIR}"

rm -rf .cr-release-packages .cr-index
mkdir -p .cr-release-packages

helm lint "${CHART_DIR}"
helm package "${CHART_DIR}" --destination .cr-release-packages

: "${CR_TOKEN:?CR_TOKEN is not set. Export a GitHub PAT as CR_TOKEN.}"

cr upload \
  --owner "${OWNER}" \
  --git-repo "${REPO}" \
  --package-path .cr-release-packages \
  --skip-existing

rm -rf .cr-index
mkdir -p .cr-index

cr index \
  --owner "${OWNER}" \
  --git-repo "${REPO}" \
  --package-path .cr-release-packages \
  --index-path .cr-index/index.yaml

tmprepo="$(mktemp -d)"
git init "${tmprepo}" >/dev/null
git -C "${tmprepo}" checkout --orphan "${PAGES_BRANCH}" >/dev/null

cp .cr-index/index.yaml "${tmprepo}/index.yaml"

git -C "${tmprepo}" add index.yaml
git -C "${tmprepo}" \
  -c user.name="release-script" \
  -c user.email="release-script@example.com" \
  commit -m "Update Helm index" >/dev/null

git -C "${tmprepo}" remote add origin "$(git remote get-url origin)"
git -C "${tmprepo}" push --force origin "${PAGES_BRANCH}"

rm -rf "${tmprepo}"
