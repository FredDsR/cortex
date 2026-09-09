"""cortex kb ingest: extract documentable artifacts from a codebase into
knowledge docs. Deterministic OpenAPI + SQL DDL extraction; fuzzy sources go to
an agent worklist. Moved from the former lib/ingest_extract.py; the extractor is
now called in-process (concept dicts, no wire format), collecting diagnostics
into a warnings list instead of stderr.

The module boundaries are the three layers the single file interleaved, and the
two it already marked with section comments:

- `extract.py`  bytes in, concept dicts out. Reads files, writes none.
- `scan.py`     one walk of a source tree: which files are candidates for which
                half, deterministic extraction or the agent worklist.
- `cli.py`      argparse in, terminal out. The only place this package prints,
                and the only place it writes a doc.
"""
