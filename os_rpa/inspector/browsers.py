"""Discovery of already-open browsers the inspector can attach to over CDP (Chrome DevTools Protocol).

Browsers launched by `web.open_browser` register their local debug port here; browsers the user
started with `--remote-debugging-port=92xx` are found by probing the common ports.
"""
import json
import os
import socket
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

COMMON_PORTS = range(9222, 9230)
_lock = threading.Lock()


def registry_file() -> Path:
    return Path("data") / "browser_sessions.json"


def inspectable_browsers_enabled() -> bool:
    """Workflow browsers expose a 127.0.0.1-only debug port unless OS_RPA_INSPECTABLE_BROWSER=0."""
    return os.environ.get("OS_RPA_INSPECTABLE_BROWSER", "1").strip().lower() not in ("0", "false", "no")


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _read() -> List[Dict[str, Any]]:
    try:
        data = json.loads(registry_file().read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _write(entries: List[Dict[str, Any]]):
    path = registry_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def register(port: int, browser: str, label: str = "Workflow browser"):
    with _lock:
        entries = [e for e in _read() if e.get("port") != port]
        entries.append({"port": port, "browser": browser, "label": label, "pid": os.getpid(), "started": time.time()})
        _write(entries)


def unregister(port: Optional[int]):
    if not port:
        return
    with _lock:
        entries = _read()
        kept = [e for e in entries if e.get("port") != port]
        if len(kept) != len(entries):
            _write(kept)


def _get_json(url: str, timeout: float) -> Any:
    # Never route localhost through a corporate proxy (HTTP(S)_PROXY / Zscaler)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def probe(port: int, timeout: float = 0.4) -> Optional[Dict[str, Any]]:
    """Returns {endpoint, browser, pages} when a CDP endpoint answers on the port."""
    endpoint = f"http://127.0.0.1:{port}"
    try:
        version = _get_json(f"{endpoint}/json/version", timeout)
        targets = _get_json(f"{endpoint}/json/list", timeout)
    except Exception:
        return None
    pages = [
        {"title": t.get("title", ""), "url": t.get("url", "")}
        for t in targets
        if t.get("type") == "page" and not str(t.get("url", "")).startswith(("devtools://", "edge://", "chrome://"))
    ]
    return {"endpoint": endpoint, "port": port, "browser": version.get("Browser", ""), "pages": pages}


def list_instances() -> List[Dict[str, Any]]:
    """Open browsers that can be inspected: registered workflow browsers first, then common debug ports."""
    registered = {e["port"]: e for e in _read() if isinstance(e.get("port"), int)}
    found: List[Dict[str, Any]] = []
    dead: List[int] = []
    for port in list(registered) + [p for p in COMMON_PORTS if p not in registered]:
        info = probe(port)
        if info is None:
            if port in registered:
                dead.append(port)
            continue
        entry = registered.get(port)
        info["source"] = "workflow" if entry else "debug-port"
        info["label"] = entry.get("label", "Workflow browser") if entry else f"Browser on port {port}"
        found.append(info)
    for port in dead:
        unregister(port)
    return found
