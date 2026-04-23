# `gh` Command Cheat Sheet

**Batch status of recent PRs:**
```bash
gh pr list --state all --limit 40 \
  --json number,state,title,mergedAt,closedAt,headRefName
```

**Per-PR detail:**
```bash
gh pr view <num> --json number,state,title,mergedAt,closedAt,body
```

**Find PR by ticket ID or branch:**
```bash
gh pr list --state all --search "<ticket-or-keyword>"
```

**Current branch's open PR:**
```bash
gh pr view --json number,state,title
```

**Ticket detail (GitHub Issues):**
```bash
gh issue view <num>
```
