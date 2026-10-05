#!/bin/bash
# PostToolUse hook. After an edit to the scoring engine (or its data file),
# run only the fast engine tests and feed failures back to Claude.
INPUT=$(cat)
if command -v jq >/dev/null 2>&1; then
  FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
else
  FILE=$(echo "$INPUT" | grep -o '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*:[[:space:]]*"\(.*\)"/\1/')
fi
[ -z "$FILE" ] && exit 0

ROOT="${CLAUDE_PROJECT_DIR:-.}"
case "$FILE" in
  *backend/app/scoring/*|*backend/tests/scoring/*|*app/scoring/*|*tests/scoring/*|*docs/methodology/dimensions.yml)
    if [ -x "$ROOT/bin/test-scoring" ]; then
      OUT=$("$ROOT/bin/test-scoring" 2>&1)
      STATUS=$?
      if [ "$STATUS" -ne 0 ]; then
        echo "Scoring engine tests FAILED after editing $FILE:" >&2
        echo "$OUT" | tail -40 >&2
        exit 2
      fi
    fi
    ;;
esac
exit 0
