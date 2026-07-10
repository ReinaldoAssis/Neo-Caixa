from pydantic_settings import BaseSettings
from pathlib import Path
import os
import sys

from app.version import __version__


def _user_data_dir() -> Path:
    app = "NeoCaixa"
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / app


def _resolve_data_dir() -> Path:
    if getattr(sys, "frozen", False):
        return _user_data_dir()
    return Path(__file__).parent.parent / "data"


_DATA_DIR = _resolve_data_dir()

class Settings(BaseSettings):
    APP_NAME: str = "Neo Caixa"
    VERSION: str = __version__
    DEBUG: bool = False

    GITHUB_REPO: str = "ReinaldoAssis/Neo-Caixa"

    HOST: str = "127.0.0.1"
    PORT: int = 8754

    WINDOW_WIDTH: int = 1280
    WINDOW_HEIGHT: int = 720

    BASE_DIR: Path = Path(__file__).parent.parent
    DATA_DIR: Path = _DATA_DIR
    MODULES_DIR: Path = BASE_DIR / "modules"

    DB_DRIVER: str = "tinydb"
    DB_PATH: Path = _DATA_DIR / "neocaixa.json"

    LOG_LEVEL: str = "INFO"
    LOG_DIR: Path = _DATA_DIR / "logs"

    class Config:
        env_file = ".env"
        env_prefix = "NEO_CAIXA_"

settings = Settings()

settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
settings.LOG_DIR.mkdir(parents=True, exist_ok=True)

