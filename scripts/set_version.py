"""Write app/version.py from the VERSION environment variable.

Used by the GitHub Actions workflow so every push gets a unique,
monotonically increasing version (1.0.<run_number>).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

version = (os.environ.get("VERSION") or "").strip()
if not re.fullmatch(r"\d+\.\d+\.\d+", version):
    raise SystemExit(f"VERSION invalida: {version!r} (esperado MAJOR.MINOR.PATCH)")

path = Path(__file__).resolve().parent.parent / "app" / "version.py"
path.write_text(f'__version__ = "{version}"\n', encoding="utf-8")
print(f"app/version.py -> {version}")
