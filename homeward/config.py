"""Settings. Reads .env.local files without copying secrets into the repo."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


# Project-local file first, then the shared hackathon file one folder up.
_load_env_file(ROOT / ".env.local")
_load_env_file(ROOT.parent / ".env.local")

MODEL = os.environ.get("HOMEWARD_MODEL", "claude-opus-5-5")
PHOTON_API_KEY = os.environ.get("PHOTON_API_KEY", "")
PHOTON_PROJECT_ID = os.environ.get("PHOTON_PROJECT_ID", "")
PHOTON_AGENT_HANDLE = os.environ.get("PHOTON_AGENT_HANDLE", "")
USE_PHOTON = bool(PHOTON_API_KEY and PHOTON_PROJECT_ID)
DB_PATH = Path(os.environ.get("HOMEWARD_DB", ROOT / "data" / "homeward.db"))
POLL_SECONDS = float(os.environ.get("HOMEWARD_POLL_SECONDS", "2"))
