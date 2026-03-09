from __future__ import annotations

import os
from pathlib import Path

STORAGE_ROOT = Path(os.environ.get("PVM_STORAGE_ROOT", str(Path.home() / ".pvm-server" / "projects")))
DB_PATH = Path(os.environ.get("PVM_DB_PATH", str(Path.home() / ".pvm-server" / "pvm.db")))

STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
