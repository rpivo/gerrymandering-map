"""Fail when a PR changes more than the repo's 1000-line limit.

Usage: python tools/check_pr_size.py BASE_REF [--limit N]

Counts added plus removed lines between BASE_REF and HEAD. Lockfiles and generated
site data don't count (see CLAUDE.md), but they are listed in the output.
"""

import argparse
import subprocess
import sys
from pathlib import PurePosixPath

LIMIT = 1000
LOCKFILES = {"uv.lock", "pnpm-lock.yaml", "package-lock.json", "yarn.lock"}
GENERATED_PREFIXES = ("site/src/data/",)


def is_exempt(path: str) -> bool:
    """Return True for lockfiles and generated site data, which don't count."""
    return PurePosixPath(path).name in LOCKFILES or path.startswith(GENERATED_PREFIXES)


def count_changed_lines(numstat: str) -> tuple[int, list[str]]:
    """Count added plus removed lines in `git diff --numstat` output.

    Returns:
        The total for non-exempt files, and the list of exempt paths that changed.
        Binary files (shown as "-") count as zero lines.
    """
    total = 0
    exempt = []
    for line in numstat.splitlines():
        if not line.strip():
            continue
        added, removed, path = line.split("\t", 2)
        if is_exempt(path):
            exempt.append(path)
        elif added != "-":
            total += int(added) + int(removed)
    return total, exempt


def check(numstat: str, limit: int = LIMIT) -> tuple[bool, str]:
    """Return whether the diff is within the limit, and a message saying so."""
    total, exempt = count_changed_lines(numstat)
    ok = total <= limit
    lines = [f"{total} changed lines (limit {limit})."]
    if not ok:
        lines.append("This PR is too large. Split it into smaller PRs (see CLAUDE.md).")
    if exempt:
        lines.append("Not counted (lockfiles and generated data):")
        lines.extend(f"  {path}" for path in exempt)
    return ok, "\n".join(lines)


def main(argv: list[str]) -> int:
    """Diff HEAD against the base ref and check the size. Returns the process exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", help="Base ref, for example origin/main")
    parser.add_argument("--limit", type=int, default=LIMIT)
    args = parser.parse_args(argv)
    numstat = subprocess.run(
        ["git", "diff", "--numstat", "--no-renames", f"{args.base}...HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    ok, message = check(numstat, args.limit)
    print(message)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
