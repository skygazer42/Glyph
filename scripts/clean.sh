#!/usr/bin/env bash
set -euo pipefail

# Safe project cleanup: removes ONLY files ignored by .gitignore
# Usage: bash scripts/clean.sh [--yes] [--dry-run]

DRY_RUN=true
CONFIRM=false

for arg in "$@"; do
  case "$arg" in
    --yes|-y)
      CONFIRM=true
      ;;
    --dry-run|-n)
      DRY_RUN=true
      ;;
    --no-dry-run)
      DRY_RUN=false
      ;;
    -h|--help)
      echo "Usage: bash scripts/clean.sh [--yes] [--dry-run]"
      echo "  --yes        Perform deletion without interactive prompt"
      echo "  --dry-run    Show what would be deleted (default)"
      echo "  --no-dry-run Actually delete (requires --yes or prompt)"
      exit 0
      ;;
  esac
done

if ! command -v git >/dev/null 2>&1; then
  echo "git not found. Please run this script in a Git-enabled environment." >&2
  exit 1
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Not inside a Git repository. Aborting to stay safe." >&2
  exit 1
fi

if [[ "$DRY_RUN" == true ]]; then
  echo "[Dry run] Showing files that would be removed (ignored files only):"
  git clean -fdXn
  echo "\nNo changes made. Re-run with --no-dry-run to actually delete."
  exit 0
fi

if [[ "$CONFIRM" == false ]]; then
  read -r -p "This will DELETE all IGNORED files (git clean -fdX). Continue? [y/N] " ans
  case "$ans" in
    y|Y|yes|YES) ;;
    *) echo "Aborted."; exit 1;;
  esac
fi

echo "Deleting ignored files..."
git clean -fdX
echo "Done."

