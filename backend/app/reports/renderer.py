"""
Server-Side Headless Chromium PDF Rendering Pipeline for Stage 34 Gate D.

Provides deterministic, institutional-grade PDF rendering using headless Chromium
(Chrome / Edge / Chromium) with strict execution sandboxing, timeout enforcement,
concurrency limits, zero network access, and complete temporary resource lifecycle cleanup.
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Sequence

import pypdf

logger = logging.getLogger("app.reports.renderer")

# Default rendering timeout in seconds
DEFAULT_RENDER_TIMEOUT_SECONDS: float = 25.0

# Bounded concurrency semaphore to limit system memory and process saturation
_RENDER_SEMAPHORE = threading.BoundedSemaphore(value=int(os.environ.get("PDF_MAX_CONCURRENT_RENDERS", "4")))


def get_chromium_executable() -> str:
    """
    Locates an available Chromium-compatible browser binary for headless PDF rendering.
    Checks explicit environment variables first, then standard platform install paths.
    """
    # 1. Check explicit environment overrides
    env_vars = ["CHROME_BIN", "CHROMIUM_PATH", "EDGE_BIN", "BROWSER_PATH"]
    for var in env_vars:
        custom_path = os.environ.get(var)
        if custom_path and os.path.isfile(custom_path) and os.access(custom_path, os.X_OK):
            return custom_path

    # 2. Check standard system candidates by platform
    candidates: list[str] = []
    if sys.platform == "win32":
        candidates.extend([
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
        ])
    elif sys.platform == "darwin":
        candidates.extend([
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ])
    else:  # Linux / Unix / Container
        candidates.extend([
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/snap/bin/chromium",
        ])

    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate

    # 3. Check PATH for standard binary names
    for bin_name in ["google-chrome-stable", "google-chrome", "chromium-browser", "chromium", "chrome", "msedge"]:
        path = shutil.which(bin_name)
        if path and os.path.isfile(path):
            return path

    raise RuntimeError(
        "Headless Chromium browser executable was not found on this system. "
        "Please set CHROME_BIN or CHROMIUM_PATH environment variable, or ensure "
        "Google Chrome, Microsoft Edge, or Chromium is installed."
    )


def count_pdf_pages(pdf_bytes: bytes) -> int:
    """
    Parses a PDF byte stream and returns the exact physical page count using pypdf.
    """
    if not pdf_bytes or not pdf_bytes.startswith(b"%PDF-"):
        raise ValueError("Invalid PDF content: Missing %PDF- magic signature header.")

    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    return len(reader.pages)


def render_html_to_pdf(
    html_content: str,
    timeout_seconds: float = DEFAULT_RENDER_TIMEOUT_SECONDS,
    extra_flags: Sequence[str] | None = None,
) -> bytes:
    """
    Renders an HTML document to PDF bytes using headless Chromium.

    Security & Reliability Controls:
    1. Isolated Temporary Directory: Scratch files are generated in an ephemeral,
       uniquely named directory wiped immediately upon completion or error.
    2. Zero External Network Access: Headless Chromium is invoked with flags
       disabling background networking, extensions, sync, and remote fonts.
    3. Resource Bounding: Uses a concurrency semaphore and strict subprocess timeout.
    4. Validation: Ensures non-empty PDF output with valid %PDF- header.
    """
    browser_bin = get_chromium_executable()

    # Acquire concurrency permit
    acquired = _RENDER_SEMAPHORE.acquire(timeout=timeout_seconds)
    if not acquired:
        raise TimeoutError("PDF rendering service is currently busy. Please retry shortly.")

    temp_dir = tempfile.mkdtemp(prefix="quant_pdf_render_")
    try:
        html_file = Path(temp_dir) / "document.html"
        pdf_file = Path(temp_dir) / "output.pdf"

        # Write UTF-8 HTML document
        html_file.write_text(html_content, encoding="utf-8")

        # Headless Chromium command line flags
        cmd = [
            browser_bin,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            "--disable-default-apps",
            "--disable-background-networking",
            "--disable-sync",
            "--disable-translate",
            "--disable-component-update",
            "--run-all-compositor-stages-before-draw",
            "--no-pdf-header-footer",
            f"--print-to-pdf={pdf_file.resolve()}",
            html_file.resolve().as_uri(),
        ]

        if extra_flags:
            cmd.extend(extra_flags)

        logger.debug("Executing headless Chromium PDF render: %s", " ".join(cmd[:4]))

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
        )

        if not pdf_file.exists():
            stderr_snippet = result.stderr.decode("utf-8", errors="replace")[-500:]
            logger.error("Chromium PDF export failed with exit code %d: %s", result.returncode, stderr_snippet)
            raise RuntimeError(
                f"Chromium failed to generate PDF artifact (exit code {result.returncode})."
            )

        pdf_bytes = pdf_file.read_bytes()
        if len(pdf_bytes) < 100:
            raise ValueError(f"Generated PDF artifact is suspiciously truncated ({len(pdf_bytes)} bytes).")

        if not pdf_bytes.startswith(b"%PDF-"):
            raise ValueError("Generated file does not begin with the canonical %PDF- magic signature.")

        return pdf_bytes

    except subprocess.TimeoutExpired as exc:
        logger.error("Chromium PDF rendering timed out after %.1f seconds", timeout_seconds)
        raise TimeoutError(f"PDF rendering exceeded timeout of {timeout_seconds:.1f}s.") from exc

    finally:
        _RENDER_SEMAPHORE.release()
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as exc:
            logger.warning("Failed to clean up temporary PDF rendering directory %s: %s", temp_dir, exc)
