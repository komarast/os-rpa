## Project: OS RPA Tool

RPA tool that automates human steps using actions.

# Description

Robots handle passed Queue Items.
Interface uses drag-drop UI, also allows the ability to write code.
Actions: UI automation read, write, click; ability to automate browser or desktop applications, as well as Excel and other office documents.

---

# Current Progress & Implementation Status

### 1. Architecture & Tech Stack Decision
- **Automation Engine & Scripting**: Python 3.13 (`os_rpa` package)
- **Studio Interface**: React 19 + TypeScript + Vite + `@xyflow/react` (React Flow) + `@monaco-editor/react` (Monaco Editor)
- **Persistence**: Transactional SQLite database (`data/rpa_queues.db`)
- **Unattended Execution**: Outbound WebSocket daemon + isolated subprocess workers with watchdog timeout and screenshot failure forensics.

### 2. Implemented Components

- **Robots & Queue Management (`os_rpa/queue/manager.py`)**:
  - SQLite transactional storage with `threading.RLock` and atomic acquisitions.
  - Priority & FIFO processing.
  - Lifecycle: `NEW` -> `IN_PROGRESS` -> `SUCCESS` / `FAILED` -> `RETRIED` / `ABANDONED`.
  - Queue summary stats and payload/output tracking.

- **Automation Action Drivers (`os_rpa/actions/`)**:
  - **Control Flow (`flow.py`)**:
    - `flow.start`: Workflow entry point with default variable schemas.
    - `flow.end`: Explicit termination with final status (`SUCCESS`/`FAILED`) and output variables.
    - `flow.assign`: Multi-variable assignment with expression evaluation.
    - `flow.if_else`: Conditional branching with dedicated True (Green) and False (Red) output ports.
    - `flow.loop`: Collection iteration injecting `loop.item` and `loop.index`.
    - `flow.try_catch`: Safe code execution with error capture into variable.
  - **HTTP & REST APIs (`http_action.py`)**:
    - `http.request`: Full HTTP method support (`GET`, `POST`, `PUT`, `DELETE`, `PATCH`), headers, JSON payloads, and response status/data extraction.
  - **File System Operations (`file_system.py`)**:
    - `file.read_text`, `file.write_text`, `file.copy`, `file.delete`, `file.exists`.
  - **Web Automation (`web.py`)**: Playwright Chromium integration (`web.open_browser`, `web.navigate`, `web.click`, `web.type`, `web.get_text`, `web.screenshot`, `web.close_browser`).
  - **Desktop UI Automation (`desktop.py`)**: Windows UI Automation via `uiautomation` (`desktop.find_window`, `desktop.click`, `desktop.type`, `desktop.get_text`, `desktop.send_keys`) with simulation fallback.
  - **Excel Automation (`excel.py`)**: Native spreadsheet manipulation via `openpyxl` (`excel.create`, `excel.read_range`, `excel.append_row`, `excel.write_cell`).
  - **Custom Code Activity (`script.py`)**: Sandboxed Python script execution (`script.python`) with context variables (`context`, `variables`, `item`) and standard output capture into logs.
  - **Logic & Flow (`logic.py`)**: Variable assignment (`logic.set_variable`), delays, and logging.

- **Unattended Bot Host & Orchestrator (`os_rpa/agent/` & `os_rpa/server/dispatcher.py`)**:
  - **Bot Runner Daemon (`os_rpa/agent/daemon.py`)**: Outbound WebSocket connection (`/ws/agent`), periodic heartbeats, job listener, sandboxed subprocess spawning (`worker.py`), watchdog timeout handling.
  - **Failure Forensics (`os_rpa/agent/forensics.py`)**: Automatic desktop screenshot capture upon unhandled exceptions with base64/file upload back to Orchestrator.
  - **Orchestrator WebSocket Dispatcher (`os_rpa/server/dispatcher.py`)**: Bot registry, live connection tracking (`/api/bots`), remote job dispatching (`/api/jobs/trigger`), and screenshot retrieval (`/api/jobs/{job_id}/screenshot`).

- **Workflow Engine & Interactive Debugger (`os_rpa/engine/`)**:
  - Graph & sequential execution with dynamic variable expression evaluator (`{{variable}}` and Python expressions).
  - Breakpoints support on any node.
  - Single-step stepping (`Step Over`), Pause, Resume, and Stop controls.
  - Slow-motion configurable execution delay (0ms – 2000ms).
  - Real-time event hooks and WebSocket debug channel (`/ws/debug`).

