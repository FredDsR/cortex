"""BM25 keyword search over a parsed World, fused with RRF.

`search` powers `cortex query search <terms>`: the headless counterpart to the
viz's client-side MiniSearch. Before this, the only search in the family ran in
a browser, so an agent could not answer "do we already know something about X"
without a human opening a tab. `cortex kb index` is a table of contents over
`description:` fields, which answers a different question.

`related` powers `cortex query related <slug>`: the same ranking with a
document as the query instead of terms, so link discovery is deterministic
rather than a per-run judgment call about which words to search for.

The module boundaries are the three layers that were interleaved in one file,
only the last of which the single file marked with a section comment:

- `index.py`  Okapi BM25 and Reciprocal Rank Fusion over opaque string keys.
              Stdlib only, and it knows nothing about cortex: no `Doc`, no
              `World`, no store. A scoring change touches this file alone.
- `rank.py`   a `World` in, a `SearchResult` out. Which docs are indexable,
              which fields are weighted, and what a snippet is.
- `cli.py`    argparse in, terminal out. The only place this package prints.
"""
