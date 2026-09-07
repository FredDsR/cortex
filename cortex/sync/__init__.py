"""cortex sync: replicate ~/.cortex to a private git remote.

The odd one out among #57's modules, and the audit that re-scoped that issue
says why: 62% of the flat file's body printed and only 48 lines were pure, so
"lift the pure half out" had nothing to lift. What it does have is three
layers, and the file already marked two of them with section comments:

- `repo.py`   the store's git remote: plumbing, `is_enabled`, `push`, `pull`,
              and the stderr reporting all three share. Returns exit codes.
- `setup.py`  first-run bootstrap: clone, create, or opt out. Holds the only
              interactive prompt in the engine, which is the category none of
              the other split packages had.
- `cli.py`    argparse in, exit code out.

Every function here reports progress and failures to stderr as it goes, rather
than returning something for a caller to print. That is deliberate: a sync is a
sequence of git operations that can each fail differently, and a caller holding
one exit code cannot say which.
"""
