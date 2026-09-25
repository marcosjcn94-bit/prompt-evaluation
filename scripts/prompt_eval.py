"""Repository-local launcher; no package installation or third-party deps needed."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from prompt_eval.cli import main

raise SystemExit(main())
