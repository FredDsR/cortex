# Security policy

## Reporting a vulnerability

Report privately through
[GitHub security advisories](https://github.com/FredDsR/cortex/security/advisories/new),
or by email to frederico.reckziegel@osf.digital. Please do not open a public
issue for a security problem.

Expect an acknowledgement within a week. This is a personal project, not a
funded one, so treat that as a best effort rather than a guarantee.

## Do not include store contents in a report

`~/.cortex/` holds real workspace, session, task, and knowledge content,
including client and project names. A report that pastes raw store output
leaks that into a public thread.

Reproduce against the synthetic fixtures in `cortex/tests/fixtures/`, or build
a throwaway store under a temporary `HOME`:

```bash
HOME=$(mktemp -d) cortex kb new knowledge demo --workspace demo
```

## Scope

The parts most worth scrutiny:

- `cortex kb ingest` reads files from a codebase you may not control, and the
  text it extracts can reach `description:` frontmatter.
- `cortex inject` emits that frontmatter into an agent's context at session
  start. It is off by default and requires two independent opt-ins.
- `cortex sync` commits and pushes the store to a remote you configure.
- `cortex viz serve --edit` writes to the store from a localhost browser
  session.
