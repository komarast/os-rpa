import argparse
import json
import sys
import traceback
from pathlib import Path

from os_rpa.models import Workflow, ExecutionLogMessage
from os_rpa.engine.runner import WorkflowRunner
from os_rpa.queue.manager import QueueManager
from os_rpa.agent.forensics import capture_desktop_screenshot


def emit_event(event_type: str, data: dict):
    payload = {"type": event_type, "data": data}
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def run_worker(job_file: str, output_file: str, db_path: str = "data/rpa_queues.db"):
    job_path = Path(job_file)
    if not job_path.exists():
        sys.stderr.write(f"Job file {job_file} not found\n")
        sys.exit(1)

    try:
        raw_job = json.loads(job_path.read_text(encoding="utf-8"))
        wf_data = raw_job.get("workflow", {})
        init_vars = raw_job.get("variables", {})
        workflow = Workflow(**wf_data)
    except Exception as e:
        emit_event("error", {"message": f"Failed to parse job payload: {e}"})
        sys.exit(1)

    queue_mgr = QueueManager(db_path) if Path(db_path).parent.exists() or db_path == ":memory:" else None

    def on_node_start(node_id: str):
        emit_event("node_start", {"node_id": node_id})

    def on_node_complete(node_id: str, result: any):
        emit_event("node_complete", {
            "node_id": node_id,
            "result": str(result)[:300] if result is not None else None,
        })

    def on_log(log_msg: ExecutionLogMessage):
        emit_event("log", log_msg.model_dump())

    runner = WorkflowRunner(
        queue_manager=queue_mgr,
        on_node_start=on_node_start,
        on_node_complete=on_node_complete,
        on_log=on_log,
    )

    try:
        result = runner.run(workflow, initial_variables=init_vars)

        # If failed, capture screenshot forensics
        screenshot_data = None
        if not result.success:
            screenshot_data = capture_desktop_screenshot()
            if screenshot_data:
                emit_event("screenshot", {"screenshot": screenshot_data})

        out_data = result.model_dump()
        if screenshot_data:
            out_data["screenshot"] = screenshot_data

        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        Path(output_file).write_text(json.dumps(out_data, indent=2), encoding="utf-8")
        emit_event("result", out_data)

        sys.exit(0 if result.success else 1)

    except Exception as e:
        tb = traceback.format_exc()
        screenshot_data = capture_desktop_screenshot()
        err_data = {
            "error": str(e),
            "traceback": tb,
            "screenshot": screenshot_data,
        }
        emit_event("failure_forensics", err_data)

        if output_file:
            Path(output_file).parent.mkdir(parents=True, exist_ok=True)
            Path(output_file).write_text(json.dumps({
                "workflow_id": workflow.id,
                "success": False,
                "status": "FAILED",
                "error": str(e),
                "traceback": tb,
                "screenshot": screenshot_data,
            }, indent=2), encoding="utf-8")

        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="OS RPA Subprocess Job Worker")
    parser.add_argument("--job-file", required=True, help="Path to input job JSON")
    parser.add_argument("--output-file", required=True, help="Path to write execution result JSON")
    parser.add_argument("--db-path", default="data/rpa_queues.db", help="Path to SQLite queue database")
    args = parser.parse_args()

    run_worker(args.job_file, args.output_file, args.db_path)


if __name__ == "__main__":
    main()
