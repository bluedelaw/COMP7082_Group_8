# server.py
from __future__ import annotations

import os
import sys
import threading
import time
import webbrowser
from urllib.parse import urlunparse

import uvicorn

import config as cfg
from backend.logging_setup import init_logging
from backend.app import create_app as create_fastapi_app

# NEW: import gradio + your Gradio Blocks factory
import gradio as gr
from ui_app import create_app as create_gradio_blocks
from fastapi.responses import RedirectResponse

def build_app_with_ui():
    init_logging(cfg.LOG_LEVEL)
    fastapi_app = create_fastapi_app()

    os.environ["GRADIO_USE_CDN"] = "true" if cfg.GRADIO_USE_CDN else "false"
    os.environ["GRADIO_ANALYTICS_ENABLED"] = "true" if cfg.GRADIO_ANALYTICS_ENABLED else "false"

    blocks = create_gradio_blocks()
    mount_path = cfg.GRADIO_MOUNT_PATH.rstrip("/") or "/"
    gr.mount_gradio_app(app=fastapi_app, blocks=blocks, path=mount_path)

    if mount_path != "/":
        @fastapi_app.get("/")
        def _root_redirect():
            return RedirectResponse(url=mount_path, status_code=307)
    return fastapi_app


def _browser_url(host: str, port: int, path: str) -> str:
    """
    Build a http:// URL for the local browser. If the server binds to 0.0.0.0,
    use 127.0.0.1 for the client-side URL.
    """
    client_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    netloc = f"{client_host}:{port}"
    # Ensure leading slash on path
    p = path if path.startswith("/") else f"/{path}"
    return urlunparse(("http", netloc, p, "", "", ""))


def _open_browser_later(url: str, delay: float) -> None:
    def _worker():
        # small stagger to give uvicorn time to bind
        time.sleep(max(0.0, delay))
        try:
            webbrowser.open(url, new=2)  # new tab if possible
        except Exception:
            pass
    t = threading.Thread(target=_worker, name="OpenBrowser", daemon=True)
    t.start()


def main() -> int:
    init_logging(cfg.LOG_LEVEL)

    # Build FastAPI
    fastapi_app = create_fastapi_app()

    # Ensure Gradio behavior is controlled via config (no user env required)
    os.environ["GRADIO_USE_CDN"] = "true" if cfg.GRADIO_USE_CDN else "false"
    os.environ["GRADIO_ANALYTICS_ENABLED"] = "true" if cfg.GRADIO_ANALYTICS_ENABLED else "false"

    # Build Gradio Blocks (no launch here; we mount it)
    blocks = create_gradio_blocks()

    # Mount Gradio at configured path (default "/ui")
    mount_path = cfg.GRADIO_MOUNT_PATH.rstrip("/") or "/"
    gr.mount_gradio_app(app=fastapi_app, blocks=blocks, path=mount_path)

    # Redirect "/" to the UI if UI is not at root
    if mount_path != "/":
        @fastapi_app.get("/")
        def _root_redirect():
            return RedirectResponse(url=mount_path, status_code=307)

    # Decide reload flag by platform
    if os.name == "nt":
        reload_flag = cfg.UVICORN_RELOAD_WINDOWS
    else:
        reload_flag = cfg.UVICORN_RELOAD_OTHERS

    # Host/port from config
    host = cfg.SERVER_HOST
    port = int(cfg.SERVER_PORT)

    # Auto-open UI if enabled
    if cfg.GRADIO_AUTO_OPEN:
        url = _browser_url(host, port, mount_path)
        _open_browser_later(url, delay=cfg.GRADIO_OPEN_DELAY_SEC)

    try:
        if reload_flag:
            uvicorn.run(
                "server:build_app_with_ui",   # <- use our factory, not backend.main:app
                host=host,
                port=port,
                reload=True,
                log_level=cfg.LOG_LEVEL,
                factory=True,                # <- IMPORTANT
                access_log=cfg.UVICORN_ACCESS_LOG,  # <<< kills 200 OK spam when False
            )
        else:
            uvicorn.run(
                app=fastapi_app,
                host=host,
                port=port,
                reload=False,
                log_level=cfg.LOG_LEVEL,
                access_log=cfg.UVICORN_ACCESS_LOG,  # <<< kills 200 OK spam when False
            )
        return 0
    except KeyboardInterrupt:
        return 0

if __name__ == "__main__":
    sys.exit(main())
