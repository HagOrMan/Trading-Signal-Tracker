"""Shared pytest fixtures + path bootstrapping."""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure `import src.foo` resolves regardless of cwd.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
