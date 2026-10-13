import asyncio
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional
import websockets
from os_rpa.agent.forensics import capture_desktop_screenshot
from os_rpa.paths import module_cmd


class BotAgent:
    """Unattended Bot Daemon that connects via outbound WebSocket to the Orchestrator,
    executes workflows in sandboxed subprocesses, and streams real-time telemetry."""

    def __init__(
        self,
        server_ws_url: str = "ws://localhost:8000/ws/agent",
        bot_id: Optional[str] = None,
        token: Optional[str] = None,
        heartbeat_interval: float = 5.0,
    ):
        self.server_ws_url = server_ws_url
        self.bot_id = bot_id or f"bot-{platform.node().lower()}"
        self.token = token or "default-token"
        self.heartbeat_interval = heartbeat_interval
        self.status = "IDLE"
        self.current_job_id: Optional[str] = None
        self._stop_requested = False

    def get_system_info(self) -> dict:
        return {
            "hostname": platform.node(),
            "os": platform.platform(),
            "username": os.getlogin() if hasattr(os, "getlogin") else os.getenv("USERNAME", "unknown"),
            "python_version": platform.python_version(),
        }

    async def start(self):
        """Starts the daemon with auto-reconnection loop."""
        print(f"[*] Starting Bot Runner Daemon (Bot ID: {self.bot_id})")
        print(f"[*] Connecting to Orchestrator at: {self.server_ws_url}")

        while not self._stop_requested:
            try:
                url = f"{self.server_ws_url}?bot_id={self.bot_id}&token={self.token}"
                async with websockets.connect(url) as ws:
                    print(f"[+] Connected to Orchestrator: {self.server_ws_url}")
                    # Run heartbeat sender and message listener concurrently
                    heartbeat_task = asyncio.create_task(self._heartbeat_loop(ws))
                    listen_task = asyncio.create_task(self._listen_loop(ws))

                    done, pending = await asyncio.wait(
                        [heartbeat_task, listen_task],
                        return_when=asyncio.FIRST_COMPLETED,
                    )

                    for task in pending:
                        task.cancel()

            except (websockets.exceptions.ConnectionClosed, ConnectionRefusedError, OSError) as e:
                print(f"[!] Connection lost / unavailable: {e}. Retrying in 3 seconds...")
                await asyncio.sleep(3.0)
            except Exception as e:
                print(f"[!] Unexpected daemon error: {e}. Retrying in 5 seconds...")
                await asyncio.sleep(5.0)

    async def _heartbeat_loop(self, ws):
        while not self._stop_requested:
            payload = {
                "type": "heartbeat",
                "bot_id": self.bot_id,
                "status": self.status,
                "current_job_id": self.current_job_id,
                "system": self.get_system_info(),
                "timestamp": time.time(),
            }
            try:
                await ws.send(json.dumps(payload))
            except Exception:
                break
            await asyncio.sleep(self.heartbeat_interval)

    async def _listen_loop(self, ws):
        async for raw_msg in ws:
            try:
                msg = json.loads(raw_msg)
                msg_type = msg.get("type")

                if msg_type == "dispatch_job":
                    job_id = msg.get("job_id")
                    workflow_data = msg.get("workflow")
                    variables = msg.get("variables", {})
                    timeout_sec = float(msg.get("timeout_seconds", 300))
                    # Execute job in background task
                    asyncio.create_task(self._execute_job(ws, job_id, workflow_data, variables, timeout_sec))

                elif msg_type == "ping":
                    await ws.send(json.dumps({"type": "pong", "bot_id": self.bot_id}))

            except Exception as e:
                print(f"[!] Error processing message from Orchestrator: {e}")

    async def _execute_job(self, ws, job_id: str, workflow_data: dict, variables: dict, timeout_sec: float):
        self.status = "BUSY"
        self.current_job_id = job_id
        print(f"[*] Executing Job {job_id}...")

        await ws.send(json.dumps({
            "type": "job_started",
            "bot_id": self.bot_id,
            "job_id": job_id,
        }))

        temp_dir = tempfile.mkdtemp(prefix="rpa_job_")
        job_file = Path(temp_dir) / f"{job_id}.json"
        output_file = Path(temp_dir) / f"{job_id}_output.json"

        job_file.write_text(json.dumps({
            "workflow": workflow_data,
            "variables": variables,
        }), encoding="utf-8")

        # Launch worker subprocess
        cmd = module_cmd(
            "os_rpa.agent.worker",
            "--job-file",
            str(job_file),
            "--output-file",
            str(output_file),
        )

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Watchdog timeout handler
        start_time = time.time()
        timeout_occurred = False

        async def read_stream():
            nonlocal timeout_occurred
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                try:
                    event = json.loads(line.decode("utf-8").strip())
                    ev_type = event.get("type")
                    ev_data = event.get("data", {})

                    # Forward telemetry event to Orchestrator
                    await ws.send(json.dumps({
                        "type": "job_telemetry",
                        "bot_id": self.bot_id,
                        "job_id": job_id,
                        "event": ev_type,
                        "data": ev_data,
                    }))
                except Exception:
                    pass

        try:
            read_task = asyncio.create_task(read_stream())
            await asyncio.wait_for(proc.wait(), timeout=timeout_sec)
            await read_task
        except asyncio.TimeoutError:
            timeout_occurred = True
            try:
                proc.kill()
            except Exception:
                pass
            print(f"[!] Job {job_id} timed out after {timeout_sec}s. Terminated worker.")
            screenshot = capture_desktop_screenshot()
            await ws.send(json.dumps({
                "type": "job_finished",
                "bot_id": self.bot_id,
                "job_id": job_id,
                "result": {
                    "workflow_id": workflow_data.get("id", "unknown"),
                    "success": False,
                    "status": "TIMEOUT",
                    "error": f"Job execution exceeded timeout of {timeout_sec} seconds",
                    "screenshot": screenshot,
                },
            }))
            self.status = "IDLE"
            self.current_job_id = None
            return

        # Check result
        if output_file.exists():
            try:
                out_json = json.loads(output_file.read_text(encoding="utf-8"))
                await ws.send(json.dumps({
                    "type": "job_finished",
                    "bot_id": self.bot_id,
                    "job_id": job_id,
                    "result": out_json,
                }))
            except Exception as e:
                await ws.send(json.dumps({
                    "type": "job_finished",
                    "bot_id": self.bot_id,
                    "job_id": job_id,
                    "result": {
                        "workflow_id": workflow_data.get("id", "unknown"),
                        "success": False,
                        "status": "FAILED",
                        "error": f"Failed reading output: {e}",
                    },
                }))
        else:
            stderr_out = (await proc.stderr.read()).decode("utf-8")
            screenshot = capture_desktop_screenshot()
            await ws.send(json.dumps({
                "type": "job_finished",
                "bot_id": self.bot_id,
                "job_id": job_id,
                "result": {
                    "workflow_id": workflow_data.get("id", "unknown"),
                    "success": False,
                    "status": "FAILED",
                    "error": stderr_out or "Subprocess exited without result",
                    "screenshot": screenshot,
                },
            }))

        self.status = "IDLE"
        self.current_job_id = None
        print(f"[+] Finished Job {job_id}.")
