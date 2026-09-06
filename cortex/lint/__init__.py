"""cortex kb lint: a health check over a workspace's docs.

Karpathy's llm-wiki names lint as a first-class operation alongside ingest and
query. cortex had the other two. The gap this closes is that a knowledge base
accumulates statements that were true when written and quietly stopped being
true, and nothing noticed: this repo's README advertised `cortex viz --watch`
long after the flag was deleted, and two archived tasks described symbols in a
file that no longer existed.

The split mirrors `cortex kb ingest`. Everything a machine can decide is a
finding, printed one line per finding. Everything needing judgment goes to an
agent worklist and is phrased as a candidate, never an assertion.

Report-only unless `--fix`, which is deliberately narrow: it repairs a broken
reference ONLY when the target it names exists elsewhere under an unambiguous
address, so the edit changes an address and never a claim. It does not delete
dangling links (a link to a doc nobody has written yet is authoring intent, and
it is what the viz renders as a ghost node) and it does not touch `updated`
(bumping it would erase the very signal the stale check reads).

The module boundaries are the three layers that were interleaved in one file:

- `checks.py`  a `World` in, findings out. No IO but reading a derived index.
- `fix.py`     the narrow `--fix` rewriter, the only writer here.
- `cli.py`     argparse in, terminal out. The only place this package prints.
"""
