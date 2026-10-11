from os_rpa.actions.registry import ActionRegistry
from os_rpa.engine.context import ExecutionContext


def test_python_script_action():
    ctx = ExecutionContext(initial_variables={"num_a": 15, "num_b": 25})
    script_act = ActionRegistry.get("script.python")

    code = """
print(f"Adding {variables['num_a']} and {variables['num_b']}")
sum_result = variables['num_a'] + variables['num_b']
context.set('sum_result', sum_result)
output = sum_result * 2
"""
    result = script_act.execute({"code": code}, ctx)

    assert result == 80
    assert ctx.get("sum_result") == 40
    # Check stdout captured in logs
    log_messages = [l.message for l in ctx.logs]
    assert any("Adding 15 and 25" in m for m in log_messages)

