import asyncio
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import WebSocket


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class BotDispatcher:
    """Orchestrator WebSocket Dispatcher managing remote unattended bots and job scheduling."""

    def __init__(self):
        # bot_id -> dict with details & active websocket
        self._bots: Dict[str, Dict[str, Any]] = {}
        # job_id -> dict with status, logs, result, screenshot
        self._jobs: Dict[str, Dict[str, Any]] = {}

    def register_bot(self, bot_id: str, websocket: WebSocket):
        self._bots[bot_id] = {
            "bot_id": bot_id,
            "websocket": websocket,
            "status": "IDLE",
            "hostname": "unknown",
            "system": {},
            "connected_at": utc_now_iso(),
            "last_heartbeat": utc_now_iso(),
            "last_heartbeat_ts": time.time(),
        }

    def unregister_bot(self, bot_id: str):
        if bot_id in self._bots:
            del self._bots[bot_id]

    def update_heartbeat(self, bot_id: str, data: Dict[str, Any]):
        if bot_id in self._bots:
            bot = self._bots[bot_id]
            bot["status"] = data.get("status", "IDLE")
            bot["system"] = data.get("system", {})
            bot["hostname"] = data.get("system", {}).get("hostname", "unknown")
            bot["last_heartbeat"] = utc_now_iso()
            bot["last_heartbeat_ts"] = time.time()

    def list_bots(self) -> List[Dict[str, Any]]:
        now = time.time()
        results = []
        for bot_id, bot in self._bots.items():
            # Mark OFFLINE if no heartbeat in 15 seconds
            is_alive = (now - bot.get("last_heartbeat_ts", 0)) < 15.0
            status = bot["status"] if is_alive else "OFFLINE"
            results.append({
                "bot_id": bot["bot_id"],
                "hostname": bot.get("hostname", "unknown"),
                "status": status,
                "system": bot.get("system", {}),
                "connected_at": bot.get("connected_at"),
                "last_heartbeat": bot.get("last_heartbeat"),
                "is_online": is_alive,
            })
        return results

    async def dispatch_job(
        self,
        workflow: Dict[str, Any],
        variables: Optional[Dict[str, Any]] = None,
        target_bot_id: Optional[str] = None,
        timeout_seconds: float = 300.0,
    ) -> Dict[str, Any]:
        available_bot_id = target_bot_id

        if not available_bot_id:
            # Pick first available IDLE online bot
            now = time.time()
            for b_id, b_info in self._bots.items():
                if b_info["status"] == "IDLE" and (now - b_info.get("last_heartbeat_ts", 0)) < 15.0:
                    available_bot_id = b_id
                    break

        if not available_bot_id or available_bot_id not in self._bots:
            raise ValueError(f"No available online bot found to execute job (target={target_bot_id})")

        bot = self._bots[available_bot_id]
        ws: WebSocket = bot["websocket"]

        job_id = f"job_{uuid.uuid4().hex[:10]}"
        job_record = {
            "job_id": job_id,
            "bot_id": available_bot_id,
            "workflow_id": workflow.get("id", "unknown"),
            "workflow_name": workflow.get("name", "Untitled"),
            "status": "DISPATCHED",
            "dispatched_at": utc_now_iso(),
            "finished_at": None,
            "variables": variables or {},
            "logs": [],
            "result": None,
            "screenshot": None,
        }
        self._jobs[job_id] = job_record
        bot["status"] = "BUSY"

        dispatch_payload = {
            "type": "dispatch_job",
            "job_id": job_id,
            "workflow": workflow,
            "variables": variables or {},
            "timeout_seconds": timeout_seconds,
        }

        await ws.send_text(json.dumps(dispatch_payload))
        return job_record

    def handle_bot_message(self, bot_id: str, msg: Dict[str, Any]):
        msg_type = msg.get("type")
        if msg_type == "heartbeat":
            self.update_heartbeat(bot_id, msg)

        elif msg_type == "job_started":
            job_id = msg.get("job_id")
            if job_id in self._jobs:
                self._jobs[job_id]["status"] = "RUNNING"

        elif msg_type == "job_telemetry":
            job_id = msg.get("job_id")
            ev_type = msg.get("event")
            data = msg.get("data", {})
            if job_id in self._jobs:
                job = self._jobs[job_id]
                if ev_type == "log":
                    job["logs"].append(data)
                elif ev_type == "screenshot":
                    job["screenshot"] = data.get("screenshot")

        elif msg_type == "job_finished":
            job_id = msg.get("job_id")
            result = msg.get("result", {})
            if job_id in self._jobs:
                job = self._jobs[job_id]
                job["status"] = "SUCCESS" if result.get("success") else "FAILED"
                job["finished_at"] = utc_now_iso()
                job["result"] = result
                if result.get("screenshot"):
                    job["screenshot"] = result.get("screenshot")

            if bot_id in self._bots:
                self._bots[bot_id]["status"] = "IDLE"

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self._jobs.get(job_id)

    def list_jobs(self) -> List[Dict[str, Any]]:
        return list(self._jobs.values())


dispatcher = BotDispatcher()
