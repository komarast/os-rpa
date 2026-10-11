from pathlib import Path
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


def test_http_request_action():
    # Test HTTP request against a reliable public endpoint or local mock
    http_act = ActionRegistry.get("http.request")
    # httpbin or raw jsonplaceholder
    res = http_act.execute(
        {
            "method": "GET",
            "url": "https://httpbin.org/get",
            "headers": {"X-Custom-RPA": "Antigravity"},
            "timeout": 10.0,
        },
        ExecutionContext(),
    )
    assert isinstance(res, dict)
    assert "status_code" in res
    assert res["status_code"] == 200
    assert res["ok"] is True
    assert "headers" in res["data"]
