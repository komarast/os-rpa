from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import asyncio
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from os_rpa.models import Workflow, QueueItem, ExecutionResult, ExecutionLogMessage
from os_rpa.queue.manager import QueueManager
from os_rpa.engine.runner import WorkflowRunner
from os_rpa.actions.registry import ActionRegistry

app = FastAPI(title="OS RPA Tool Engine API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

WORKFLOWS_DIR = Path("workflows")
WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)
queue_mgr = QueueManager("data/rpa_queues.db")


# --- Action Registry Endpoints ---
@app.get("/api/actions")
def list_actions():
    return ActionRegistry.list_actions()


# --- Queue Management Endpoints ---
@app.get("/api/queues")
def get_queues():
    return queue_mgr.list_queues()


@app.get("/api/queues/{queue_name}/items")
def get_queue_items(queue_name: str, status: Optional[str] = None, limit: int = 100):
    return queue_mgr.list_items(queue_name=queue_name, status=status, limit=limit)


class AddQueueItemRequest(BaseModel):
    queue_name: str
    payload: Dict[str, Any]
    priority: int = 0
    max_retries: int = 3


@app.post("/api/queues/items")
def add_queue_item(req: AddQueueItemRequest):
    item = queue_mgr.add_item(
        queue_name=req.queue_name,
        payload=req.payload,
        priority=req.priority,
        max_retries=req.max_retries,
    )
    return item


@app.post("/api/queues/items/{item_id}/retry")
def retry_queue_item(item_id: str):
    item = queue_mgr.fail_and_retry(item_id, error_message="Manually retried from Studio")
    return item


@app.delete("/api/queues/items/{item_id}")
def delete_queue_item(item_id: str):
    success = queue_mgr.delete_item(item_id)
    if not success:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"success": True}


# --- Workflow Storage Endpoints ---
@app.get("/api/workflows")
def list_workflows():
    results = []
    for f in WORKFLOWS_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            results.append({
                "id": data.get("id", f.stem),
                "name": data.get("name", f.name),
                "description": data.get("description", ""),
                "node_count": len(data.get("nodes", [])),
                "file_path": str(f),
            })
        except Exception:
            pass
    return results


@app.get("/api/workflows/{workflow_id}")
def get_workflow(workflow_id: str):
    file_path = WORKFLOWS_DIR / f"{workflow_id}.json"
    if not file_path.exists():
        # try search by id inside files
        for f in WORKFLOWS_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if data.get("id") == workflow_id:
                    return data
            except Exception:
                pass
        raise HTTPException(status_code=404, detail="Workflow not found")
    return json.loads(file_path.read_text(encoding="utf-8"))


@app.post("/api/workflows")
def save_workflow(wf: Workflow):
    file_path = WORKFLOWS_DIR / f"{wf.id}.json"
    file_path.write_text(json.dumps(wf.model_dump(), indent=2), encoding="utf-8")
    return {"success": True, "id": wf.id}


@app.delete("/api/workflows/{workflow_id}")
def delete_workflow(workflow_id: str):
    file_path = WORKFLOWS_DIR / f"{workflow_id}.json"
    if file_path.exists():
        file_path.unlink()
        return {"success": True}
    raise HTTPException(status_code=404, detail="Workflow not found")


# --- Execution Endpoints ---
class RunWorkflowRequest(BaseModel):
    workflow: Workflow
    initial_variables: Optional[Dict[str, Any]] = None


@app.post("/api/workflows/run", response_model=ExecutionResult)
def run_workflow_sync(req: RunWorkflowRequest):
    runner = WorkflowRunner(queue_manager=queue_mgr)
    return runner.run(req.workflow, initial_variables=req.initial_variables)


# --- Live WebSocket Execution ---
@app.websocket("/ws/run")
async def run_workflow_ws(websocket: WebSocket):
    await websocket.accept()
    loop = asyncio.get_running_loop()

    try:
        data = await websocket.receive_text()
        req_json = json.loads(data)
        wf = Workflow(**req_json.get("workflow"))
        init_vars = req_json.get("initial_variables", {})

        def on_log(log_msg: ExecutionLogMessage):
            asyncio.run_coroutine_threadsafe(
                websocket.send_text(json.dumps({
                    "event": "log",
                    "data": log_msg.model_dump(),
                })),
                loop,
            )

        def on_node_start(node_id: str):
            asyncio.run_coroutine_threadsafe(
                websocket.send_text(json.dumps({
                    "event": "node_start",
                    "node_id": node_id,
                })),
                loop,
            )

        def on_node_complete(node_id: str, result: Any):
            asyncio.run_coroutine_threadsafe(
                websocket.send_text(json.dumps({
                    "event": "node_complete",
                    "node_id": node_id,
                    "result": str(result)[:300] if result is not None else None,
                })),
                loop,
            )

        runner = WorkflowRunner(
            queue_manager=queue_mgr,
            on_node_start=on_node_start,
            on_node_complete=on_node_complete,
            on_log=on_log,
        )

        exec_res = await asyncio.to_thread(runner.run, wf, init_vars)
        await websocket.send_text(json.dumps({
            "event": "finished",
            "result": exec_res.model_dump(),
        }))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_text(json.dumps({
            "event": "error",
            "message": str(e),
        }))
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


# Mount static studio build if present
STUDIO_DIST = Path("studio/dist")
if STUDIO_DIST.exists():
    app.mount("/", StaticFiles(directory=str(STUDIO_DIST), html=True), name="studio")

