"""Filesystem locations that differ between running from source and a packaged (PyInstaller) build."""
import os
import sys
from pathlib import Path
from typing import List

APP_NAME = "OS-RPA"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def resource_root() -> Path:
    """Directory holding bundled read-only resources (studio/dist)."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[1]


def studio_dist() -> Path:
    override = os.environ.get("OS_RPA_STUDIO_DIST")
    return Path(override) if override else resource_root() / "studio" / "dist"


def workspace_dir() -> Path:
    """Writable working directory holding workflows/ and data/ (relative paths resolve here)."""
    override = os.environ.get("OS_RPA_HOME")
    if override:
        root = Path(override)
    elif is_frozen():
        root = Path.home() / "Documents" / APP_NAME
    else:
        root = resource_root()
    for sub in ("workflows", "data"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root


def module_cmd(module: str, *args: str) -> List[str]:
    """Command line that runs `python -m module`, also from a frozen executable."""
    if is_frozen():
        return [sys.executable, "--run-module", module, *args]
    return [sys.executable, "-m", module, *args]


def use_system_certificates() -> None:
    """Trust the OS certificate store (corporate TLS-inspecting proxies such as Zscaler)."""
    try:
        import truststore
        truststore.inject_into_ssl()
    except ImportError:
        pass
