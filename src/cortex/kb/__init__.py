"""kb commands (new / update / index) for the cortex engine.

Ports the former skills/cortex-kb bash `work-kb` bin onto the shared core
(cortex.frontmatter + cortex.store). Behavior-preserving: same frontmatter
bytes, exit codes, and messages.

The split here is by feature rather than by the pure/presentation seam #57
opens with, because that seam was not this module's problem. Eight modules
already imported `kb`, and they reached for private names (`_home`,
`_md_escape`, `_more_notice`, `_SLUG`) across the boundary. What the file
actually held was three things:

- `common.py`  the shared base the rest of the package depends on: paths,
               `--max` parsing, the sync hook, the `type` vocabulary, and the
               two markdown helpers. Stdlib plus `cortex.errors`, nothing else,
               so anything may import it.
- `index.py`   the derived catalog: one read of a kb directory, rendered flat
               for stdout or as an OKF §8 group listing for the index file.
- `cli.py`     argparse in, terminal out. `kb new`, `kb update`, `kb index`.

The private names that used to cross the boundary are public here, which is the
point: importing a private name across a module boundary is the smell the split
exists to remove.
"""
