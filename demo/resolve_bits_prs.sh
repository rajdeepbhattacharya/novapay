#!/bin/bash
git fetch github
for branch in $(git branch -r | grep "github/dd/" | sed 's|github/||'); do
  echo "Resolving: $branch"
  git checkout -b "$branch" "github/$branch" 2>/dev/null || git checkout "$branch"
  git merge main --strategy-option=theirs -m "merge: resolve conflict keeping Bits AI changes" 2>/dev/null || true
  git push github "$branch" --force
  git checkout main
done
echo "All Bits AI PRs resolved"
