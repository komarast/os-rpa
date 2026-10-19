import json
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
    description = (
        "Iterates over a collection, count, or condition. "
        "Connect 'LOOP' handle to actions to repeat, and 'DONE' handle to actions after completion."
    )
    params_schema = {
        "collection": {
            "type": "string",
            "label": "Collection, Count, or Variable (e.g. 5, [1, 2, 3], or {{items}})",
            "required": False,
            "default": "[1, 2, 3]",
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
        "condition": {
            "type": "string",
            "label": "While Condition (Optional, e.g. count < 10)",
            "default": "",
        },
        "max_iterations": {
            "type": "number",
            "label": "Max Iterations (Safety Limit)",
            "default": 1000,
        },
    }

    @staticmethod
    def parse_collection(coll: Any, context: ExecutionContext) -> List[Any]:
        if coll is None:
            return []
        if isinstance(coll, bool):
            return [coll]
        if isinstance(coll, int):
            return list(range(max(0, coll)))
        if isinstance(coll, float):
            return list(range(max(0, int(coll))))
        if isinstance(coll, (list, tuple, set, range)):
            return list(coll)
        if isinstance(coll, dict):
            return list(coll.items())
        if isinstance(coll, str):
            s = coll.strip()
            if not s:
                return []
            # 1. Pure integer count e.g. "5"
            if s.isdigit() or (s.startswith("-") and s[1:].isdigit()):
                return list(range(max(0, int(s))))
            # 2. JSON array or object e.g. '[1, 2, 3]' or '["a", "b"]'
            if (s.startswith("[") and s.endswith("]")) or (s.startswith("{") and s.endswith("}")):
                try:
                    parsed = json.loads(s)
                    return FlowLoopAction.parse_collection(parsed, context)
                except Exception:
                    pass
            # 3. Python expression or variable name e.g. "my_items" or "range(1, 5)"
            try:
                eval_res = evaluate_expression(s, context.variables)
                if eval_res is not s:
                    return FlowLoopAction.parse_collection(eval_res, context)
            except Exception:
                pass
            # 4. Comma-separated values e.g. "item1, item2, item3"
            if "," in s:
                return [part.strip() for part in s.split(",") if part.strip()]
            return [s]
        return [coll]

    def execute(self, params: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        coll_raw = params.get("collection", [])
        item_var = str(params.get("item_var") or "loop_item").strip() or "loop_item"
        index_var = str(params.get("index_var") or "loop_index").strip() or "loop_index"
        condition = str(params.get("condition") or "").strip()
        max_iterations = int(params.get("max_iterations") or 1000)

        items = self.parse_collection(coll_raw, context)
        if len(items) > max_iterations:
            items = items[:max_iterations]

        total = len(items)
        first_item = items[0] if total > 0 else None

        if total > 0:
            context.set(item_var, first_item)
            context.set(index_var, 0)

        loop_meta = {
            "items": items,
            "total": total,
            "index": 0,
            "item": first_item,
            "item_var": item_var,
            "index_var": index_var,
            "condition": condition,
            "max_iterations": max_iterations,
        }
        context.set("loop", loop_meta)
        context.info(f"Loop initialized with {total} items (item_var='{item_var}', index_var='{index_var}')")
        return loop_meta


class FlowInvokeWorkflowAction(BaseAction):
    name = "flow.invoke_workflow"
    category = "flow"
    description = (
        "Runs another saved workflow as a sub-step: passes arguments in as its variables "
        "and returns its flow.end outputs."
    )
    params_schema = {
        "workflow": {
            "type": "workflow",
            "label": "Workflow (saved id, name, or .json path)",
            "required": True,
            "default": "",
        },
        "arguments": {
            "type": "object",
            "label": "Arguments (name -> expression or value)",
            "default": {},
            "description": "Initial variables of the invoked workflow, e.g. {\"invoice\": \"{{item}}\"}.",
        },
        "merge_outputs": {
            "type": "boolean",
            "label": "Copy outputs into this workflow's variables",
            "default": False,
        },
        "fail_on_error": {
            "type": "boolean",
            "label": "Fail this step if the invoked workflow fails",
            "default": True,
        },
    }

    MAX_DEPTH = 16

    def execute(self, params: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        # Imported here: the runner imports the action registry, which imports this module
        from os_rpa.engine.runner import WorkflowRunner
        from os_rpa.engine.workflow_store import load_workflow

        ref = str(params.get("workflow") or "").strip()
        if not ref:
            raise ValueError("No workflow selected to invoke")
        if context.call_depth >= self.MAX_DEPTH:
            raise RecursionError(
                f"Invoke depth limit ({self.MAX_DEPTH}) reached while invoking '{ref}' (recursive workflow call?)"
            )

        arguments = params.get("arguments") or {}
        if isinstance(arguments, str):
            arguments = json.loads(arguments) if arguments.strip() else {}
        if not isinstance(arguments, dict):
            raise ValueError("'arguments' must be an object of name -> value")

        child_wf = load_workflow(ref)
        label = child_wf.name or child_wf.id

        def on_log(msg: Any):
            # Child logs are attributed to the invoking step and kept in this run's log
            context.log(msg.level, f"[{label}] {msg.message}", msg.details)

        context.info(f"Invoking workflow '{label}' with arguments {list(arguments.keys())}")
        runner = context.runner
        if runner is not None:
            result = runner.run_child(child_wf, initial_variables=arguments, on_log=on_log)
        else:
            result = WorkflowRunner(queue_manager=context.get("_queue_manager"), on_log=on_log).run(
                child_wf, initial_variables=arguments
            )

        outputs = dict(result.outputs or {})
        summary = {
            "workflow_id": child_wf.id,
            "workflow": label,
            "status": result.status,
            "success": result.success,
            "outputs": outputs,
            "error": result.error,
            "duration_seconds": result.duration_seconds,
        }

        if result.status == "ABORTED":
            context.warning(f"Invoked workflow '{label}' was stopped")
            return summary
        if not result.success:
            if bool(params.get("fail_on_error", True)):
                raise RuntimeError(f"Invoked workflow '{label}' failed: {result.error or result.status}")
            context.warning(f"Invoked workflow '{label}' failed: {result.error or result.status}")
            return summary

        if bool(params.get("merge_outputs", False)):
            for k, v in outputs.items():
                context.set(k, v)
        context.success(f"Invoked workflow '{label}' finished with status {result.status}")
        return summary


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
