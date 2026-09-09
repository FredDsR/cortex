"""cortex inject: strictly opt-in, off-by-default session-start injection.

The flat module already named its own three pieces in its docstring, which is
the same tell #57 reads off a section comment. They are now three files:

- `render.py`    the harness-agnostic payload, and the per-workspace sentinel
                 that decides whether there is one. The gate lives beside the
                 renderer because the renderer is its only non-CLI reader.
- `adapters.py`  the per-harness registry: stdout envelope plus hook wiring.
                 Adding a harness touches this file alone.
- `cli.py`       argparse in, terminal out. The only place this package prints.

`cortex inject here` never errors to the user: any unresolved gate or exception
yields exit 0 with empty stdout. See
docs/superpowers/specs/2026-07-14-optin-sessionstart-inject-design.md.
"""
