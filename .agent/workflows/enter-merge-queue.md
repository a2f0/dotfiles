---
description: Guarantee PR merge by cycling until merged
---

# Enter Merge Queue

This skill guarantees a PR gets merged by continuously updating from base, fixing CI, addressing reviews, and waiting until the PR is actually merged.

## Steps

1. **Verify PR exists**: Run `gh pr view --json number,title,headRefName,baseRefName,url,state` to get PR info. If no PR exists, abort with a message. Store the `baseRefName` for use in subsequent steps.

2. **Check current branch**: Ensure you're on the PR's head branch, not `main`.

3. **Main loop** - Repeat until PR is merged:

   ### 3a. Check PR state

   ```bash
   gh pr view --json state,mergeStateStatus,mergeable
   ```

   - If `state` is `MERGED`: Exit loop and proceed to step 4
   - If `mergeStateStatus` is `BEHIND`: Update from base (step 3b)
   - If `mergeStateStatus` is `BLOCKED` or `UNKNOWN`: Address feedback (step 3c/3d), then wait for CI (step 3e)
   - If `mergeStateStatus` is `CLEAN`: Ensure auto-merge is enabled and wait (step 3f)

   ### 3b. Update from base branch (rebase)

   Use rebase to keep the branch history clean (no merge commits for updates):

   ```bash
   git fetch origin <baseRefName>
   git rebase origin/<baseRefName>
   ```

   - If rebase conflicts occur:
     1. Run `git rebase --abort` to restore the branch
     2. List the conflicting files
     3. Stop and ask the user for help. Do NOT auto-resolve conflicts.
   - If successful, force push (required after rebase) and continue to step 3c:

     ```bash
     git push --force-with-lease
     ```

   ### 3c. Wait for Review (first iteration only)

   On the first pass through the loop, poll for reviews:

   ```bash
   gh pr view <pr-number> --json reviews
   ```

   Check every 30 seconds until a review is found (timeout: 5 minutes).

   ### 3d. Address Feedback

   **Important**: All conversation threads must be resolved before the PR can merge.

   - Notify that feedback has been addressed
   - Wait for response (polling every 30 seconds, up to 5 minutes)
   - When a fix is satisfactory, resolve the thread
   - If further changes are requested, repeat step 3d

   ### 3e. Wait for CI (with branch freshness checks)

   **Important**: Check if branch is behind BEFORE waiting for CI, and periodically during CI. This prevents wasting time on CI runs that will be obsolete.

   ```bash
   git rev-parse HEAD
   gh run list --commit <commit-sha> --limit 1 --json status,conclusion,databaseId
   ```

   **While CI is running**:
   - Every 2-3 minutes, check if branch is behind: `gh pr view --json mergeStateStatus`
   - If `mergeStateStatus` is `BEHIND`: **Immediately** go back to step 3b (don't wait for CI to finish)
   - This avoids wasting 15-20 minutes on a CI run that will need to be rerun anyway

   **When CI completes**:
   - If CI **passes**: Continue to step 3f
   - If CI is **cancelled**: Rerun CI using the CLI (do NOT push empty commits):

     ```bash
     gh run rerun <run-id>
     ```

   - If CI **fails**: Diagnose and fix the failure, then return to monitoring CI status

   ### 3f. Enable auto-merge and wait

   ```bash
   gh pr merge --auto --merge
   ```

   Then poll for merge completion:

   ```bash
   gh pr view --json state,mergeStateStatus
   ```

   - If `state` is `MERGED`: Exit loop
   - If `mergeStateStatus` is `BEHIND`: Go back to step 3b
   - Otherwise: Wait 30 seconds and check again

4. **Reset workspace**: Once the PR is merged, switch back to main and pull latest:

   ```bash
   git checkout main && git pull
   ```

5. **Report success**: Confirm the PR was merged and provide a summary:
   - Show the PR URL
   - Output a brief description of what was merged (1-3 sentences summarizing the changes based on the PR title and commits)

## Resolving Conversation Threads

**All conversation threads must be resolved before the PR can merge.** When resolving a thread, provide context in the thread itself (not the PR body).

### Before Resolving a Thread

Reply to the thread with:

1. **The commit(s) that fixed the issue** - Link to the specific commit(s) that addressed the feedback
2. **If an issue was opened** - Link the issue that will track the work

### Reply Format

```bash
# Get the commit SHA for the fix
git log --oneline -1

# Reply to the thread with context
gh api repos/{owner}/{repo}/pulls/{pr}/comments/{comment_id}/replies \
  -f body="Fixed in commit abc1234. Please confirm."
```

### Then Resolve the Thread

```bash
gh api graphql -f query='
  mutation {
    resolveReviewThread(input: {threadId: "<thread_node_id>"}) {
      thread { isResolved }
    }
  }
'
```

## Notes

- This skill loops until the PR is **actually merged**, not just until auto-merge is enabled
- If multiple PRs are in the queue, this PR may need to update from main multiple times as others merge
- Common fixable issues: lint errors, type errors, test failures, code style suggestions
- Non-fixable issues: merge conflicts, infrastructure failures, architectural disagreements
- If stuck in a loop (same fix attempted twice), ask the user for help

## Commit Rules

When committing fixes during the merge queue process:

### Conventional Commit Format

- Subject line: `<type>(<scope>): <description>` (max 50 chars)
- Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `perf`, `ci`, `build`
- Scope: prefer feature-based (`pwa`, `auth`, `settings`) over package-based when possible
- Description should be imperative mood ("add" not "added")
- Body can contain detailed explanation (wrap at 72 chars)

### GPG Signing

The commit MUST be signed. Use a 15-second timeout. For multi-line messages, pipe the content to `git commit`:

```bash
printf "subject\n\nbody" | timeout 15 git commit -S -F -
```

### DO NOT

- Add `Co-Authored-By` headers
- Add emoji or "Generated with Antigravity" footers
- Use `--no-gpg-sign` or skip signing
