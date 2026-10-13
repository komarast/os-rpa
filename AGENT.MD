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
- **Corporate Network Support**: TLS verified against the Windows certificate store (`truststore`), so TLS-inspecting proxies such as Zscaler work without exporting CA bundles.
- **Path Resolution (`os_rpa/paths.py`)**: Central place for `studio_dist()` (env `OS_RPA_STUDIO_DIST`), `workspace_dir()` (env `OS_RPA_HOME`), `module_cmd()` (frozen-safe `python -m` subprocess command), and `use_system_certificates()`.

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
    - TLS is verified with `truststore.SSLContext` (OS cert store, works behind Zscaler); `verify_ssl: false` param for self-signed internal endpoints.
  - **File System Operations (`file_system.py`)**:
    - `file.read_text`, `file.write_text`, `file.copy`, `file.delete`, `file.exists`.
  - **Web Automation (`web.py`)**: Playwright Chromium integration (`web.open_browser`, `web.navigate`, `web.click`, `web.type`, `web.get_text`, `web.screenshot`, `web.close_browser`).
    - Browser selection via `web.open_browser` param `channel` or env `OS_RPA_BROWSER_CHANNEL`: `auto` (default: bundled Chromium, falls back to installed Microsoft Edge when Playwright browsers are not downloaded), `chromium`, `msedge`, `chrome`.
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
  - **Live variable snapshots (`runner.snapshot_variables()`)**: JSON-safe public variables plus per-variable `meta` (`type`, `source`). Emitted through the `on_variables` hook at run start and after every step.
  - **Variable origin tracking (`runner.variable_sources`)**: Each variable records who last set it: a node id, `workflow` (workflow default), `input` (run input), `queue` (queue item), or `debugger` (manual edit). Detected by diffing `context.variables` around each action, so `logic.set_variable`, `flow.assign`, node `output`, scripts, etc. are all attributed.
  - **Debugger edits**: `runner.set_variable(name, value)` / `runner.delete_variable(name)`; names must be identifiers and must not start with `_` (private engine state).
  - **JSON-safe serialization (`os_rpa/engine/snapshot.py`)**: `to_jsonable()` / `json_default()` turn opaque runtime objects (Playwright pages, handles) into `"<TypeName>"`, so websocket events never fail on unserializable variables.
  - **Evaluator**: Strings that start and end with placeholders (`"{{a}} and {{b}}"`) are interpolated instead of being mis-evaluated as a single expression.
  - **`/ws/debug` protocol**:
    - Client -> server: first message `{workflow, initial_variables, breakpoints, step_delay}`, then commands `pause`, `resume`, `step`, `stop`, `set_breakpoints {breakpoints}`, `set_delay {delay}`, `set_variable {name, value}`, `delete_variable {name}`.
    - Server -> client: `log`, `node_start`, `node_complete`, `paused {node_id, variables, meta}`, `variables {variables, meta}`, `variable_error {message}`, `resumed`, `finished {result}`, `error {message}`.

- **Visual Studio UI (`studio/`)**:
  - **Interactive Debug Toolbar**: Debug (F5), Resume (F5), Step Over (F10), Pause, Stop, and Slow-Motion slider.
  - **Visual Breakpoints**: Clickable red breakpoint dot on every node.
  - **Console Drawer**:
    - **Logs Tab**: Real-time streaming log events.
    - **Variables Inspector Tab**: Live table of context variables, types, and values.
    - **Call Stack Tab**: History of executed steps with durations and previews.
    - **Unattended Bots Tab**: Real-time view of connected bots and direct "Dispatch to Bot" button.
  - **Debug Variables Panel (`components/DebugVariablesPanel.tsx`)**: Floating inspector on the canvas, opened automatically on Debug (F5) and toggled by the **Variables** toolbar button.
    - Live values updated after every step, type badges, "set by" step link (selects the node on canvas), changed-since-last-step highlight, filter by name/value, expandable pretty-printed JSON.
    - While paused: edit values (JSON input, Ctrl+Enter), remove variables, add new variables; changes are sent as `set_variable` / `delete_variable` and the next step sees them.
    - Keeps final values after the run finishes.
  - **Data Manager (`components/DataManagerModal.tsx`, toolbar **Data** button)**:
    - **All Variables** tab: union of workflow variables, step-created variables, and last-run values with columns Name, Defined By (workflow default / step / runtime, with step chips), Type, Default, Last Run Value, Used In.
    - **Workflow Variables** tab: add/edit/delete workflow-level variables (Text, Number, Boolean, JSON) with identifier/duplicate/JSON validation; Apply/Discard. Saved in the workflow JSON `variables` and set before the first step runs.
    - Helpers in `studio/src/variables.ts`: `findVariableDefinitions()` (node `output`, `logic.set_variable`, `flow.assign`, `flow.start` inputs, `flow.try_catch` error var, `flow.loop`, `queue.get_item`), `findVariableUsages()` (`{{...}}` expressions and script/condition code), value parsing and formatting.
  - **Work Queues Modal**: Interface to inspect queue items, view backlog statistics, add items with JSON payloads, and retry failed items.
  - **Embedded Monaco Editor**: VS Code-grade code editor for custom Python scripts and expressions.
  - Production build compiled (`studio/dist`) and mounted by FastAPI (absolute path via `paths.studio_dist()`). When the build is missing, `/` serves a "Studio UI is not built" help page instead of a 404 JSON.

