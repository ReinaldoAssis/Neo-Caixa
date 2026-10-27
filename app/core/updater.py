"""Auto-update support.

Checks the GitHub releases of the project repository, downloads the
platform-specific asset and applies it by swapping the running
executable / app bundle, then relaunches the application.

Only the Python standard library is used so no extra dependency is
required inside the frozen build.

Important: PyInstaller onefile exports ``_PYI_*`` / ``_MEIPASS*``
environment variables.  If a child process launched by the updater
inherits them, the new bootloader believes the archive was already
extracted and tries to load ``python3xx.dll`` from the old (already
deleted) ``_MEI`` directory.  Every script spawned here runs with a
sanitized environment for that reason.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import ssl
import subprocess
import sys
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
    # Accepts "v1.0.8", "V1.0.8" and the legacy "v.0.1.6" style.
    tag = re.sub(r"^[vV]+[.\s]*", "", tag)
    return tag.strip()


def _parse_version(tag: str) -> tuple:
    numbers = re.findall(r"\d+", _normalize(tag))
    parts = [int(chunk) for chunk in numbers[:3]]
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _clean_env() -> dict:
    """Environment without PyInstaller bootloader variables.

    Onefile's parent/child handshake uses these; inheriting them when
    relaunching the freshly swapped executable makes the new bootloader
    look for python3xx.dll inside the old, deleted ``_MEI`` directory.
    """
    return {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("_PYI_")
        and not key.upper().startswith("_MEIPASS")
    }


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
        "download_size": None,
        "download_sha256": None,
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
            result["download_size"] = asset.get("size")
            digest = asset.get("digest") or ""
            if digest.startswith("sha256:"):
                result["download_sha256"] = digest.split(":", 1)[1]

        result["update_available"] = bool(
            tag and is_newer(tag, __version__) and result["download_url"]
        )
    except Exception as exc:  # network / parsing errors are non fatal
        logger.error(f"Update check failed: {exc}")
        result["error"] = str(exc)
    return result


def download_update(
    download_url: str,
    asset_name: str,
    expected_size: int | None = None,
    sha256: str | None = None,
) -> Path:
    dest = _staging_dir() / asset_name
    part = dest.with_name(dest.name + ".part")
    logger.info(f"Downloading update: {download_url}")
    try:
        if part.exists():
            part.unlink()
        _download(download_url, part)

        size = part.stat().st_size
        if expected_size and size != int(expected_size):
            raise ValueError(
                f"Download incompleto: {size} bytes (esperado {expected_size})."
            )
        if sha256:
            actual = _sha256_file(part)
            if actual.lower() != str(sha256).lower():
                raise ValueError("Hash SHA256 do download nao confere.")

        os.replace(part, dest)
    finally:
        if part.exists():
            try:
                part.unlink()
            except OSError:
                pass

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
    log_path = staging / "apply_update.log"
    target_dir = target.parent

    if key == "windows":
        script = staging / "apply_update.bat"
        content = f"""@echo off
