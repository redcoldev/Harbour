# GitHub conflicts + "main-only" workflow (quick guide)

This project should use a **single branch** workflow:
- `main` only
- no long-lived feature branches
- small, frequent commits

## Why you saw 8 conflicts
Conflicts happen when two versions changed the same lines differently:
- **Current change** = what is already in the target branch (`main`) on GitHub.
- **Incoming change** = what your PR/merge is trying to add.

If both touched the same area, GitHub asks you to choose or manually combine.

## What to pick: Current vs Incoming
Use this rule of thumb:

1. **Pick Current change** when the code already in `main` is newer/correct and incoming is old.
2. **Pick Incoming change** when your incoming edit is the intended new behavior.
3. **Pick both (manual merge)** when each side has useful parts.

Never blindly click one option for all files.

## Safe conflict workflow (recommended)

1. In GitHub conflict editor, resolve one file at a time.
2. After each file, ensure there are no conflict markers left:
   - `<<<<<<<`
   - `=======`
   - `>>>>>>>`
3. Run app/tests locally before finalizing merge.

## How to keep it truly main-only on GitHub

In GitHub repo settings:
1. **Default branch**: `main`
2. **Branch protection** on `main`:
   - require up-to-date branch before merge
   - require status checks (if you add CI)
3. **Disable merge commits** (optional but useful)
4. Prefer **Rebase and merge** or **Squash and merge** only
5. Delete PR branches automatically after merge

## Local commands for a clean main-only flow

```bash
git checkout main
git pull --rebase
# make edits
git add .
git commit -m "small focused change"
git push origin main
```

If a rebase conflict appears:

```bash
git status
# edit conflicted files
git add <file>
git rebase --continue
```

## Recovery if history got messy

```bash
git fetch origin
git checkout main
git reset --hard origin/main
```

(Use hard reset only if you are sure local unpushed work can be discarded.)
