---
description: Commit staged changes and push to remote using conventional commits
---

# Commit and Push

Commit and push the current changes following these rules:

1. **Check branch**: If on `main`, create a new branch with an appropriate name based on the changes.

2. **Analyze changes**: Run `git status` and `git diff --staged` to understand what's being committed.

3. **Conventional commit format**:
   - Subject line: `<type>(<scope>): <description>` (max 50 chars)
   - Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `perf`, `ci`, `build`
   - Scope: prefer feature-based (`pwa`, `auth`, `settings`) over package-based when possible
   - Description should be imperative mood ("add" not "added")
   - Body can contain detailed explanation (wrap at 72 chars)

4. **DO NOT**:
   - Add `Co-Authored-By` headers
   - Add emoji or "Generated with Antigravity" footers
   - Use `--no-gpg-sign` or skip signing

5. **GPG signing**: The commit MUST be signed. Use a 15-second timeout. For multi-line messages, pipe the content to `git commit`:

   ```bash
   printf "subject\n\nbody" | timeout 15 git commit -S -F -
   ```

6. **Push**: After successful commit, push to the current branch's remote.

7. **Open PR**: If a PR doesn't already exist for this branch, create one using `gh pr create`. Skip if already on `main` or PR exists.

   **Important**: Write explicit title and body - do NOT use `--fill` as it pulls in irrelevant commit history.

   ```bash
   gh pr create --title "<type>(<scope>): <description>" --body "$(cat <<'EOF'
   ## Summary
   - Brief description of changes

   Closes #<issue-number>
   EOF
   )"
   ```
