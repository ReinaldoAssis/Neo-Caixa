import os
import sys
import threading
import uvicorn
import webview
from pathlib import Path

from app.core.config import settings
from app.api import create_app

def get_frontend_path() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS) / "frontend" / "dist"
    return Path(__file__).parent / "frontend" / "dist"

def run_api():
    app = create_app()
    uvicorn.run(app, host=settings.HOST, port=settings.PORT, log_level="info")

def main():
    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()

    window = webview.create_window(
        title="Neo Caixa",
        url=f"http://{settings.HOST}:{settings.PORT}",
        width=settings.WINDOW_WIDTH,
        height=settings.WINDOW_HEIGHT,
        min_size=(800, 600),
        confirm_close=True,
    )
    webview.start(debug=settings.DEBUG)

if __name__ == "__main__":
    main()
