import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import pytest
from os_rpa.actions.registry import ActionRegistry
from os_rpa.engine.context import ExecutionContext
from os_rpa.models import Workflow, WorkflowNode
from os_rpa.engine.runner import WorkflowRunner


def test_file_operations(tmp_path: Path):
    test_file = tmp_path / "subfolder" / "hello.txt"
    copy_file = tmp_path / "copied.txt"

    # Write
    write_act = ActionRegistry.get("file.write_text")
    write_act.execute(
        {"file_path": str(test_file), "content": "RPA File Content\n", "append": False},
        ExecutionContext(),
    )
    assert test_file.exists()

    # Append
    write_act.execute(
        {"file_path": str(test_file), "content": "Second Line", "append": True},
        ExecutionContext(),
    )

    # Read
    read_act = ActionRegistry.get("file.read_text")
    content = read_act.execute({"file_path": str(test_file)}, ExecutionContext())
    assert "RPA File Content\nSecond Line" == content

    # Copy
    copy_act = ActionRegistry.get("file.copy")
    copy_act.execute({"source": str(test_file), "destination": str(copy_file)}, ExecutionContext())
    assert copy_file.exists()

    # Exists
    exists_act = ActionRegistry.get("file.exists")
    assert exists_act.execute({"file_path": str(copy_file)}, ExecutionContext()) is True

    # Delete
    del_act = ActionRegistry.get("file.delete")
    del_act.execute({"file_path": str(copy_file)}, ExecutionContext())
    assert copy_file.exists() is False


class _EchoHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"path": self.path, "headers": dict(self.headers)}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def echo_server():
    server = HTTPServer(("127.0.0.1", 0), _EchoHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def test_http_request_action(echo_server: str):
    http_act = ActionRegistry.get("http.request")
    res = http_act.execute(
        {
            "method": "GET",
            "url": f"{echo_server}/get",
            "headers": {"X-Custom-RPA": "Antigravity"},
            "timeout": 10.0,
        },
        ExecutionContext(),
    )
    assert res["status_code"] == 200
    assert res["ok"] is True
    assert res["data"]["path"] == "/get"
    assert res["data"]["headers"]["X-Custom-RPA"] == "Antigravity"


@pytest.mark.network
def test_http_request_https_through_system_trust_store():
    """Real HTTPS request; passes behind TLS-inspecting proxies (Zscaler) via truststore."""
    http_act = ActionRegistry.get("http.request")
    res = http_act.execute({"method": "GET", "url": "https://httpbin.org/get", "timeout": 15.0}, ExecutionContext())
    assert res["status_code"] == 200

