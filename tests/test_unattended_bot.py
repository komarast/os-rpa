import json
import subprocess
import sys
import tempfile
from pathlib import Path
from starlette.testclient import TestClient

from os_rpa.server.app import app
from os_rpa.server.dispatcher import BotDispatcher
from os_rpa.models import Workflow, WorkflowNode


def test_dispatcher_bot_lifecycle():
    disp = BotDispatcher()

    # Initially empty
    assert len(disp.list_bots()) == 0

    class MockWebSocket:
        async def send_text(self, txt):
            pass

    # Register bot
    mock_ws = MockWebSocket()
    disp.register_bot("bot-test-01", mock_ws)
    bots = disp.list_bots()
    assert len(bots) == 1
    assert bots[0]["bot_id"] == "bot-test-01"
    assert bots[0]["status"] == "IDLE"

    # Send heartbeat
    disp.handle_bot_message("bot-test-01", {
        "type": "heartbeat",
        "status": "IDLE",
        "system": {"hostname": "VM-RPA-01", "os": "Windows 11"},
    })

    bots = disp.list_bots()
    assert bots[0]["hostname"] == "VM-RPA-01"

    # Unregister bot
    disp.unregister_bot("bot-test-01")
    assert len(disp.list_bots()) == 0


def test_worker_subprocess_execution(tmp_path: Path):
    job_file = tmp_path / "test_job.json"
    out_file = tmp_path / "test_out.json"

    wf = Workflow(
        id="wf_worker_test",
        name="Worker Test",
        nodes=[
            WorkflowNode(
                id="n1",
                type="flow.assign",
                params={"assignments": {"msg": "Worker executed successfully"}},
            )
        ],
    )

    job_file.write_text(json.dumps({
        "workflow": wf.model_dump(),
        "variables": {},
    }), encoding="utf-8")

    cmd = [
        sys.executable,
        "-m",
        "os_rpa.agent.worker",
        "--job-file",
        str(job_file),
        "--output-file",
        str(out_file),
        "--db-path",
        ":memory:",
    ]

    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert out_file.exists()

    out_data = json.loads(out_file.read_text(encoding="utf-8"))
    assert out_data["success"] is True
    assert out_data["variables"]["msg"] == "Worker executed successfully"


def test_api_bots_and_jobs_endpoints():
    client = TestClient(app)
    
    # Check /api/bots
    res = client.get("/api/bots")
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    # Check /api/jobs
    res = client.get("/api/jobs")
    assert res.status_code == 200
    assert isinstance(res.json(), list)