- **Visual Studio UI (`studio/`)**:
  - **Interactive Debug Toolbar**: Debug (F5), Resume (F5), Step Over (F10), Pause, Stop, and Slow-Motion slider.
  - **Visual Breakpoints**: Clickable red breakpoint dot on every node.
  - **Console Drawer**:
    - **Logs Tab**: Real-time streaming log events.
    - **Variables Inspector Tab**: Live table of context variables, types, and values.
    - **Call Stack Tab**: History of executed steps with durations and previews.
    - **Unattended Bots Tab**: Real-time view of connected bots and direct "Dispatch to Bot" button.
  - **Work Queues Modal**: Interface to inspect queue items, view backlog statistics, add items with JSON payloads, and retry failed items.
  - **Embedded Monaco Editor**: VS Code-grade code editor for custom Python scripts and expressions.
  - Production build compiled (`studio/dist`) and mounted by FastAPI.

- **CLI Runner & Unified Server (`os_rpa/cli.py` & `os_rpa/server/app.py`)**:
  - Single port (8000) hosts Studio UI, REST API, WebSocket runner, debugger, and bot dispatcher.
  - Headless execution: `python -m os_rpa.cli run <workflow.json>`.
  - Bot Daemon launcher: `python -m os_rpa.cli agent start --server ws://localhost:8000/ws/agent --bot-id <id>`.
  - Remote trigger CLI: `python -m os_rpa.cli trigger <workflow.json> --server http://localhost:8000`.
  - Queue management: `python -m os_rpa.cli queue list` / `queue add`.

---

# Completed Roadmap Items

### Priority 1: Control Flow Nodes
- [x] **`flow.start` (Start Node)**: Workflow entry point with declared input schema and defaults.
- [x] **`flow.end` (End Node)**: Explicit workflow termination with final status (`SUCCESS`, `FAILED`), message, and output variables extraction.
- [x] **`flow.assign` (Assign Variable Node)**: Multi-variable assignment with dynamic expression evaluation.
- [x] **`flow.loop` (Loop / For-Each Node)**: Iterates over collections or counts, exposing `loop.item`, `loop.index`, and `loop.total`.

### Priority 2: Branching & Robustness Nodes
- [x] **`flow.if_else` (Decision Node)**: Dedicated True (Green) and False (Red) output ports with conditional branch routing.
- [x] **`flow.try_catch` (Error Handling Node)**: Wraps execution with safe error capture into context variable.

### Priority 3: Utility & Integration Nodes
- [x] **`http.request` (REST API & Webhooks)**: HTTP calls (`GET`, `POST`, `PUT`, `DELETE`, `PATCH`) with headers, auth, and auto JSON parsing via `httpx`.
- [x] **`file.system` (File Operations)**: `file.read_text`, `file.write_text`, `file.copy`, `file.delete`, `file.exists`.

### Priority 4: Interactive Debugging Panel
- [x] **Visual Breakpoints**: Click node breakpoint dot to toggle; runner pauses automatically.
- [x] **Execution Controls (Debug Toolbar)**: Step Over (F10), Pause / Resume (F5), Stop, and Slow-Motion slider (0ms – 2000ms).
- [x] **Live Variable Watcher & Inspector**: Real-time table showing all variables in `context.variables` (name, type, preview value).
- [x] **Call Stack & Step History**: Chronological list of completed steps with inputs, outputs, duration, and status.

### Priority 5: Unattended Remote Bot Architecture
- [x] **Outbound WebSocket Dispatcher (`/ws/agent`)**: Heartbeats, bot tracking, and state management.
- [x] **Remote Trigger API (`/api/jobs/trigger`)**: Remote webhook/API job scheduling on available bots.
- [x] **Isolated Subprocess Worker (`os_rpa/agent/worker.py`)**: Sandboxed process per job with watchdog timeout.
- [x] **Failure Forensics (`os_rpa/agent/forensics.py`)**: Automatic desktop screenshot on failure transmitted back to Orchestrator.

---

### Automated Tests: 26 Tests Passing (`python -m pytest tests -v`)
- `tests/test_flow_actions.py`: Flow start, assign, end, if_else branching, try_catch, and loop.
- `tests/test_http_and_file_actions.py`: HTTP request execution and file read/write/copy/delete/exists.
- `tests/test_debugging.py`: Breakpoints, pause, step over, and stop controls.
- `tests/test_unattended_bot.py`: Dispatcher lifecycle, subprocess worker isolation, and remote bot APIs.
- `tests/test_queue.py`: Queue item lifecycle, atomic pickup, and retries.
- `tests/test_engine.py`: AST sequential execution, expression evaluator, and conditional branching.
- `tests/test_excel.py`: Excel file creation, appending, range reading, and cell writing.
- `tests/test_script.py`: Sandboxed Python script execution and stdout capture.
- `tests/test_web.py`: Headless Playwright browser automation and screenshot capture.
- `tests/test_e2e_workflow.py`: End-to-end integration pipeline.
- `tests/test_api.py`: FastAPI endpoints for actions, queues, workflows, execution, and static UI delivery.
