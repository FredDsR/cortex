import sys
from pathlib import Path

# Ensure the repo root (parent of the cortex package) is importable so
# `import cortex.frontmatter` works regardless of pytest's invocation dir.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
