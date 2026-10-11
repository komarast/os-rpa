from typing import Any, Dict, List, Optional
from os_rpa.actions.base import BaseAction
from os_rpa.engine.context import ExecutionContext
from os_rpa.engine.evaluator import evaluate_expression, evaluate_value


class WorkflowTermination(Exception):
    """Exception raised by flow.end to explicitly terminate execution with final status."""
    def __init__(self, status: str, message: str, outputs: Dict[str, Any]):
        super().__init__(message)
        self.status = status
        self.message = message
        self.outputs = outputs


class FlowStartAction(BaseAction):
    name = "flow.start"
    category = "flow"
    description = "Defines the explicit workflow entry point and declares default input variables."
    params_schema = {
        "inputs": {
            "type": "object",
            "label": "Input Variables & Defaults",
            "default": {},
            "description": "Key-value map of initial variables declared by this workflow.",
        },
    }

    def execute(self, params: Dict[str, Any], context: ExecutionContext) -> Any:
        inputs = params.get("inputs", {})
        if isinstance(inputs, dict):
            for k, v in inputs.items():
                if k not in context.variables:
                    context.set(k, evaluate_value(v, context))
        context.info(f"Workflow started with inputs: {list(inputs.keys()) if isinstance(inputs, dict) else inputs}")
        return inputs


class FlowEndAction(BaseAction):
    name = "flow.end"
    category = "flow"
    description = "Explicitly terminates workflow execution with final status and returns output variables."
    params_schema = {
        "status": {
            "type": "select",
            "options": ["SUCCESS", "FAILED"],
            "label": "Final Status",
            "default": "SUCCESS",
        },
        "message": {
            "type": "string",
            "label": "Completion Message",
            "default": "Workflow completed successfully",
        },
        "output_variables": {
            "type": "array",
            "label": "Output Variable Names",
            "default": [],
            "description": "List of variable names to extract and return in the execution response.",
        },
    }

    def execute(self, params: Dict[str, Any], context: ExecutionContext) -> Any:
        status = params.get("status", "SUCCESS").upper()
        message = str(params.get("message", "Workflow finished"))
        var_names = params.get("output_variables", [])
        
        outputs: Dict[str, Any] = {}
        if isinstance(var_names, list):
            for var_name in var_names:
                if isinstance(var_name, str) and var_name in context.variables:
                    outputs[var_name] = context.variables[var_name]
        elif isinstance(var_names, dict):
            for out_key, expr in var_names.items():
                outputs[out_key] = evaluate_expression(expr, context.variables)

        context.set("_final_status", status)
        context.set("_final_message", message)
        context.set("_final_outputs", outputs)

        if status == "FAILED":
            context.error(f"Flow ended with failure: {message}")
            raise WorkflowTermination(status="FAILED", message=message, outputs=outputs)
        else:
            context.success(f"Flow ended successfully: {message}")
            raise WorkflowTermination(status="SUCCESS", message=message, outputs=outputs)


class FlowAssignAction(BaseAction):
    name = "flow.assign"
    category = "flow"
    description = "Assigns multiple variables in a single step using evaluated expressions or static values."
    params_schema = {
        "assignments": {
            "type": "object",
            "label": "Variable Assignments (var_name -> expression or value)",
            "required": True,
            "default": {},
        },
    }

    def execute(self, params: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        assignments = params.get("assignments", {})
        if not isinstance(assignments, dict):
            raise ValueError("'assignments' parameter must be an object/dict")

        results = {}
        for var_name, expr in assignments.items():
            evaluated = evaluate_value(expr, context)
            context.set(var_name, evaluated)
            results[var_name] = evaluated
            context.info(f"Assigned '{var_name}' = {repr(evaluated)}")

        return results


class FlowIfElseAction(BaseAction):
    name = "flow.if_else"
    category = "flow"
    description = "Evaluates a condition and branches execution (returns True or False)."
    params_schema = {
        "condition": {
            "type": "string",
            "label": "Condition Expression (e.g. total > 100 or item['status'] == 'APPROVED')",
            "required": True,
            "default": "True",
        },
    }

    def execute(self, params: Dict[str, Any], context: ExecutionContext) -> bool:
        cond_raw = params.get("condition", "True")
        result = bool(evaluate_expression(str(cond_raw), context.variables))
        context.info(f"Condition '{cond_raw}' evaluated to: {result}")
        return result


class FlowLoopAction(BaseAction):
    name = "flow.loop"
    category = "flow"
    description = "Iterates over a collection or count, exposing loop.item, loop.index, and loop.total."
    params_schema = {
        "collection": {
            "type": "any",
            "label": "Collection (list, range count, or variable reference)",
            "required": True,
            "default": [],
        },
        "item_var": {
            "type": "string",
            "label": "Item Variable Name (injected into context)",
            "default": "loop_item",
        },
        "index_var": {
            "type": "string",
            "label": "Index Variable Name (injected into context)",
            "default": "loop_index",
        },
    }

    def execute(self, params: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        coll = params.get("collection", [])
        if isinstance(coll, int):
            items = list(range(coll))
        elif isinstance(coll, (list, tuple)):
            items = list(coll)
        elif isinstance(coll, dict):
            items = list(coll.items())
        else:
            items = [coll]

        total = len(items)
        context.set("loop", {"items": items, "total": total})
        context.info(f"Loop initialized with {total} items")
        return {"items": items, "total": total}


class FlowTryCatchAction(BaseAction):
    name = "flow.try_catch"
    category = "flow"
    description = "Executes an action or code block safely, capturing errors without terminating the workflow."
    params_schema = {
        "code": {
            "type": "code",
            "language": "python",
            "label": "Try Python Code",
            "default": "# Code to execute safely\nresult = 10 / 2",
        },
        "error_var": {
            "type": "string",
            "label": "Error Variable Name",
            "default": "last_error",
        },
    }

    def execute(self, params: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        code = params.get("code", "")
        error_var = params.get("error_var", "last_error")

        scope = context.variables.copy()
        scope["context"] = context
        scope["variables"] = context.variables

        try:
            exec(code, {}, scope)
            context.set(error_var, None)
            context.info("Try block executed successfully with no errors.")
            return {"success": True, "error": None}
        except Exception as e:
            err_msg = str(e)
            context.set(error_var, err_msg)
            context.warning(f"Try block caught error: {err_msg}")
            return {"success": False, "error": err_msg}
