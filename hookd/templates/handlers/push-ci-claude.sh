#!/usr/bin/env bash
set -euo pipefail

# hookd handler: push → run tests + auto-fix
# On push to the configured branch, runs tests.
# If tests fail, Claude attempts to fix them and pushes a fix commit.
#
# Required env: HOOKD_GITHUB_TOKEN, HOOKD_REPO, HOOKD_BRANCH,
#               HOOKD_COMMIT_MESSAGES, HOOKD_WORKDIR

echo "[hookd] Push to ${HOOKD_BRANCH}: ${HOOKD_COMMIT_MESSAGES}"

cd "$HOOKD_WORKDIR"
git fetch origin "$HOOKD_BRANCH" --quiet
git checkout "$HOOKD_BRANCH" --quiet
git reset --hard "origin/$HOOKD_BRANCH" --quiet

# Detect test runner
if [ -f "Makefile" ] && grep -q "^test:" Makefile; then
    TEST_CMD="make test"
elif [ -f "pyproject.toml" ]; then
    TEST_CMD="python -m pytest"
elif [ -f "package.json" ]; then
    TEST_CMD="npm test"
elif [ -f "Cargo.toml" ]; then
    TEST_CMD="cargo test"
else
    echo "[hookd] No test runner detected, skipping"
    exit 0
fi

echo "[hookd] Running: $TEST_CMD"

if $TEST_CMD; then
    echo "[hookd] Tests passed"
    exit 0
fi

echo "[hookd] Tests failed, asking Claude to fix..."

# Capture the failure output
FAILURE=$($TEST_CMD 2>&1 || true)

PROMPT="You are working on repo ${HOOKD_REPO}, branch ${HOOKD_BRANCH}.

The following test command failed after a recent push:
  $ ${TEST_CMD}

Test output:
\`\`\`
${FAILURE}
\`\`\`

Recent commits:
${HOOKD_COMMIT_MESSAGES}

Please fix the failing tests. Commit your fix."

claude --print "$PROMPT"

# If claude made fixes, push them
if [ "$(git status --porcelain | wc -l)" -gt 0 ] || [ "$(git log "origin/$HOOKD_BRANCH..HEAD" --oneline | wc -l)" -gt 0 ]; then
    git push origin "$HOOKD_BRANCH" --quiet
    echo "[hookd] Claude pushed a fix to ${HOOKD_BRANCH}"
else
    echo "[hookd] Claude could not fix the tests"
fi
