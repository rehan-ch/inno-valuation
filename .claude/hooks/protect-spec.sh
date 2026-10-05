#!/bin/bash
# PreToolUse hook. Blocks edits to the signed-off methodology files unless the
# /decision skill has unlocked them. This stops a scoring rule from being
# changed in code without a tracked decision from Amy.
INPUT=$(cat)
if command -v jq >/dev/null 2>&1; then
  FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
else
  FILE=$(echo "$INPUT" | grep -o '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*:[[:space:]]*"\(.*\)"/\1/')
fi
[ -z "$FILE" ] && exit 0

ROOT="${CLAUDE_PROJECT_DIR:-.}"
case "$FILE" in
  *docs/methodology/scoring-spec.md|*docs/methodology/dimensions.yml)
    if [ -f "$ROOT/.claude/.spec-edit-unlocked" ]; then
      exit 0
    fi
    echo "Blocked: $FILE is the signed-off methodology. Record the change with /decision <Q-id> \"<answer>\" so it is tracked. That skill unlocks the file for the edit." >&2
    exit 2
    ;;
esac
exit 0
