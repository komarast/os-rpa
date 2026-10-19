import json
import threading
import time
from pathlib import Path

from os_rpa.models import Workflow, WorkflowNode, WorkflowEdge
from os_rpa.engine.runner import WorkflowRunner
from os_rpa.engine.workflow_store import find_workflow_file, load_workflow


def _save(path: Path, wf: Workflow) -> Path:
    path.write_text(json.dumps(wf.model_dump(), indent=2), encoding="utf-8")
    return path


def _child_workflow(status: str = "SUCCESS") -> Workflow:
    return Workflow(
        id="wf_child",
        name="Child Calculator",
        variables={"a": 1, "b": 1},
        nodes=[
            WorkflowNode(id="c_assign", type="flow.assign", params={"assignments": {"total": "{{a + b}}"}}),
            WorkflowNode(id="c_log", type="logic.log", params={"message": "child total {{total}}"}),
            WorkflowNode(
                id="c_end",
                type="flow.end",
                params={"status": status, "message": "child done", "output_variables": ["total"]},
            ),
        ],
        edges=[
            WorkflowEdge(source="c_assign", target="c_log"),
            WorkflowEdge(source="c_log", target="c_end"),
        ],
    )


def _parent_workflow(ref: str, **invoke_params) -> Workflow:
    return Workflow(
        id="wf_parent",
        name="Parent",
        variables={"x": 40},
        nodes=[
            WorkflowNode(
                id="p_invoke",
                type="flow.invoke_workflow",
                params={"workflow": ref, "arguments": {"a": "{{x}}", "b": 2}, **invoke_params},
                output="child_result",
            ),
            WorkflowNode(id="p_after", type="logic.set_variable", params={"variable_name": "after", "value": True}),
        ],
        edges=[WorkflowEdge(source="p_invoke", target="p_after")],
    )


def test_invoke_passes_arguments_and_returns_outputs(tmp_path: Path):
    child_file = _save(tmp_path / "child.json", _child_workflow())

    res = WorkflowRunner().run(_parent_workflow(str(child_file)))

    assert res.success is True, res.error
    child_result = res.variables["child_result"]
    assert child_result["status"] == "SUCCESS"
    assert child_result["outputs"] == {"total": 42}
    assert "total" not in res.variables  # child variables stay isolated
    assert res.variables["after"] is True
    # Child logs are forwarded into the parent run, attributed to the invoking step
    child_logs = [log for log in res.logs if "[Child Calculator]" in log.message]
    assert any("child total 42" in log.message for log in child_logs)
    assert all(log.node_id == "p_invoke" for log in child_logs)


def test_invoke_merge_outputs_copies_into_parent(tmp_path: Path):
    child_file = _save(tmp_path / "child.json", _child_workflow())

    res = WorkflowRunner().run(_parent_workflow(str(child_file), merge_outputs=True))

    assert res.success is True, res.error
    assert res.variables["total"] == 42


def test_invoke_by_saved_id_and_name(tmp_path: Path, monkeypatch):
    _save(tmp_path / "some_file_name.json", _child_workflow())
    monkeypatch.setenv("OS_RPA_WORKFLOWS_DIR", str(tmp_path))

    assert find_workflow_file("wf_child") == tmp_path / "some_file_name.json"
    assert find_workflow_file("child calculator") == tmp_path / "some_file_name.json"
    assert load_workflow("some_file_name").id == "wf_child"
    assert find_workflow_file("missing") is None

    res = WorkflowRunner().run(_parent_workflow("wf_child"))
    assert res.success is True, res.error
    assert res.variables["child_result"]["outputs"] == {"total": 42}


def test_invoke_failed_child_fails_parent(tmp_path: Path):
    child_file = _save(tmp_path / "child.json", _child_workflow(status="FAILED"))

    res = WorkflowRunner().run(_parent_workflow(str(child_file)))

    assert res.success is False
    assert res.status == "FAILED"
    assert "Child Calculator" in res.error and "child done" in res.error
    assert "after" not in res.variables


def test_invoke_failed_child_can_be_tolerated(tmp_path: Path):
    child_file = _save(tmp_path / "child.json", _child_workflow(status="FAILED"))

    res = WorkflowRunner().run(_parent_workflow(str(child_file), fail_on_error=False))

    assert res.success is True, res.error
    assert res.variables["child_result"]["success"] is False
    assert res.variables["child_result"]["status"] == "FAILED"
    assert res.variables["after"] is True


def test_invoke_missing_workflow_fails(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("OS_RPA_WORKFLOWS_DIR", str(tmp_path))
    res = WorkflowRunner().run(_parent_workflow("does_not_exist"))
    assert res.success is False
    assert "not found" in res.error


def test_recursive_invoke_hits_depth_limit(tmp_path: Path):
    self_file = tmp_path / "recursive.json"
    wf = Workflow(
        id="wf_recursive",
        name="Recursive",
        nodes=[WorkflowNode(id="r", type="flow.invoke_workflow", params={"workflow": str(self_file)})],
    )
    _save(self_file, wf)

    res = WorkflowRunner().run(wf)

    assert res.success is False
    assert "depth limit" in res.error


def test_stop_propagates_to_invoked_workflow(tmp_path: Path):
    slow_child = Workflow(
        id="wf_slow",
        name="Slow Child",
        nodes=[
            WorkflowNode(id="s1", type="logic.delay", params={"seconds": 0.3}),
            WorkflowNode(id="s2", type="logic.delay", params={"seconds": 0.3}),
            WorkflowNode(id="s3", type="logic.set_variable", params={"variable_name": "finished", "value": True}),
        ],
    )
    child_file = _save(tmp_path / "slow.json", slow_child)
    parent = _parent_workflow(str(child_file))
    runner = WorkflowRunner()

    def stop_soon():
        time.sleep(0.15)
        runner.request_stop()

    threading.Thread(target=stop_soon).start()
    res = runner.run(parent)

    assert res.status == "ABORTED"
    assert res.variables["child_result"]["status"] == "ABORTED"
    assert "after" not in res.variables


def test_invoke_action_is_listed_by_api():
    from fastapi.testclient import TestClient
    from os_rpa.server.app import app

    client = TestClient(app)
    actions = {a["type"]: a for a in client.get("/api/actions").json()}
    assert actions["flow.invoke_workflow"]["params_schema"]["workflow"]["type"] == "workflow"
