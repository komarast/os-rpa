from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import asyncio
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from os_rpa.models import Workflow, QueueItem, ExecutionResult, ExecutionLogMessage
from os_rpa.queue.manager import QueueManager
from os_rpa.engine.runner import WorkflowRunner
from os_rpa.actions.registry import ActionRegistry
from os_rpa.server.dispatcher import dispatcher
from os_rpa.paths import studio_dist
from os_rpa.engine.snapshot import json_default
from os_rpa.engine.workflow_store import find_workflow_file, workflows_dir
from os_rpa.inspector.service import InspectorBusyError, inspector
from os_rpa.inspector.browsers import list_instances as list_browser_instances

app = FastAPI(title="OS RPA Tool Engine API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

WORKFLOWS_DIR = workflows_dir()
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
    file_path = find_workflow_file(workflow_id, WORKFLOWS_DIR)
    if not file_path:
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


def _dumps(obj: Any) -> str:
    """json.dumps for websocket events whose payloads may contain runtime objects (pages, handles)."""
    return json.dumps(obj, default=json_default)


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
                websocket.send_text(_dumps({
                    "event": "log",
                    "data": log_msg.model_dump(),
                })),
                loop,
            )

        def on_node_start(node_id: str):
            asyncio.run_coroutine_threadsafe(
                websocket.send_text(_dumps({
                    "event": "node_start",
                    "node_id": node_id,
                })),
                loop,
            )

        def on_node_complete(node_id: str, result: Any):
            asyncio.run_coroutine_threadsafe(
                websocket.send_text(_dumps({
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
        await websocket.send_text(_dumps({
            "event": "finished",
            "result": exec_res.model_dump(),
        }))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_text(_dumps({
            "event": "error",
            "message": str(e),
        }))
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


# --- Interactive Debugging WebSocket ---
@app.websocket("/ws/debug")
async def run_workflow_debug_ws(websocket: WebSocket):
    await websocket.accept()
    loop = asyncio.get_running_loop()

    runner: Optional[WorkflowRunner] = None
    exec_task: Optional[asyncio.Task] = None

    try:
        data = await websocket.receive_text()
        init_msg = json.loads(data)
        wf = Workflow(**init_msg.get("workflow"))
        init_vars = init_msg.get("initial_variables", {})
        initial_bps = set(init_msg.get("breakpoints", []))
        initial_delay = float(init_msg.get("step_delay", 0.0))

        def on_log(log_msg: ExecutionLogMessage):
            asyncio.run_coroutine_threadsafe(
                websocket.send_text(_dumps({
                    "event": "log",
                    "data": log_msg.model_dump(),
                })),
                loop,
            )

        def on_node_start(node_id: str):
            asyncio.run_coroutine_threadsafe(
                websocket.send_text(_dumps({
                    "event": "node_start",
                    "node_id": node_id,
                })),
                loop,
            )

        def on_node_complete(node_id: str, result: Any):
            asyncio.run_coroutine_threadsafe(
                websocket.send_text(_dumps({
                    "event": "node_complete",
                    "node_id": node_id,
                    "result": str(result)[:300] if result is not None else None,
                })),
                loop,
            )

        def on_pause(node_id: str, current_vars: Dict[str, Any]):
            asyncio.run_coroutine_threadsafe(
                websocket.send_text(_dumps({
                    "event": "paused",
                    "node_id": node_id,
                    **runner.snapshot_variables(),
                })),
                loop,
            )

        def on_variables(snapshot: Dict[str, Any]):
            asyncio.run_coroutine_threadsafe(
                websocket.send_text(_dumps({"event": "variables", **snapshot})),
                loop,
            )

        runner = WorkflowRunner(
            queue_manager=queue_mgr,
            on_node_start=on_node_start,
            on_node_complete=on_node_complete,
            on_log=on_log,
            on_pause=on_pause,
            on_variables=on_variables,
            breakpoints=initial_bps,
            step_delay=initial_delay,
        )

        async def run_in_thread():
            res = await asyncio.to_thread(runner.run, wf, init_vars)
            await websocket.send_text(_dumps({
                "event": "finished",
                "result": res.model_dump(),
            }))

        exec_task = asyncio.create_task(run_in_thread())

        # Command listener loop
        while True:
            cmd_data = await websocket.receive_text()
            cmd_json = json.loads(cmd_data)
            cmd = cmd_json.get("cmd")

            if cmd == "pause":
                runner.request_pause()
            elif cmd == "resume":
                runner.request_resume()
                await websocket.send_text(_dumps({"event": "resumed"}))
            elif cmd == "step":
                runner.request_step()
            elif cmd == "stop":
                runner.request_stop()
            elif cmd == "set_breakpoints":
                runner.set_breakpoints(set(cmd_json.get("breakpoints", [])))
            elif cmd == "set_delay":
                runner.set_step_delay(float(cmd_json.get("delay", 0.0)))
            elif cmd in ("set_variable", "delete_variable"):
                try:
                    if cmd == "set_variable":
                        runner.set_variable(str(cmd_json.get("name", "")), cmd_json.get("value"))
                    else:
                        runner.delete_variable(str(cmd_json.get("name", "")))
                    await websocket.send_text(_dumps({"event": "variables", **runner.snapshot_variables()}))
                except Exception as e:
                    await websocket.send_text(_dumps({"event": "variable_error", "message": str(e)}))

    except WebSocketDisconnect:
        if runner:
            runner.request_stop()
    except Exception as e:
        try:
            await websocket.send_text(_dumps({"event": "error", "message": str(e)}))
        except Exception:
            pass
    finally:
        if exec_task and not exec_task.done():
            exec_task.cancel()
        try:
            await websocket.close()
        except Exception:
            pass


# --- Element Inspector (desktop & web "indicate on screen") ---
INSPECTOR_TARGETS = ("desktop", "web")


INSPECTOR_WEB_SOURCES = ("new", "cdp", "window")


class InspectorPickRequest(BaseModel):
    target: str
    url: Optional[str] = ""
    channel: Optional[str] = "auto"
    timeout: float = 120
    # web only: 'new' browser window, 'cdp' attach to an open browser at `endpoint`, or any open 'window'
    source: Optional[str] = "new"
    endpoint: Optional[str] = ""


class InspectorValidateRequest(BaseModel):
    target: str
    params: Dict[str, Any] = {}
    url: Optional[str] = ""
    channel: Optional[str] = "auto"
    timeout: float = 10
    endpoint: Optional[str] = ""


def _check_inspector_target(target: str):
    if target not in INSPECTOR_TARGETS:
        raise HTTPException(status_code=400, detail=f"target must be one of {INSPECTOR_TARGETS}")


@app.post("/api/inspector/pick")
async def inspector_pick(req: InspectorPickRequest):
    _check_inspector_target(req.target)
    source = req.source or "new"
    if source not in INSPECTOR_WEB_SOURCES:
        raise HTTPException(status_code=400, detail=f"source must be one of {INSPECTOR_WEB_SOURCES}")
    if source == "cdp" and not req.endpoint:
        raise HTTPException(status_code=400, detail="endpoint is required to attach to an open browser")
    try:
        return await asyncio.to_thread(
            inspector.pick, req.target, req.url or "", req.channel or "auto", max(5.0, min(req.timeout, 600.0)),
            source, req.endpoint or "",
        )
    except InspectorBusyError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.get("/api/inspector/browsers")
async def inspector_browsers():
    """Open browsers the web inspector can attach to (workflow browsers and debug-port browsers)."""
    return await asyncio.to_thread(list_browser_instances)


@app.post("/api/inspector/validate")
async def inspector_validate(req: InspectorValidateRequest):
    _check_inspector_target(req.target)
    try:
        return await asyncio.to_thread(
            inspector.validate, req.target, req.params, req.url or "", req.channel or "auto",
            max(1.0, min(req.timeout, 120.0)), req.endpoint or "",
        )
    except InspectorBusyError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.post("/api/inspector/cancel")
def inspector_cancel():
    return {"cancelled": inspector.cancel()}


# --- Unattended Remote Bot Dispatcher Endpoints ---
@app.websocket("/ws/agent")
async def agent_websocket(websocket: WebSocket, bot_id: Optional[str] = Query(None)):
    await websocket.accept()
    assigned_bot_id = bot_id or f"bot_{websocket.client.host if websocket.client else 'client'}"
    dispatcher.register_bot(assigned_bot_id, websocket)

    try:
        while True:
            raw_text = await websocket.receive_text()
            try:
                msg = json.loads(raw_text)
                dispatcher.handle_bot_message(assigned_bot_id, msg)
            except Exception as e:
                print(f"[!] Error parsing message from bot {assigned_bot_id}: {e}")
    except WebSocketDisconnect:
        pass
    finally:
        dispatcher.unregister_bot(assigned_bot_id)


@app.get("/api/bots")
def list_connected_bots():
    return dispatcher.list_bots()


class TriggerJobRequest(BaseModel):
    workflow: Workflow
    variables: Optional[Dict[str, Any]] = None
    target_bot_id: Optional[str] = None
    timeout_seconds: Optional[float] = 300.0


@app.post("/api/jobs/trigger")
async def trigger_remote_job(req: TriggerJobRequest):
    try:
        job = await dispatcher.dispatch_job(
            workflow=req.workflow.model_dump(),
            variables=req.variables,
            target_bot_id=req.target_bot_id,
            timeout_seconds=req.timeout_seconds or 300.0,
        )
        return job
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/jobs")
def list_jobs():
    return dispatcher.list_jobs()


@app.get("/api/jobs/{job_id}")
def get_job_status(job_id: str):
    job = dispatcher.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/api/jobs/{job_id}/screenshot")
def get_job_screenshot(job_id: str):
    job = dispatcher.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    screenshot = job.get("screenshot")
    if not screenshot:
        raise HTTPException(status_code=404, detail="No screenshot available for this job")
    return {"screenshot": screenshot}


# Mount static studio build if present
STUDIO_DIST = studio_dist()
if STUDIO_DIST.exists():
    app.mount("/", StaticFiles(directory=str(STUDIO_DIST), html=True), name="studio")
else:
    @app.get("/", response_class=HTMLResponse)
    def studio_not_built():
        return f"""<!doctype html><html><head><title>OS RPA Studio</title></head>
<body style="font-family:Segoe UI,sans-serif;max-width:640px;margin:60px auto;line-height:1.5">
<h2>OS RPA Studio UI is not built</h2>
<p>The engine API is running, but no Studio build was found at <code>{STUDIO_DIST}</code>.</p>
<p>Build it, then restart the server:</p>
<pre style="background:#f3f3f3;padding:12px">cd studio
set NODE_USE_SYSTEM_CA=1
npm ci
npm run build</pre>
<p>Or just run <code>start_app.bat</code>, which builds it automatically.</p>
</body></html>"""
