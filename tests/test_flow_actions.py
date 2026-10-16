import pytest
from os_rpa.models import Workflow, WorkflowNode, WorkflowEdge
from os_rpa.engine.runner import WorkflowRunner


def test_flow_start_assign_and_end_success():
    wf = Workflow(
        id="wf_flow_test",
        name="Flow Test",
        variables={"base_price": 100},
        nodes=[
            WorkflowNode(
                id="n_start",
                type="flow.start",
                params={"inputs": {"discount": 20}},
            ),
            WorkflowNode(
                id="n_assign",
                type="flow.assign",
                params={
                    "assignments": {
                        "final_price": "{{base_price - discount}}",
                        "status_tag": "PAID",
                    }
                },
            ),
            WorkflowNode(
                id="n_end",
                type="flow.end",
                params={
                    "status": "SUCCESS",
                    "message": "Calculated successfully",
                    "output_variables": ["final_price", "status_tag"],
                },
            ),
        ],
        edges=[
            WorkflowEdge(source="n_start", target="n_assign"),
            WorkflowEdge(source="n_assign", target="n_end"),
        ],
    )

    runner = WorkflowRunner()
    res = runner.run(wf)

    assert res.success is True
    assert res.status == "SUCCESS"
    assert res.variables["final_price"] == 80
    assert res.variables["status_tag"] == "PAID"
    assert res.outputs == {"final_price": 80, "status_tag": "PAID"}


def test_flow_if_else_branching():
    wf = Workflow(
        id="wf_branch_test",
        name="Branch Test",
        variables={"score": 85},
        nodes=[
            WorkflowNode(
                id="n_check",
                type="flow.if_else",
                params={"condition": "score >= 70"},
            ),
            WorkflowNode(
                id="n_pass",
                type="flow.assign",
                params={"assignments": {"result": "PASSED"}},
            ),
            WorkflowNode(
                id="n_fail",
                type="flow.assign",
                params={"assignments": {"result": "FAILED"}},
            ),
        ],
        edges=[
            WorkflowEdge(source="n_check", target="n_pass", source_handle="true"),
            WorkflowEdge(source="n_check", target="n_fail", source_handle="false"),
        ],
    )

    runner = WorkflowRunner()
    res = runner.run(wf)

    assert res.success is True
    assert res.variables["result"] == "PASSED"


def test_flow_try_catch_action():
    wf = Workflow(
        id="wf_try_catch",
        name="Try Catch Test",
        nodes=[
            WorkflowNode(
                id="n_try",
                type="flow.try_catch",
                params={
                    "code": "val = 10 / 0",
                    "error_var": "division_error",
                },
            )
        ],
    )

    runner = WorkflowRunner()
    res = runner.run(wf)

    assert res.success is True
    assert "division by zero" in res.variables["division_error"]


def test_flow_loop_action():
    wf = Workflow(
        id="wf_loop",
        name="Loop Test",
        nodes=[
            WorkflowNode(
                id="n_loop",
                type="flow.loop",
                params={"collection": ["itemA", "itemB", "itemC"]},
            )
        ],
    )

    runner = WorkflowRunner()
    res = runner.run(wf)

    assert res.success is True
    assert res.variables["loop"]["total"] == 3
    assert res.variables["loop"]["items"] == ["itemA", "itemB", "itemC"]


def test_flow_loop_graph_body_and_done_execution():
    wf = Workflow(
        id="wf_loop_graph",
        name="Loop Graph Body & Done Test",
        variables={"running_sum": 0, "done_flag": False},
        nodes=[
            WorkflowNode(
                id="n_loop",
                type="flow.loop",
                params={
                    "collection": "[10, 20, 30]",
                    "item_var": "val",
                    "index_var": "idx",
                },
            ),
            WorkflowNode(
                id="n_add",
                type="flow.assign",
                params={
                    "assignments": {
                        "running_sum": "{{running_sum + val}}",
                        "last_idx": "{{idx}}",
                    }
                },
            ),
            WorkflowNode(
                id="n_done",
                type="flow.assign",
                params={
                    "assignments": {
                        "done_flag": True,
                        "final_message": "Sum is {{running_sum}}",
                    }
                },
            ),
        ],
        edges=[
            WorkflowEdge(source="n_loop", target="n_add", source_handle="loop"),
            WorkflowEdge(source="n_loop", target="n_done", source_handle="done"),
        ],
    )

    runner = WorkflowRunner()
    res = runner.run(wf)

    assert res.success is True
    assert res.variables["running_sum"] == 60
    assert res.variables["last_idx"] == 2
    assert res.variables["done_flag"] is True
    assert res.variables["final_message"] == "Sum is 60"


def test_flow_loop_while_condition():
    wf = Workflow(
        id="wf_loop_while",
        name="While Loop Test",
        variables={"counter": 0},
        nodes=[
            WorkflowNode(
                id="n_loop",
                type="flow.loop",
                params={
                    "collection": "",
                    "condition": "counter < 4",
                },
            ),
            WorkflowNode(
                id="n_inc",
                type="flow.assign",
                params={
                    "assignments": {
                        "counter": "{{counter + 1}}",
                    }
                },
            ),
        ],
        edges=[
            WorkflowEdge(source="n_loop", target="n_inc", source_handle="loop"),
        ],
    )

    runner = WorkflowRunner()
    res = runner.run(wf)

    assert res.success is True
    assert res.variables["counter"] == 4

