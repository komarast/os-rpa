import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set
from os_rpa.models import ExecutionResult, Workflow, WorkflowNode
from os_rpa.engine.context import ExecutionContext
from os_rpa.engine.evaluator import evaluate_value, evaluate_expression
from os_rpa.engine.snapshot import public_variables, to_jsonable, type_name
from os_rpa.actions.registry import ActionRegistry
from os_rpa.actions.flow import WorkflowTermination
from os_rpa.queue.manager import QueueManager


class WorkflowRunner:
    """Executes an RPA workflow graph or sequence with variable propagation, debugging, and lifecycle hooks."""

    def __init__(
        self,
        queue_manager: Optional[QueueManager] = None,
        on_node_start: Optional[Callable[[str], None]] = None,
        on_node_complete: Optional[Callable[[str, Any], None]] = None,
        on_log: Optional[Callable[[Any], None]] = None,
        on_pause: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        on_variables: Optional[Callable[[Dict[str, Any]], None]] = None,
        step_delay: float = 0.0,
        breakpoints: Optional[Set[str]] = None,
    ):
        self.queue_manager = queue_manager
        self.on_node_start = on_node_start
        self.on_node_complete = on_node_complete
        self.on_log = on_log
        self.on_pause = on_pause
        self.on_variables = on_variables
        self.step_delay = max(0.0, float(step_delay))
        self.breakpoints: Set[str] = set(breakpoints or [])

        # Debugger control primitives
        self._pause_event = threading.Event()
        self._pause_event.set()  # Not paused by default
        self._step_event = threading.Event()
        self._is_step_mode: bool = False
        self._stop_requested: bool = False

        # Live state for the debugger's variable inspector
        self._context: Optional[ExecutionContext] = None
        self.variable_sources: Dict[str, str] = {}

    def request_pause(self):
        """Pauses execution before the next node executes."""
        self._pause_event.clear()

    def request_resume(self):
        """Resumes running without single-stepping."""
        self._is_step_mode = False
        self._pause_event.set()
        self._step_event.set()

    def request_step(self):
        """Steps over a single node then pauses."""
        self._is_step_mode = True
        self._pause_event.set()
        self._step_event.set()

    def request_stop(self):
        """Requests immediate abortion of workflow execution."""
        self._stop_requested = True
        self._pause_event.set()
        self._step_event.set()

    def set_breakpoints(self, breakpoints: Set[str]):
        """Dynamically updates active breakpoints."""
        self.breakpoints = set(breakpoints)

    def set_step_delay(self, delay: float):
        """Dynamically updates slow-motion delay."""
        self.step_delay = max(0.0, float(delay))

    def snapshot_variables(self) -> Dict[str, Any]:
        """JSON-safe snapshot of current public variables with type and origin (node id,
        'workflow', 'input', 'queue' or 'debugger') for each."""
        if not self._context:
            return {"variables": {}, "meta": {}}
        current = public_variables(self._context.variables)
        return {
            "variables": {k: to_jsonable(v) for k, v in current.items()},
            "meta": {
                k: {"type": type_name(v), "source": self.variable_sources.get(k)}
                for k, v in current.items()
            },
        }

    def set_variable(self, name: str, value: Any):
        """Overrides a variable from the debugger (typically while paused)."""
        name = name.strip()
        if not name.isidentifier() or name.startswith("_"):
            raise ValueError(f"Invalid variable name '{name}'")
        if not self._context:
            raise RuntimeError("No workflow is running")
        self._context.set(name, value)
        self.variable_sources[name] = "debugger"
        self._context.info(f"Debugger set variable '{name}' = {str(value)[:120]}")

    def delete_variable(self, name: str):
        if self._context and not name.startswith("_"):
            self._context.variables.pop(name, None)
            self.variable_sources.pop(name, None)

    def _emit_variables(self):
        if self.on_variables:
            try:
                self.on_variables(self.snapshot_variables())
            except Exception:
                pass

    def run(
        self,
        workflow: Workflow,
        initial_variables: Optional[Dict[str, Any]] = None,
        queue_item: Optional[Any] = None,
    ) -> ExecutionResult:
        start_time = time.time()
        self._stop_requested = False

        # Merge initial variables from workflow default and runtime input
        combined_vars = workflow.variables.copy()
        if initial_variables:
            combined_vars.update(initial_variables)

        context = ExecutionContext(
            initial_variables=combined_vars,
            queue_item=queue_item,
            on_log=self.on_log,
        )
        if self.queue_manager:
            context.set("_queue_manager", self.queue_manager)

        self._context = context
        self.variable_sources = {k: "workflow" for k in workflow.variables}
        self.variable_sources.update({k: "input" for k in (initial_variables or {})})
        if queue_item is not None:
            self.variable_sources.update({"item": "queue", "queue_item_id": "queue"})
        self._emit_variables()

        context.info(f"Starting workflow '{workflow.name}' ({workflow.id})")

        def get_clean_vars(vars_dict: Dict[str, Any]) -> Dict[str, Any]:
            return {k: v for k, v in vars_dict.items() if not k.startswith("_")}

        nodes_by_id: Dict[str, WorkflowNode] = {n.id: n for n in workflow.nodes}
        if not nodes_by_id:
            context.warning("Workflow contains no nodes to execute")
            duration = time.time() - start_time
            return ExecutionResult(
                workflow_id=workflow.id,
                success=True,
                status="COMPLETED",
                variables=get_clean_vars(context.variables),
                outputs={},
                logs=context.logs,
                duration_seconds=round(duration, 3),
            )

        try:
            # If workflow has edges, execute graph. Otherwise execute sequentially.
            if workflow.edges:
                self._execute_graph(workflow, nodes_by_id, context)
            else:
                self._execute_sequential(workflow.nodes, context)

            if self._stop_requested:
                context.warning("Workflow execution stopped by user request.")
                duration = time.time() - start_time
                return ExecutionResult(
                    workflow_id=workflow.id,
                    success=False,
                    status="ABORTED",
                    error="Execution stopped by user",
                    variables=get_clean_vars(context.variables),
                    outputs=context.variables.get("_final_outputs", {}),
                    logs=context.logs,
                    duration_seconds=round(duration, 3),
                )

            final_status = context.variables.get("_final_status", "COMPLETED")
            final_outputs = context.variables.get("_final_outputs", {})
            context.success(f"Workflow '{workflow.name}' completed with status: {final_status}")
            duration = time.time() - start_time
            return ExecutionResult(
                workflow_id=workflow.id,
                success=(final_status in ("COMPLETED", "SUCCESS")),
                status=final_status,
                variables=get_clean_vars(context.variables),
                outputs=final_outputs,
                logs=context.logs,
                duration_seconds=round(duration, 3),
            )

        except WorkflowTermination as wt:
            duration = time.time() - start_time
            return ExecutionResult(
                workflow_id=workflow.id,
                success=(wt.status == "SUCCESS"),
                status=wt.status,
                error=(wt.message if wt.status == "FAILED" else None),
                variables=get_clean_vars(context.variables),
                outputs=wt.outputs,
                logs=context.logs,
                duration_seconds=round(duration, 3),
            )

        except Exception as e:
            context.error(f"Workflow failed at node '{context.current_node_id}': {e}")
            duration = time.time() - start_time
            return ExecutionResult(
                workflow_id=workflow.id,
                success=False,
                status="FAILED",
                error=str(e),
                variables=get_clean_vars(context.variables),
                outputs=context.variables.get("_final_outputs", {}),
                logs=context.logs,
                duration_seconds=round(duration, 3),
            )

    def _execute_sequential(self, nodes: List[WorkflowNode], context: ExecutionContext):
        for node in nodes:
            if self._stop_requested:
                break
            self._execute_node(node, context)

    def _execute_graph(
        self,
        workflow: Workflow,
        nodes_by_id: Dict[str, WorkflowNode],
        context: ExecutionContext,
    ):
        # Build adjacency list: node_id -> list of (target_id, condition, source_handle)
        adj: Dict[str, List[Any]] = {n_id: [] for n_id in nodes_by_id}
        in_degree: Dict[str, int] = {n_id: 0 for n_id in nodes_by_id}

        for edge in workflow.edges:
            if edge.source in adj and edge.target in nodes_by_id:
                adj[edge.source].append((edge.target, edge.condition, edge.source_handle))
                in_degree[edge.target] += 1

        # Entry nodes have in-degree 0 (or start with flow.start node if present)
        start_nodes = [n_id for n_id, n in nodes_by_id.items() if n.type == "flow.start"]
        if start_nodes:
            current_batch = start_nodes
        else:
            current_batch = [n_id for n_id, deg in in_degree.items() if deg == 0]
            if not current_batch:
                current_batch = [workflow.nodes[0].id]

        visited: Set[str] = set()

        while current_batch and not self._stop_requested:
            next_batch = []
            for node_id in current_batch:
                if self._stop_requested:
                    break
                if node_id in visited:
                    continue
                node = nodes_by_id.get(node_id)
                if not node:
                    continue

                visited.add(node_id)
                node_result = self._execute_node(node, context)

                # Determine next branch edges
                for target_id, condition, source_handle in adj.get(node_id, []):
                    should_follow = True

                    # 1. Check handle-based condition (e.g. True / False output ports)
                    if source_handle:
                        handle_lower = source_handle.lower()
                        if handle_lower in ("true", "yes"):
                            should_follow = bool(node_result is True or node_result == "True" or node_result == 1)
                        elif handle_lower in ("false", "no"):
                            should_follow = bool(node_result is False or node_result == "False" or node_result == 0)

                    # 2. Check explicit expression condition
                    if should_follow and condition:
                        try:
                            # Evaluate with context variables and last node result
                            cond_scope = context.variables.copy()
                            cond_scope["result"] = node_result
                            should_follow = bool(evaluate_expression(condition, cond_scope))
                        except Exception as e:
                            context.warning(f"Condition '{condition}' error: {e}. Defaulting to False.")
                            should_follow = False

                    if should_follow and target_id not in visited:
                        next_batch.append(target_id)

            current_batch = next_batch

    def _execute_node(self, node: WorkflowNode, context: ExecutionContext) -> Any:
        context.current_node_id = node.id
        node_display = node.name or node.type

        # Check breakpoint or single-step pause
        is_bp = node.id in self.breakpoints
        if is_bp or self._is_step_mode:
            context.info(f"Execution paused at node '{node_display}' (Breakpoint: {is_bp})")
            if self.on_pause:
                try:
                    self.on_pause(node.id, self.snapshot_variables()["variables"])
                except Exception:
                    pass
            self._pause_event.clear()
            # Wait until resume or step event
            self._pause_event.wait()
            if self._stop_requested:
                return None

        context.info(f"Executing step '{node_display}' [{node.type}] (id={node.id})")

        if self.on_node_start:
            try:
                self.on_node_start(node.id)
            except Exception:
                pass

        # Optional slow-motion delay
        if self.step_delay > 0:
            time.sleep(self.step_delay)

        action = ActionRegistry.get(node.type)
        eval_params = evaluate_value(node.params, context)

        before = dict(context.variables)
        try:
            result = action.execute(eval_params, context)

            if node.output:
                context.set(node.output, result)
        finally:
            # Attribute new/changed variables to this step (also on failure)
            for k, v in context.variables.items():
                if not k.startswith("_") and (k not in before or before[k] is not v):
                    self.variable_sources[k] = node.id

        if self.on_node_complete:
            try:
                self.on_node_complete(node.id, result)
            except Exception:
                pass
        self._emit_variables()

        return result
