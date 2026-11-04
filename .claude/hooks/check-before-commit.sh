#!/usr/bin/env bash
# Claude Code PreToolUse hook: block `git commit` unless `make check` passes.
# Exit code 2 blocks the tool call and shows stderr to Claude.
set -uo pipefail

command=$(jq -r '.tool_input.command // empty')

if ! grep -qE '(^|[;&|[:space:]])git([[:space:]]+-[cC][[:space:]]+[^[:space:]]+)*[[:space:]]+commit([[:space:]]|$)' <<<"$command"; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}" || exit 2

if ! output=$(make check 2>&1); then
  {
    echo "Commit blocked: 'make check' failed. Fix it before committing (see CLAUDE.md)."
    echo
    tail -n 40 <<<"$output"
  } >&2
  exit 2
fi
exit 0