- **CLI Runner & Unified Server (`os_rpa/cli.py` & `os_rpa/server/app.py`)**:
  - Single port (8000) hosts Studio UI, REST API, WebSocket runner, debugger, and bot dispatcher.
  - Headless execution: `python -m os_rpa.cli run <workflow.json>`.
  - Bot Daemon launcher: `python -m os_rpa.cli agent start --server ws://localhost:8000/ws/agent --bot-id <id>`.
  - Remote trigger CLI: `python -m os_rpa.cli trigger <workflow.json> --server http://localhost:8000`.
  - Queue management: `python -m os_rpa.cli queue list` / `queue add`.
  - **`start_app.bat`**: Creates `.venv` and installs `requirements.txt` if missing, sets `NODE_USE_SYSTEM_CA=1` (and `NODE_EXTRA_CA_CERTS` if `%USERPROFILE%\.certs\corp-ca.pem` exists), builds `studio/dist` with `npm ci && npm run build` when missing, then starts the server and opens the browser. The server only checks for `studio/dist` at startup, so restart it after building the UI.

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
- [x] **Isolated Subprocess Worker (`os_rpa/agent/worker.py`)**: Sandboxed process per job with watchdog timeout; spawned via `paths.module_cmd()`.
- [x] **Failure Forensics (`os_rpa/agent/forensics.py`)**: Automatic desktop screenshot on failure transmitted back to Orchestrator.

### Priority 6: Corporate Network (Zscaler) Compatibility
- [x] **System trust store for Python HTTPS**: `truststore` in `http.request` (in `requirements.txt`).
- [x] **Browser fallback**: Installed Edge used when Playwright's bundled Chromium is missing (no `playwright install` download needed).
- [x] **Node/npm behind proxy**: `NODE_USE_SYSTEM_CA=1` set by `start_app.bat` (Node 22.15+ / 24).
- [x] **Hermetic tests**: HTTP action tested against a local echo server; real HTTPS check marked `@pytest.mark.network` (`pytest -m "not network"` to skip offline).

### Priority 7: Debug Variables Panel & Data Manager
- [x] **Live variable streaming** after every step (`variables` event) with type and origin metadata.
- [x] **Edit / add / remove variables while paused** from the Studio.
- [x] **Debug Variables Panel** on the canvas (filter, change highlight, set-by step links, JSON expand).
- [x] **Data Manager**: overview of all variables (defined by, type, default, last value, used in) and a workflow variable editor persisted with the workflow.

---

# Next Roadmap Items

### Priority 8: Native Desktop App (planned, not started)
- [ ] `os_rpa/desktop.py`: pywebview (Edge WebView2) window hosting the Studio; uvicorn on a free localhost port in a background thread; closing the window stops the server; `--dev` loads the Vite dev server; `--run-module` entry for frozen worker subprocesses.
- [ ] `python -m os_rpa.cli desktop` subcommand; `start_app.bat` launches the desktop window via `pythonw`.
- [ ] Native Import/Export workflow dialogs via pywebview `js_api` (`studio/src/desktop.ts`), "Open workspace folder".
- [ ] Packaging: `os-rpa-studio.spec` (PyInstaller onedir, windowed, bundles `studio/dist`) + `build_desktop.bat`; workspace in `Documents\OS-RPA` when frozen.
- [ ] `tools/export_corp_ca.ps1`: export the Zscaler root CA to `%USERPROFILE%\.certs\corp-ca.pem` for tools that ignore the Windows store.
- [ ] Call `paths.use_system_certificates()` at CLI/desktop entry points (covers `wss://` agent connections and user scripts).

---

### Automated Tests: 31 Tests Passing (`python -m pytest tests -v`)
- `tests/test_flow_actions.py`: Flow start, assign, end, if_else branching, try_catch, and loop.
- `tests/test_http_and_file_actions.py`: HTTP request against a local echo server, real HTTPS via the system trust store (`network` marker), and file read/write/copy/delete/exists.
- `tests/test_debugging.py`: Breakpoints, pause, step over, stop controls, variable snapshots with origin tracking, debugger edits, and JSON-safe serialization.
- `tests/test_unattended_bot.py`: Dispatcher lifecycle, subprocess worker isolation, and remote bot APIs.
- `tests/test_queue.py`: Queue item lifecycle, atomic pickup, and retries.
- `tests/test_engine.py`: AST sequential execution, expression evaluator (incl. multi-placeholder interpolation), and conditional branching.
- `tests/test_excel.py`: Excel file creation, appending, range reading, and cell writing.
- `tests/test_script.py`: Sandboxed Python script execution and stdout capture.
- `tests/test_web.py`: Headless Playwright browser automation and screenshot capture (Edge fallback when Chromium is not installed).
- `tests/test_e2e_workflow.py`: End-to-end integration pipeline.
- `tests/test_api.py`: FastAPI endpoints for actions, queues, workflows, execution, static UI delivery (skipped if `studio/dist` is not built), and `/ws/debug` variable streaming/editing.
