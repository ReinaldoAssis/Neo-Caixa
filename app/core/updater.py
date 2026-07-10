"""Auto-update support.

Checks the GitHub releases of the project repository, downloads the
platform-specific asset and applies it by swapping the running
executable / app bundle, then relaunches the application.

Only the Python standard library is used so no extra dependency is
required inside the frozen build.
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

from app.core.logger import logger
from app.version import __version__


GITHUB_API = "https://api.github.com"
USER_AGENT = "NeoCaixa-Updater"


# ─── Version helpers ─────────────────────────────────────────────

def _normalize(tag: str) -> str:
    tag = (tag or "").strip()
    if tag.lower().startswith("v"):
        tag = tag[1:]
    return tag


def _parse_version(tag: str) -> tuple:
    tag = _normalize(tag)
    parts = []
    for chunk in tag.split("."):
        num = ""
        for ch in chunk:
            if ch.isdigit():
                num += ch
            else:
                break
        parts.append(int(num) if num else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def is_newer(remote: str, local: str) -> bool:
    return _parse_version(remote) > _parse_version(local)


# ─── Platform detection ──────────────────────────────────────────

def _platform_key() -> str:
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def _asset_matches(name: str) -> bool:
    """Return True when the asset name matches the current platform."""
    name = name.lower()
    key = _platform_key()
    if key == "windows":
        return name.endswith(".exe") or ("win" in name and name.endswith(".zip"))
    if key == "macos":
        return "mac" in name or "darwin" in name or "osx" in name
    return "linux" in name


# ─── HTTP helpers (stdlib) ───────────────────────────────────────

def _ssl_context() -> ssl.SSLContext:
    try:
        return ssl.create_default_context()
    except Exception:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx


def _get_json(url: str, timeout: int = 15) -> dict:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"})
    with urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _download(url: str, dest: Path, timeout: int = 300) -> Path:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/octet-stream"})
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(req, timeout=timeout, context=_ssl_context()) as resp, open(dest, "wb") as out:
        shutil.copyfileobj(resp, out)
    return dest


# ─── Public API ──────────────────────────────────────────────────

def _staging_dir() -> Path:
    from app.core.config import settings
    d = settings.DATA_DIR / "updates"
    d.mkdir(parents=True, exist_ok=True)
    return d


def check_for_update(repo: str) -> dict:
    """Query the latest GitHub release and report whether an update exists."""
    result = {
        "current_version": __version__,
        "latest_version": None,
        "update_available": False,
        "download_url": None,
        "asset_name": None,
        "release_notes": "",
        "release_url": None,
        "error": None,
    }
    try:
        data = _get_json(f"{GITHUB_API}/repos/{repo}/releases/latest")
        tag = data.get("tag_name") or data.get("name") or ""
        result["latest_version"] = _normalize(tag)
        result["release_notes"] = data.get("body", "") or ""
        result["release_url"] = data.get("html_url")

        asset = None
        for a in data.get("assets", []):
            if _asset_matches(a.get("name", "")):
                asset = a
                break
        if asset:
            result["download_url"] = asset.get("browser_download_url")
            result["asset_name"] = asset.get("name")

        result["update_available"] = bool(
            tag and is_newer(tag, __version__) and result["download_url"]
        )
    except Exception as exc:  # network / parsing errors are non fatal
        logger.error(f"Update check failed: {exc}")
        result["error"] = str(exc)
    return result


def download_update(download_url: str, asset_name: str) -> Path:
    dest = _staging_dir() / asset_name
    if dest.exists():
        dest.unlink()
    logger.info(f"Downloading update: {download_url}")
    _download(download_url, dest)
    logger.info(f"Update downloaded to {dest}")
    return dest


def _current_target() -> Path:
    """Path of the running executable / bundle to be replaced."""
    exe = Path(sys.executable)
    if sys.platform == "darwin":
        # sys.executable -> NeoCaixa.app/Contents/MacOS/NeoCaixa
        for parent in exe.parents:
            if parent.suffix == ".app":
                return parent
    return exe


def _write_apply_script(new_path: Path, target: Path) -> Path:
    """Create an OS specific script that swaps files and relaunches."""
    staging = _staging_dir()
    key = _platform_key()

    if key == "windows":
        script = staging / "apply_update.bat"
        # new_path is the downloaded .exe; target is current .exe
        content = f"""@echo off
timeout /t 2 /nobreak >nul
:retry
copy /y "{new_path}" "{target}" >nul 2>&1
if errorlevel 1 (
  timeout /t 1 /nobreak >nul
  goto retry
)
start "" "{target}"
del "%~f0"
"""
        script.write_text(content, encoding="utf-8")
        return script

    # macOS / Linux
    script = staging / "apply_update.sh"
    if key == "macos" and target.suffix == ".app":
        # new_path is a directory (extracted .app) or a zip already extracted
        content = f"""#!/usr/bin/env bash
sleep 2
rm -rf "{target}"
cp -R "{new_path}" "{target}"
open "{target}"
rm -f "$0"
"""
    else:
        content = f"""#!/usr/bin/env bash
sleep 2
cp "{new_path}" "{target}"
chmod +x "{target}"
"{target}" &
rm -f "$0"
"""
    script.write_text(content, encoding="utf-8")
    os.chmod(script, 0o755)
    return script


def _prepare_new_artifact(downloaded: Path) -> Path:
    """Return the path to copy over the target.

    For macOS the asset is a zip containing NeoCaixa.app; extract it.
    For Windows/Linux the asset is the binary itself (or a zip with it).
    """
    key = _platform_key()
    if downloaded.suffix.lower() == ".zip":
        extract_dir = _staging_dir() / "extracted"
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
        extract_dir.mkdir(parents=True)
        with zipfile.ZipFile(downloaded) as zf:
            zf.extractall(extract_dir)
        if key == "macos":
            for p in extract_dir.rglob("*.app"):
                return p
        # windows/linux: find the executable
        for p in extract_dir.rglob("NeoCaixa*"):
            if p.is_file():
                return p
        return extract_dir
    return downloaded


def apply_update(downloaded_path: str) -> dict:
    """Swap the running app with the downloaded artifact and relaunch."""
    if not getattr(sys, "frozen", False):
        return {"applied": False, "error": "Auto-update so funciona no app compilado."}

    downloaded = Path(downloaded_path)
    if not downloaded.exists():
        return {"applied": False, "error": "Arquivo de atualizacao nao encontrado."}

    try:
        artifact = _prepare_new_artifact(downloaded)
        target = _current_target()
        script = _write_apply_script(artifact, target)

        def _run_and_exit():
            time.sleep(1)
            if _platform_key() == "windows":
                subprocess.Popen(
                    ["cmd", "/c", str(script)],
                    creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
                    close_fds=True,
                )
            else:
                subprocess.Popen(["/bin/bash", str(script)], close_fds=True)
            os._exit(0)

        threading.Thread(target=_run_and_exit, daemon=True).start()
        return {"applied": True, "error": None}
    except Exception as exc:
        logger.error(f"Apply update failed: {exc}")
        return {"applied": False, "error": str(exc)}
