set -euo pipefail

OWNER="paidiver"
REPO="worms-cache"
CHART_DIR="api"

PAGES_BRANCH="gh-pages"
CHART_REPO_URL="https://${OWNER}.github.io/${REPO}/"

VERSION="0.0.2"

# Ensure tools exist
command -v helm >/dev/null
command -v cr >/dev/null
command -v yq >/dev/null

# 0) Add dependency repos (match CI)
helm repo add bitnami https://charts.bitnami.com/bitnami >/dev/null 2>&1 || true
helm repo update >/dev/null

# 1) Update Chart.yaml
yq -i ".version = \"${VERSION}\"" "${CHART_DIR}/Chart.yaml"
yq -i ".appVersion = \"${VERSION}\"" "${CHART_DIR}/Chart.yaml"

# 2) Build deps
helm dependency build "${CHART_DIR}"

# 3) Lint/package
rm -rf .cr-release-packages .cr-index
mkdir -p .cr-release-packages

helm lint "${CHART_DIR}"
helm package "${CHART_DIR}" --destination .cr-release-packages

# 4) Upload package(s) to GitHub Releases
: "${CR_TOKEN:?CR_TOKEN is not set. Export a GitHub PAT as CR_TOKEN.}"

cr upload \
  --owner "${OWNER}" \
  --git-repo "${REPO}" \
  --package-path .cr-release-packages \
  --skip-existing

# 5) Update index.yaml on the pages branch and push it
git fetch origin "${PAGES_BRANCH}:${PAGES_BRANCH}" || true
git checkout "${PAGES_BRANCH}" 2>/dev/null || git checkout -b "${PAGES_BRANCH}"

cr index \
  --owner "${OWNER}" \
  --git-repo "${REPO}" \
  --charts-repo "${CHART_REPO_URL}" \
  --package-path .cr-release-packages \
  --index-path index.yaml \
  --push
