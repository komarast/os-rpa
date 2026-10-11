import argparse
import asyncio
import json
import sys
from pathlib import Path
import httpx
from os_rpa.models import Workflow
from os_rpa.queue.manager import QueueManager
from os_rpa.engine.runner import WorkflowRunner


def main():
    parser = argparse.ArgumentParser(prog="os-rpa", description="OS RPA Tool Engine, Robot Runner & Unattended Agent")
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")

    # Command: run
    run_parser = subparsers.add_parser("run", help="Run a workflow file locally")
    run_parser.add_argument("file", help="Path to workflow JSON file")
    run_parser.add_argument("--vars", help="Optional JSON string of variables", default="{}")

    # Command: queue
    queue_parser = subparsers.add_parser("queue", help="Queue commands")
    queue_subs = queue_parser.add_subparsers(dest="queue_sub", help="Queue sub-commands")
    
    # queue list
    queue_subs.add_parser("list", help="List all queues and statistics")
    
    # queue add
    add_parser = queue_subs.add_parser("add", help="Add an item to a queue")
    add_parser.add_argument("name", help="Queue name")
    add_parser.add_argument("payload", help="JSON string payload")
    add_parser.add_argument("--priority", type=int, default=0, help="Priority (higher = processed first)")

    # Command: server
    server_parser = subparsers.add_parser("server", help="Start the RPA Engine, Studio API, and Orchestrator server")
    server_parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    server_parser.add_argument("--port", type=int, default=8000, help="Port to bind")

    # Command: agent
    agent_parser = subparsers.add_parser("agent", help="Unattended Bot Agent commands")
    agent_subs = agent_parser.add_subparsers(dest="agent_sub", help="Agent sub-commands")
    agent_start = agent_subs.add_parser("start", help="Start unattended bot runner daemon")
    agent_start.add_argument("--server", default="ws://127.0.0.1:8000/ws/agent", help="WebSocket URL of Orchestrator")
    agent_start.add_argument("--bot-id", default=None, help="Custom identifier for this bot")
    agent_start.add_argument("--token", default="secret", help="Authentication token")

    # Command: trigger (remote trigger)
    trigger_parser = subparsers.add_parser("trigger", help="Remotely trigger a workflow on an unattended bot")
    trigger_parser.add_argument("file", help="Path to workflow JSON file")
    trigger_parser.add_argument("--server", default="http://127.0.0.1:8000", help="HTTP URL of Orchestrator")
    trigger_parser.add_argument("--bot-id", default=None, help="Target bot ID (optional, defaults to first idle bot)")
    trigger_parser.add_argument("--vars", default="{}", help="JSON variables string")

    args = parser.parse_args()

    if args.command == "run":
        wf_path = Path(args.file)
        if not wf_path.exists():
            print(f"Error: Workflow file '{wf_path}' not found", file=sys.stderr)
            sys.exit(1)

        wf_data = json.loads(wf_path.read_text(encoding="utf-8"))
        wf = Workflow(**wf_data)
        init_vars = json.loads(args.vars)

        queue_mgr = QueueManager("data/rpa_queues.db")
        runner = WorkflowRunner(queue_manager=queue_mgr)

        print(f"[*] Executing workflow '{wf.name}'...")
        res = runner.run(wf, initial_variables=init_vars)

        for log in res.logs:
            print(f"[{log.timestamp}] [{log.level}] {log.message}")

        if res.success:
            print(f"\n[+] Workflow finished successfully in {res.duration_seconds}s")
            sys.exit(0)
        else:
            print(f"\n[-] Workflow failed: {res.error}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "queue":
        queue_mgr = QueueManager("data/rpa_queues.db")
        if args.queue_sub == "list":
            queues = queue_mgr.list_queues()
            if not queues:
                print("No active queues found.")
            else:
                print(f"{'Queue Name':<20} {'Total':<8} {'New':<8} {'In Prog':<10} {'Success':<10} {'Failed':<8}")
                print("-" * 68)
                for q in queues:
                    print(
                        f"{q['queue_name']:<20} {q['total_items']:<8} {q['new_items']:<8} "
                        f"{q['in_progress_items']:<10} {q['success_items']:<10} {q['failed_items']:<8}"
                    )
        elif args.queue_sub == "add":
            try:
                payload = json.loads(args.payload)
            except Exception as e:
                print(f"Error parsing JSON payload: {e}", file=sys.stderr)
                sys.exit(1)
            item = queue_mgr.add_item(args.name, payload, priority=args.priority)
            print(f"[+] Added item {item.id} to queue '{args.name}'")

    elif args.command == "agent" and args.agent_sub == "start":
        from os_rpa.agent.daemon import BotAgent
        agent = BotAgent(
            server_ws_url=args.server,
            bot_id=args.bot_id,
            token=args.token,
        )
        try:
            asyncio.run(agent.start())
        except KeyboardInterrupt:
            print("\n[*] Bot daemon stopped.")

    elif args.command == "trigger":
        wf_path = Path(args.file)
        if not wf_path.exists():
            print(f"Error: Workflow file '{wf_path}' not found", file=sys.stderr)
            sys.exit(1)

        wf_data = json.loads(wf_path.read_text(encoding="utf-8"))
        vars_data = json.loads(args.vars)
        api_url = f"{args.server.rstrip('/')}/api/jobs/trigger"

        print(f"[*] Triggering workflow '{wf_data.get('name')}' on Orchestrator {args.server}...")
        try:
            with httpx.Client(timeout=30.0) as client:
                res = client.post(api_url, json={
                    "workflow": wf_data,
                    "variables": vars_data,
                    "target_bot_id": args.bot_id,
                })
                if res.status_code == 200:
                    job = res.json()
                    print(f"[+] Successfully dispatched job {job.get('job_id')} to bot '{job.get('bot_id')}'")
                else:
                    print(f"[-] Trigger failed ({res.status_code}): {res.text}", file=sys.stderr)
                    sys.exit(1)
        except Exception as e:
            print(f"[-] Trigger request failed: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "server":
        import uvicorn
        print(f"[*] Starting OS RPA Tool Server at http://{args.host}:{args.port}")
        uvicorn.run("os_rpa.server.app:app", host=args.host, port=args.port, reload=False)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
