"""Runs inspector sessions in a child process for the API server (one at a time, cancellable)."""
import json
import subprocess
import sys
import threading
from typing import Any, Dict, List, Optional

from os_rpa.paths import module_cmd


class InspectorBusyError(RuntimeError):
    pass


class InspectorService:
    def __init__(self):
        self._lock = threading.Lock()
        self._proc: Optional[subprocess.Popen] = None
        self._cancelled = False

    @property
    def busy(self) -> bool:
        return self._lock.locked()

    def pick(
        self, target: str, url: str = "", channel: str = "auto", timeout: float = 120,
        source: str = "new", endpoint: str = "",
    ) -> Dict[str, Any]:
        args = [
            "pick", "--target", target, "--timeout", str(timeout), "--channel", channel or "auto",
            "--source", source or "new",
        ]
        if url:
            args += ["--url", url]
        if endpoint:
            args += ["--endpoint", endpoint]
        return self._run(args, timeout)

    def validate(
        self, target: str, params: Dict[str, Any], url: str = "", channel: str = "auto", timeout: float = 10,
        endpoint: str = "",
    ) -> Dict[str, Any]:
        args = [
            "validate", "--target", target, "--timeout", str(timeout), "--channel", channel or "auto",
            "--params", json.dumps(params or {}),
        ]
        if url:
            args += ["--url", url]
        if endpoint:
            args += ["--endpoint", endpoint]
        return self._run(args, timeout)

    def cancel(self) -> bool:
        proc = self._proc
        if proc is None or proc.poll() is not None:
            return False
        self._cancelled = True
        proc.kill()
        return True

    def _run(self, args: List[str], timeout: float) -> Dict[str, Any]:
        if not self._lock.acquire(blocking=False):
            raise InspectorBusyError("Another inspection is already in progress")
        try:
            self._cancelled = False
            self._proc = subprocess.Popen(
                module_cmd("os_rpa.inspector", *args),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0,
            )
            try:
                # Browser start-up and page load come on top of the user's selection time
                out, err = self._proc.communicate(timeout=timeout + 60)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.communicate()
                return {"ok": False, "error": "Inspector timed out"}
            if self._cancelled:
                return {"ok": False, "cancelled": True, "error": "Selection cancelled"}
            return self._parse(out, err)
        finally:
            self._proc = None
            self._lock.release()

    @staticmethod
    def _parse(out: str, err: str) -> Dict[str, Any]:
        for line in reversed((out or "").splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    return json.loads(line)
                except ValueError:
                    break
        detail = (err or out or "").strip().splitlines()
        return {"ok": False, "error": detail[-1] if detail else "Inspector exited without a result"}


inspector = InspectorService()