setlocal
set "_PYI_APPLICATION_HOME_DIR="
set "_PYI_PARENT_PROCESS_LEVEL="
set "_PYI_ARCHIVE_FILE="
set "_MEIPASS="
set "_MEIPASS2="
>> "{log_path}" echo [%DATE% %TIME%] Iniciando atualizacao
ping -n 3 127.0.0.1 >nul
del "{target}.old" >nul 2>&1
for %%A in ("{new_path}") do set "ESPERADO=%%~zA"
set /a TENTATIVAS=0
:retry
move /y "{target}" "{target}.old" >nul 2>&1
if not exist "{target}" goto copiar
set /a TENTATIVAS+=1
if %TENTATIVAS% GEQ 30 goto falha
ping -n 2 127.0.0.1 >nul
goto retry
:copiar
copy /y "{new_path}" "{target}" >nul 2>&1
if errorlevel 1 goto rollback
for %%A in ("{target}") do set "COPIADO=%%~zA"
if not "%COPIADO%"=="%ESPERADO%" goto rollback
start "" /d "{target_dir}" "{target}"
del "{target}.old" >nul 2>&1
>> "{log_path}" echo [%DATE% %TIME%] Atualizacao aplicada
del "%~f0" >nul 2>&1
exit /b 0
:rollback
>> "{log_path}" echo [%DATE% %TIME%] Falha ao copiar; restaurando versao anterior
move /y "{target}.old" "{target}" >nul 2>&1
:falha
>> "{log_path}" echo [%DATE% %TIME%] FALHA ao aplicar atualizacao
exit /b 1
"""
        script.write_text(content, encoding="utf-8")
        return script

    # macOS / Linux
    script = staging / "apply_update.sh"
    quoted_target = shlex.quote(str(target))
    quoted_new = shlex.quote(str(new_path))
    quoted_log = shlex.quote(str(log_path))

    if key == "macos" and target.suffix == ".app":
        copy_block = f"""ditto "{new_path}" "{target}" >>{quoted_log} 2>&1"""
    elif new_path.is_dir():
        copy_block = f"""cp -R "{new_path}/." "{target}/" >>{quoted_log} 2>&1"""
    else:
        copy_block = f"""cp -f "{new_path}" "{target}" >>{quoted_log} 2>&1
chmod +x "{target}" >>{quoted_log} 2>&1"""

    if key == "macos" and target.suffix == ".app":
        launch = f"""open "{target}" >>{quoted_log} 2>&1"""
    else:
        launch = f'"{target}" >>{quoted_log} 2>&1 &'

    content = f"""#!/usr/bin/env bash
set -u
unset _PYI_APPLICATION_HOME_DIR _PYI_PARENT_PROCESS_LEVEL _PYI_ARCHIVE_FILE _MEIPASS _MEIPASS2
sleep 2
TARGET={quoted_target}
NEW={quoted_new}
OLD="$TARGET.old"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Iniciando atualizacao" >>{quoted_log}
rm -rf "$OLD"
if ! mv "$TARGET" "$OLD" >>{quoted_log} 2>&1; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] FALHA ao mover versao atual" >>{quoted_log}
  exit 1
fi
if ! (
{copy_block}
); then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Falha ao copiar; restaurando" >>{quoted_log}
  rm -rf "$TARGET"
  mv "$OLD" "$TARGET"
  exit 1
fi
rm -rf "$OLD"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Atualizacao aplicada" >>{quoted_log}
{launch}
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
    if downloaded.suffix.lower() != ".zip":
        return downloaded

    extract_dir = _staging_dir() / "extracted"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True)
    with zipfile.ZipFile(downloaded) as zf:
        zf.extractall(extract_dir)

    if key == "macos":
        apps = sorted(
            (p for p in extract_dir.rglob("*.app") if p.is_dir()),
            key=lambda p: (len(p.parts), p.name),
        )
        if apps:
            return apps[0]

    exes = [p for p in extract_dir.rglob("NeoCaixa*.exe") if p.is_file()]
    if not exes:
        exes = [p for p in extract_dir.rglob("NeoCaixa*") if p.is_file()]
    if exes:
        return max(exes, key=lambda p: p.stat().st_size)
    return extract_dir


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
        env = _clean_env()

        def _run_and_exit():
            time.sleep(1)
            try:
                if _platform_key() == "windows":
                    subprocess.Popen(
                        ["cmd", "/c", str(script)],
                        creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
                        close_fds=True,
                        env=env,
                    )
                else:
                    subprocess.Popen(
                        ["/bin/bash", str(script)],
                        close_fds=True,
                        env=env,
                    )
            except Exception as exc:
                logger.error(f"Failed to start update script: {exc}")
            finally:
                os._exit(0)

        threading.Thread(target=_run_and_exit, daemon=True).start()
        return {"applied": True, "error": None}
    except Exception as exc:
        logger.error(f"Apply update failed: {exc}")
        return {"applied": False, "error": str(exc)}
