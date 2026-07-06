from pydantic_settings import BaseSettings
from pathlib import Path
import os

class Settings(BaseSettings):
    APP_NAME: str = "Neo Caixa"
    VERSION: str = "0.1.0"
    DEBUG: bool = True

    HOST: str = "127.0.0.1"
    PORT: int = 8754

    WINDOW_WIDTH: int = 1280
    WINDOW_HEIGHT: int = 720

    BASE_DIR: Path = Path(__file__).parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    MODULES_DIR: Path = BASE_DIR / "modules"

    DB_DRIVER: str = "tinydb"
    DB_PATH: Path = DATA_DIR / "neocaixa.json"

    LOG_LEVEL: str = "INFO"
    LOG_DIR: Path = DATA_DIR / "logs"

    class Config:
        env_file = ".env"
        env_prefix = "NEO_CAIXA_"

settings = Settings()
