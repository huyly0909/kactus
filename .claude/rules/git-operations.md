# Git Operations

## Never commit or merge without explicit permission

`git commit`, `git merge`, `git cherry-pick`, `git rebase` (anything that creates a commit) — do NOT run any of these on your own initiative. Wait for the user to ask for that specific operation.

```bash
# WRONG — unprompted commit, even if labelled "wip" or "backup"
git commit -m "wip: snapshot before merge"

# WRONG — running cleanup commit after the user only said "do X"
git commit -m "chore: tidy up follow-ups"

# RIGHT — leave the working tree dirty, report what's staged, ask
git status
# "Staged the X / Y / Z. Commit?"
```

Authorization is per-operation, not blanket. "Do the merge" authorizes the merge commit; it does NOT authorize subsequent fix commits, cleanup commits, or amendments. "Build and test" authorizes building and testing; it does NOT authorize commits.

If you need to make space (e.g. a clean tree to merge into), prefer `git stash` over a "wip backup" commit.

## Other git rules (applies on top of Claude Code defaults)

- Never `git push`, `git push --force`, `git reset --hard`, or any other destructive operation without an explicit user ask.
- Never `--no-verify` to bypass hooks. Fix the hook failure instead.
- Never `--amend` unless the user asked for an amendment.
- For staging: prefer named files over `git add -A` / `git add .` (avoids accidentally committing secrets or large binaries).
