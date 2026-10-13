import threading
import time
from os_rpa.models import Workflow, WorkflowNode, WorkflowEdge
from os_rpa.engine.runner import WorkflowRunner


def test_runner_breakpoints_and_step():
    wf = Workflow(
        id="wf_debug_test",
        name="Debug Test",
        nodes=[
            WorkflowNode(id="n1", type="logic.set_variable", params={"variable_name": "v1", "value": 1}),
            WorkflowNode(id="n2", type="logic.set_variable", params={"variable_name": "v2", "value": 2}),
            WorkflowNode(id="n3", type="logic.set_variable", params={"variable_name": "v3", "value": 3}),
        ],
        edges=[
            WorkflowEdge(source="n1", target="n2"),
            WorkflowEdge(source="n2", target="n3"),
        ],
    )

    paused_nodes = []
    def on_pause(node_id, vars_dict):
        paused_nodes.append((node_id, vars_dict.copy()))

    runner = WorkflowRunner(
        breakpoints={"n2"},
        on_pause=on_pause,
    )

    # Run in a background thread so we can step/resume
    thread_res = {}
    def run_target():
        thread_res["result"] = runner.run(wf)

    t = threading.Thread(target=run_target)
    t.start()

    # Wait for pause at n2
    for _ in range(50):
        if len(paused_nodes) > 0:
            break
        time.sleep(0.05)

    assert len(paused_nodes) == 1
    assert paused_nodes[0][0] == "n2"
    assert paused_nodes[0][1]["v1"] == 1
    assert "v2" not in paused_nodes[0][1]  # n2 hasn't executed yet

    # Now request step over n2
    runner.request_step()

    # Wait for pause at n3
    for _ in range(50):
        if len(paused_nodes) > 1:
            break
        time.sleep(0.05)

    assert len(paused_nodes) == 2
    assert paused_nodes[1][0] == "n3"
    assert paused_nodes[1][1]["v2"] == 2

    # Now resume to completion
    runner.request_resume()
    t.join(timeout=3.0)

    res = thread_res.get("result")
    assert res is not None
    assert res.success is True
    assert res.variables["v3"] == 3


def test_runner_stop_request():
    wf = Workflow(
        id="wf_stop_test",
        name="Stop Test",
        nodes=[
            WorkflowNode(id="n1", type="logic.set_variable", params={"variable_name": "v1", "value": 1}),
            WorkflowNode(id="n2", type="logic.set_variable", params={"variable_name": "v2", "value": 2}),
        ],
        edges=[WorkflowEdge(source="n1", target="n2")],
    )

    runner = WorkflowRunner(breakpoints={"n2"})

    def run_target():
        runner.run(wf)

    t = threading.Thread(target=run_target)
    t.start()
    time.sleep(0.1)

    runner.request_stop()
    t.join(timeout=3.0)

    assert runner._stop_requested is True


def test_runner_variable_snapshots_track_sources_and_debugger_edits():
    wf = Workflow(
        id="wf_vars_test",
        name="Variables Test",
        variables={"greeting": "hi"},
        nodes=[
            WorkflowNode(id="n1", type="logic.set_variable", params={"variable_name": "count", "value": 1}),
            WorkflowNode(id="n2", type="logic.set_variable", params={"variable_name": "total", "value": "{{count + 1}}"}),
        ],
        edges=[WorkflowEdge(source="n1", target="n2")],
    )

    snapshots = []
    paused = threading.Event()
    runner = WorkflowRunner(
        breakpoints={"n2"},
        on_pause=lambda node_id, _vars: paused.set(),
        on_variables=snapshots.append,
    )

    result = {}
    t = threading.Thread(target=lambda: result.setdefault("res", runner.run(wf)))
    t.start()
    assert paused.wait(3.0)

    snap = runner.snapshot_variables()
    assert snap["variables"] == {"greeting": "hi", "count": 1}
    assert snap["meta"]["greeting"] == {"type": "str", "source": "workflow"}
    assert snap["meta"]["count"] == {"type": "int", "source": "n1"}

    # Edit while paused: next step sees the new value
    runner.set_variable("count", 41)
    assert runner.snapshot_variables()["meta"]["count"]["source"] == "debugger"
    try:
        runner.set_variable("_internal", 1)
        assert False, "private names must be rejected"
    except ValueError:
        pass

    runner.request_resume()
    t.join(timeout=3.0)

    assert result["res"].variables["total"] == 42
    assert snapshots[-1]["meta"]["total"]["source"] == "n2"
    assert any("count" in s["variables"] for s in snapshots)


def test_snapshot_handles_unserializable_values():
    import json
    from os_rpa.engine.snapshot import to_jsonable, json_default

    class Page:
        pass

    value = {"page": Page(), "items": (1, 2), "nested": {"s": {3}}}
    assert to_jsonable(value) == {"page": "<Page>", "items": [1, 2], "nested": {"s": [3]}}
    assert json.loads(json.dumps({"v": Page()}, default=json_default)) == {"v": "<Page>"}
