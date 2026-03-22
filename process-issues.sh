#!/bin/bash
# Process GitHub issues sequentially with Claude Code.
# Each issue runs in a fresh context (no --continue).
#
# Usage:
#   ./process-issues.sh                          # all open issues labeled "ready"
#   ./process-issues.sh --label "phase-1"        # filter by label
#   ./process-issues.sh 26 27 28                 # specific issue numbers

set -euo pipefail

LABEL="ready"
ISSUE_NUMBERS=()
LOG_DIR="logs/issues"

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --label)
      LABEL="$2"
      shift 2
      ;;
    --log-dir)
      LOG_DIR="$2"
      shift 2
      ;;
    *)
      ISSUE_NUMBERS+=("$1")
      shift
      ;;
  esac
done

mkdir -p "$LOG_DIR"

# Build the list of issues
if [[ ${#ISSUE_NUMBERS[@]} -gt 0 ]]; then
  ISSUES=("${ISSUE_NUMBERS[@]}")
else
  mapfile -t ISSUES < <(
    gh issue list \
      --label "$LABEL" \
      --state open \
      --json number \
      --jq '.[].number' \
    | sort -n
  )
fi

if [[ ${#ISSUES[@]} -eq 0 ]]; then
  echo "No issues found. Pass issue numbers directly or use --label <label>."
  exit 0
fi

echo "=== Processing ${#ISSUES[@]} issue(s): ${ISSUES[*]} ==="
echo ""

PASSED=0
FAILED=0

for issue_num in "${ISSUES[@]}"; do
  # Fetch issue details
  ISSUE_TITLE=$(gh issue view "$issue_num" --json title --jq '.title')
  ISSUE_BODY=$(gh issue view "$issue_num" --json body --jq '.body')

  PLAN_LOG="$LOG_DIR/issue-${issue_num}-plan.log"
  IMPL_LOG="$LOG_DIR/issue-${issue_num}-impl.log"
  PLAN_FILE="$LOG_DIR/issue-${issue_num}-plan.md"
  echo "--- #${issue_num}: ${ISSUE_TITLE} ---"

  # Step 1: Plan (read-only exploration + write plan file)
  PLAN_PROMPT="You are in planning mode. Do NOT make any code changes.

GitHub issue #${issue_num}:
Title: ${ISSUE_TITLE}

Description:
${ISSUE_BODY}

Instructions:
1. Read the issue carefully and explore the codebase to understand what needs to change.
2. Identify all files that need modification.
3. Write a detailed implementation plan to ${PLAN_FILE} covering:
   - What the root cause / requirement is
   - Which files to modify and what changes to make in each
   - How to verify the fix (specific test commands or manual checks)
4. Do NOT edit any source code. Only write the plan file."

  echo "  Planning..."
  if ! claude -p "$PLAN_PROMPT" \
    --allowedTools "Read,Glob,Grep,Bash,Write" \
    > "$PLAN_LOG" 2>&1; then
    echo "  FAIL (planning) - logged to $PLAN_LOG"
    FAILED=$((FAILED + 1))
    echo "  Stopping on failure. Review $PLAN_LOG for details."
    break
  fi

  # Verify plan file was created
  if [[ ! -f "$PLAN_FILE" ]]; then
    echo "  FAIL - no plan file generated at $PLAN_FILE"
    FAILED=$((FAILED + 1))
    break
  fi

  PLAN_CONTENT=$(cat "$PLAN_FILE")

  # Step 2: Implement (fresh context with plan as input)
  IMPL_PROMPT="Implement GitHub issue #${issue_num}.

Title: ${ISSUE_TITLE}

Description:
${ISSUE_BODY}

A plan has already been created for this issue. Follow it closely:

${PLAN_CONTENT}

Instructions:
1. Follow the plan above to implement the fix or feature.
2. Run pytest to verify nothing is broken.
3. Commit your changes with a message referencing #${issue_num}.
4. Create a pull request for this issue."

  echo "  Implementing..."
  if claude -p "$IMPL_PROMPT" \
    --allowedTools "Read,Edit,Write,Glob,Grep,Bash" \
    > "$IMPL_LOG" 2>&1; then
    echo "  PASS - plan: $PLAN_LOG, impl: $IMPL_LOG"
    PASSED=$((PASSED + 1))
  else
    echo "  FAIL (implementation) - logged to $IMPL_LOG"
    FAILED=$((FAILED + 1))
    echo "  Stopping on failure. Review $IMPL_LOG for details."
    break
  fi
  echo ""
done

echo "=== Done: ${PASSED} passed, ${FAILED} failed ==="
