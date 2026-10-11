import time
from typing import Any, Callable, Dict, List, Optional, Set
from os_rpa.models import ExecutionResult, Workflow, WorkflowNode
from os_rpa.engine.context import ExecutionContext
from os_rpa.engine.evaluator import evaluate_value, evaluate_expression
from os_rpa.actions.registry import ActionRegistry
from os_rpa.queue.manager import QueueManager


class WorkflowRunner:
    """Executes an RPA workflow graph or sequence with variable propagation and lifecycle hooks."""

    def __init__(
        self,
        queue_manager: Optional[QueueManager] = None,
        on_node_start: Optional[Callable[[str], None]] = None,
        on_node_complete: Optional[Callable[[str, Any], None]] = None,
        on_log: Optional[Callable[[Any], None]] = None,
    ):
        self.queue_manager = queue_manager
        self.on_node_start = on_node_start
        self.on_node_complete = on_node_complete
        self.on_log = on_log

    def run(
        self,
        workflow: Workflow,
        initial_variables: Optional[Dict[str, Any]] = None,
        queue_item: Optional[Any] = None,
    ) -> ExecutionResult:
        start_time = time.time()
        
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
                logs=context.logs,
                duration_seconds=round(duration, 3),
            )

        try:
            # If workflow has edges, execute graph. Otherwise execute sequentially.
            if workflow.edges:
                self._execute_graph(workflow, nodes_by_id, context)
            else:
                self._execute_sequential(workflow.nodes, context)

            context.success(f"Workflow '{workflow.name}' completed successfully")
            duration = time.time() - start_time
            return ExecutionResult(
                workflow_id=workflow.id,
                success=True,
                status="COMPLETED",
                variables=get_clean_vars(context.variables),
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
                logs=context.logs,
                duration_seconds=round(duration, 3),
            )

    def _execute_sequential(self, nodes: List[WorkflowNode], context: ExecutionContext):
        for node in nodes:
            self._execute_node(node, context)

    def _execute_graph(
        self,
        workflow: Workflow,
        nodes_by_id: Dict[str, WorkflowNode],
        context: ExecutionContext,
    ):
        # Build adjacency list: node_id -> list of (target_id, condition)
        adj: Dict[str, List[Any]] = {n_id: [] for n_id in nodes_by_id}
        in_degree: Dict[str, int] = {n_id: 0 for n_id in nodes_by_id}

        for edge in workflow.edges:
            if edge.source in adj and edge.target in nodes_by_id:
                adj[edge.source].append((edge.target, edge.condition))
                in_degree[edge.target] += 1

        # Entry nodes have in-degree 0
        current_batch = [n_id for n_id, deg in in_degree.items() if deg == 0]
        if not current_batch:
            # Fallback to first node
            current_batch = [workflow.nodes[0].id]

        visited: Set[str] = set()

        while current_batch:
            next_batch = []
            for node_id in current_batch:
                if node_id in visited:
                    continue
                node = nodes_by_id.get(node_id)
                if not node:
                    continue

                visited.add(node_id)
                self._execute_node(node, context)

                # Determine next branch
                for target_id, condition in adj.get(node_id, []):
                    should_follow = True
                    if condition:
                        try:
                            should_follow = bool(evaluate_expression(condition, context.variables))
                        except Exception as e:
                            context.warning(f"Condition '{condition}' error: {e}. Defaulting to False.")
                            should_follow = False

                    if should_follow and target_id not in visited:
                        next_batch.append(target_id)

            current_batch = next_batch

    def _execute_node(self, node: WorkflowNode, context: ExecutionContext):
        context.current_node_id = node.id
        node_display = node.name or node.type
        context.info(f"Executing step '{node_display}' [{node.type}] (id={node.id})")

        if self.on_node_start:
            try:
                self.on_node_start(node.id)
            except Exception:
                pass

        action = ActionRegistry.get(node.type)
        eval_params = evaluate_value(node.params, context)

        result = action.execute(eval_params, context)

        if node.output:
            context.set(node.output, result)

        if self.on_node_complete:
            try:
                self.on_node_complete(node.id, result)
            except Exception:
                pass

