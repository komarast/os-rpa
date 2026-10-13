from pathlib import Path
from os_rpa.engine.context import ExecutionContext
from os_rpa.engine.evaluator import evaluate_value, evaluate_expression
from os_rpa.engine.runner import WorkflowRunner
from os_rpa.models import Workflow, WorkflowNode, WorkflowEdge
from os_rpa.queue.manager import QueueManager


def test_evaluator():
    ctx = ExecutionContext(initial_variables={"user": "Alice", "count": 5, "price": 10.5})
    # Direct typed variable
    assert evaluate_value("{{count}}", ctx) == 5
    assert evaluate_value("{{count * 2}}", ctx) == 10
    # String interpolation
    assert evaluate_value("Hello {{user}}!", ctx) == "Hello Alice!"
    assert evaluate_value("Total: {{count * price}}", ctx) == "Total: 52.5"
    # Nested dict evaluation
    nested = {"greeting": "Hi {{user}}", "qty": "{{count}}"}
    res = evaluate_value(nested, ctx)
    assert res["greeting"] == "Hi Alice"
    assert res["qty"] == 5


def test_workflow_sequential_execution(tmp_path: Path):
    wf = Workflow(
        id="test_seq",
        name="Sequential Workflow",
        variables={"base": 10},
        nodes=[
            WorkflowNode(
                id="n1",
                type="logic.set_variable",
                params={"variable_name": "x", "value": "{{base * 2}}"},
                output="n1_out",
            ),
            WorkflowNode(
                id="n2",
                type="script.python",
                params={"code": "context.set('doubled_x', variables['x'] * 2)\noutput = 'done'"},
                output="n2_out",
            ),
            WorkflowNode(
                id="n3",
                type="logic.log",
                params={"message": "Result is {{doubled_x}}", "level": "INFO"},
            ),
        ],
    )

    runner = WorkflowRunner()
    result = runner.run(wf)

    assert result.success is True
    assert result.status == "COMPLETED"
    assert result.variables["x"] == 20
    assert result.variables["doubled_x"] == 40
    assert result.variables["n2_out"] == "done"
    assert len(result.logs) > 0


def test_workflow_graph_conditional_branching():
    # Branch: n1 -> (if x > 5) -> n2 (High)
    #            -> (if x <= 5) -> n3 (Low)
    wf = Workflow(
        id="test_branch",
        name="Branching Workflow",
        variables={"score": 8},
        nodes=[
            WorkflowNode(id="start", type="logic.log", params={"message": "Starting branch test"}),
            WorkflowNode(
                id="high_branch",
                type="logic.set_variable",
                params={"variable_name": "category", "value": "HIGH"},
            ),
            WorkflowNode(
                id="low_branch",
                type="logic.set_variable",
                params={"variable_name": "category", "value": "LOW"},
            ),
        ],
        edges=[
            WorkflowEdge(source="start", target="high_branch", condition="score > 5"),
            WorkflowEdge(source="start", target="low_branch", condition="score <= 5"),
        ],
    )

    runner = WorkflowRunner()
    result = runner.run(wf)

    assert result.success is True
    assert result.variables.get("category") == "HIGH"



def test_interpolation_with_placeholders_at_both_ends():
    from os_rpa.engine.evaluator import evaluate_value
    ctx = ExecutionContext(initial_variables={"greeting": "hello", "total": 13})
    assert evaluate_value("{{greeting}} total={{total}}", ctx) == "hello total=13"
    assert evaluate_value("{{total}}", ctx) == 13
