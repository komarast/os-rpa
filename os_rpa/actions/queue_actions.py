from typing import Any, Dict
from os_rpa.actions.base import BaseAction
from os_rpa.engine.context import ExecutionContext
from os_rpa.models import QueueItemStatus


class QueueGetNextItemAction(BaseAction):
    name = "queue.get_item"
    category = "queue"
    description = "Retrieves the next pending item from a queue and sets it as the active item."
    params_schema = {
        "queue_name": {"type": "string", "label": "Queue Name", "required": True, "default": "DefaultQueue"}
    }

    def execute(self, params: Dict[str, Any], context: ExecutionContext) -> Any:
        queue_name = params.get("queue_name", "DefaultQueue")
        queue_mgr = context.get("_queue_manager")
        if not queue_mgr:
            raise RuntimeError("QueueManager is not attached to this execution context.")

        item = queue_mgr.get_next_item(queue_name)
        if item:
            context.current_item = item
            context.set("item", item.payload)
            context.set("queue_item_id", item.id)
            context.success(f"Retrieved queue item {item.id} from '{queue_name}'", {"payload": item.payload})
            return item.payload
        else:
            context.info(f"No pending items found in queue '{queue_name}'")
            return None


class QueueSetStatusAction(BaseAction):
    name = "queue.set_status"
    category = "queue"
    description = "Updates the status of the current or specified queue item (SUCCESS, FAILED, etc.)."
    params_schema = {
        "status": {"type": "select", "options": ["SUCCESS", "FAILED"], "label": "Status", "default": "SUCCESS"},
        "error_message": {"type": "string", "label": "Error Message (optional)", "default": ""},
        "output_data": {"type": "object", "label": "Output Data (optional)", "default": {}},
    }

    def execute(self, params: Dict[str, Any], context: ExecutionContext) -> Any:
        queue_mgr = context.get("_queue_manager")
        if not queue_mgr:
            raise RuntimeError("QueueManager is not attached to this execution context.")

        item_id = params.get("item_id") or context.get("queue_item_id")
        if not item_id:
            context.warning("No active queue item found to update status.")
            return None

        status_str = params.get("status", "SUCCESS").upper()
        status_enum = QueueItemStatus(status_str)
        err = params.get("error_message") or None
        out = params.get("output_data") or None

        updated = queue_mgr.set_status(item_id, status_enum, error_message=err, output_data=out)
        context.success(f"Queue item {item_id} marked as {status_str}")
        return updated.model_dump() if updated else None


class QueueAddItemAction(BaseAction):
    name = "queue.add_item"
    category = "queue"
    description = "Enqueues a new item with payload into a specified queue."
    params_schema = {
        "queue_name": {"type": "string", "label": "Queue Name", "required": True, "default": "DefaultQueue"},
        "payload": {"type": "object", "label": "Item Payload", "default": {}},
        "priority": {"type": "number", "label": "Priority (higher = processed first)", "default": 0},
    }

    def execute(self, params: Dict[str, Any], context: ExecutionContext) -> Any:
        queue_mgr = context.get("_queue_manager")
        if not queue_mgr:
            raise RuntimeError("QueueManager is not attached to this execution context.")

        queue_name = params.get("queue_name", "DefaultQueue")
        payload = params.get("payload", {})
        priority = int(params.get("priority", 0))

        item = queue_mgr.add_item(queue_name, payload, priority=priority)
        context.success(f"Added new item {item.id} to queue '{queue_name}'")
        return item.id

