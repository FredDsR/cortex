# Workspace Slug Resolution

The workspace slug identifies a logical project — a git repo, a directory, or a manually registered area. All `~/.work/workspaces/<slug>/` paths depend on this resolution.

## Resolution order (implemented in `scripts/resolve_workspace.sh`)

1. **Git remote.** `git -C <cwd> remote get-url origin` → parse `owner/repo` → slug `owner-repo`. Stable across clones of the same repo.
2. **`.meta` registry match.** Scan `~/.work/workspaces/*/.meta`; if any entry's `cwd:` field equals the current absolute CWD, use that workspace's directory name.
3. **Basename fallback.** `basename "$cwd"`.
4. **Collision check.** If the basename already exists as a registered workspace with a different CWD, the script exits 2. The skill prompts the user to (a) disambiguate to `<parent>-<basename>`, (b) reuse the existing workspace, or (c) enter a custom slug. The resolution is written to `.meta` and never asked again for this CWD.

## `.meta` fields

```
cwd: /home/fred/Workspace/osf/OPTX-AI
remote: git@github.com:psgequity/OPTX-AI.git
source: git-remote
updated: 2026-04-20
```

## Collision prompt (wording the skill uses)

> Slug `<basename>` is already registered to `<existing-cwd>`. Options:
> 1. Disambiguate this workspace to `<parent>-<basename>`
> 2. Reuse the existing workspace (intentional share across clones)
> 3. Enter a custom slug

Write the resolution into the new workspace's `.meta`.
