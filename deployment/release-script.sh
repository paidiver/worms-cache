set -euo pipefail

OWNER="paidiver"
REPO="worms-cache"
CHART_DIR="charts"

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

git fetch origin "${PAGES_BRANCH}"
git branch -f "${PAGES_BRANCH}" "origin/${PAGES_BRANCH}"

rm -rf .cr-index
mkdir -p .cr-index
cr index \
  --owner "${OWNER}" \
  --git-repo "${REPO}" \
  --package-path .cr-release-packages \
  --remote origin \
  --pages-branch gh-pages \
  --pages-index-path index.yaml \
  --push
