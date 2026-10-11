import time
from typing import Any, Dict
from os_rpa.actions.base import BaseAction
from os_rpa.engine.context import ExecutionContext


class LogicLogAction(BaseAction):
    name = "logic.log"
    category = "logic"
    description = "Logs a custom message to the workflow execution console."
    params_schema = {
        "message": {"type": "string", "label": "Message", "required": True, "default": "Processing item..."},
        "level": {"type": "select", "options": ["INFO", "WARNING", "ERROR", "SUCCESS"], "label": "Log Level", "default": "INFO"},
    }

    def execute(self, params: Dict[str, Any], context: ExecutionContext) -> Any:
        msg = str(params.get("message", ""))
        level = params.get("level", "INFO").upper()
        context.log(level, msg)
        return msg


class LogicDelayAction(BaseAction):
    name = "logic.delay"
    category = "logic"
    description = "Pauses workflow execution for a specified number of seconds."
    params_schema = {
        "seconds": {"type": "number", "label": "Seconds to wait", "default": 1.0},
    }

    def execute(self, params: Dict[str, Any], context: ExecutionContext) -> Any:
        secs = float(params.get("seconds", 1.0))
        context.info(f"Pausing for {secs}s...")
        time.sleep(secs)
        return secs


class LogicSetVariableAction(BaseAction):
    name = "logic.set_variable"
    category = "logic"
    description = "Sets or calculates a variable in the workflow context."
    params_schema = {
        "variable_name": {"type": "string", "label": "Variable Name", "required": True},
        "value": {"type": "any", "label": "Value", "required": True},
    }

    def execute(self, params: Dict[str, Any], context: ExecutionContext) -> Any:
        var_name = params.get("variable_name")
        val = params.get("value")
        if not var_name:
            raise ValueError("Variable name is required")

        context.set(var_name, val)
        context.info(f"Variable '{var_name}' set to '{val}'")
        return val


class LogicConditionAction(BaseAction):
    name = "logic.condition"
    category = "logic"
    description = "Evaluates a condition and branches workflow execution."
    params_schema = {
        "expression": {"type": "string", "label": "Python Expression (e.g. item['amount'] > 100)", "required": True},
    }

    def execute(self, params: Dict[str, Any], context: ExecutionContext) -> Any:
        expr = params.get("expression", "True")
        result = bool(eval(expr, {}, context.variables))
        context.info(f"Condition '{expr}' evaluated to: {result}")
        return result

