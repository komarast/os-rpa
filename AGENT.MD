## Project: OS RPA Tool

RPA tool that automates human steps using actions.

# Description

Robots handle passed Queue Items.
Interface uses drag-drop UI, also allows the ability to write code.
Actions: UI automation read, write, click; ability to automate browser or desktop applications, as well as Excel and other office documents.

---

# Current Progress & Implementation Status (MVP Complete)

### 1. Architecture & Tech Stack Decision
- **Automation Engine & Scripting**: Python 3.13 (`os_rpa` package)
- **Studio Interface**: React 19 + TypeScript + Vite + `@xyflow/react` (React Flow) + `@monaco-editor/react` (Monaco Editor)
- **Persistence**: Transactional SQLite database (`data/rpa_queues.db`)

### 2. Implemented Components

- **Robots & Queue Management (`os_rpa/queue/manager.py`)**:
  - SQLite transactional storage with `threading.RLock` and atomic acquisitions.
  - Priority & FIFO processing.
  - Lifecycle: `NEW` -> `IN_PROGRESS` -> `SUCCESS` / `FAILED` -> `RETRIED` / `ABANDONED`.
  - Queue summary stats and payload/output tracking.

- **Automation Action Drivers (`os_rpa/actions/`)**:
  - **Web Automation (`web.py`)**: Playwright Chromium integration (`web.open_browser`, `web.navigate`, `web.click`, `web.type`, `web.get_text`, `web.screenshot`, `web.close_browser`).
  - **Desktop UI Automation (`desktop.py`)**: Windows UI Automation via `uiautomation` (`desktop.find_window`, `desktop.click`, `desktop.type`, `desktop.get_text`, `desktop.send_keys`) with simulation fallback.
  - **Excel Automation (`excel.py`)**: Native spreadsheet manipulation via `openpyxl` (`excel.create`, `excel.read_range`, `excel.append_row`, `excel.write_cell`).
  - **Custom Code Activity (`script.py`)**: Sandboxed Python script execution (`script.python`) with context variables (`context`, `variables`, `item`) and standard output capture into logs.
  - **Logic & Flow (`logic.py`)**: Conditional branching (`logic.condition`), variable assignment (`logic.set_variable`), delays, and logging.

- **Workflow Engine & AST (`os_rpa/engine/`)**:
  - Graph & sequential execution with dynamic variable expression evaluator (`{{variable}}` and Python expressions).
  - Real-time event hooks for step progression and log streaming.

- **Visual Studio UI (`studio/`)**:
  - **Drag-and-Drop Canvas**: Built with `@xyflow/react` featuring custom nodes, category color coding, animated execution pulsing, and minimap.
  - **Embedded Monaco Editor**: VS Code-grade code editor for custom Python scripts and expressions.
  - **Work Queues Modal**: Interface to inspect queue items, view backlog statistics, add items with JSON payloads, and retry failed items.
  - **Execution Console**: Real-time log streaming over WebSocket with active step highlighting.
  - Production build compiled (`studio/dist`) and served directly by the backend server.

- **CLI Runner & Unified Server (`os_rpa/cli.py` & `os_rpa/server/app.py`)**:
  - Single port (8000) hosts both Studio UI and REST/WebSocket API.
  - Headless execution command: `python -m os_rpa.cli run <workflow.json>`.
  - Queue management commands: `python -m os_rpa.cli queue list` / `queue add`.

- **One-Click Launcher (`start_app.bat`)**:
  - Double-click to launch the server and automatically open `http://localhost:8000` in the default browser.

### 3. Testing & Verification

- **Automated Tests**: 15 tests implemented and passing (`pytest tests -v`):
  - `tests/test_queue.py`: Queue item lifecycle, atomic pickup, and retries.
  - `tests/test_engine.py`: AST sequential execution, expression evaluator, and conditional branching.
  - `tests/test_excel.py`: Excel file creation, appending, range reading, and cell writing.
  - `tests/test_script.py`: Custom Python code execution, context variable mutation, and stdout capture.
  - `tests/test_web.py`: Headless Playwright browser automation, element interaction, and screenshot capture.
  - `tests/test_e2e_workflow.py`: End-to-end integration pipeline (Queue pop -> Python calculation -> Excel append -> Web form submission -> Queue completion).
  - `tests/test_api.py`: FastAPI endpoints for actions, queues, workflows, execution, and static UI delivery.

### 4. Project File Structure
```
c:\Users\tkoma\apps\os-rpa-tool\
├── start_app.bat               # One-click app launcher
├── README.md                   # Documentation & quickstart
├── AGENT.MD                    # Project specification & progress log
├── requirements.txt            # Python dependencies
├── os_rpa/                     # Core Python engine package
│   ├── models.py               # Pydantic models (Workflow, QueueItem, ExecutionResult)
│   ├── cli.py                  # Command-line interface
│   ├── queue/manager.py        # SQLite transactional QueueManager
│   ├── engine/                 # Workflow runner, evaluator, and execution context
│   ├── actions/                # Action drivers (web, desktop, excel, script, logic)
│   └── server/app.py           # FastAPI REST API + WebSocket server
├── studio/                     # Drag-and-drop React Studio frontend
│   ├── src/                    # React Flow canvas, Monaco Editor, Queue Modal, Console
│   └── dist/                   # Production build mounted by FastAPI
├── tests/                      # Automated test suite (15 tests passing)
└── workflows/                  # Pre-built sample workflows
```

---

# Upcoming Roadmap: Additional Nodes TODO List

### Priority 1: Control Flow Nodes
- [ ] **`flow.start` (Start Node)**:
  - Defines the explicit entry point of the workflow.
  - Declares input argument schema and default values.
  - Single output handle (bottom/right).
- [ ] **`flow.end` (End Node)**:
  - Explicit workflow termination with final status (`SUCCESS`, `FAILED`) and message.
  - Extracts and returns specified output variables in the execution response.
  - Single input handle (top/left).
- [ ] **`flow.assign` (Assign Variable Node)**:
  - Sets one or more context variables in a single step without writing Python code.
  - Supports expression evaluation (e.g., `tax = subtotal * 0.21`, `clean_name = name.strip()`).
- [ ] **`flow.loop` (Loop / For-Each Node)**:
  - Iterates over collections (e.g., array of Excel rows, queue items) or runs counter/while conditions.
  - Dual output handles: **Loop Body** (per-item branch) and **Done** (completion branch).
  - Injects `loop.item` and `loop.index` into iteration scope.

### Priority 2: Branching & Robustness Nodes
- [ ] **`flow.if_else` (Decision Node)**:
  - Visual conditional branching with dedicated **True** (Green) and **False** (Red) output ports.
- [ ] **`flow.try_catch` (Error Handling Node)**:
  - Wraps execution blocks with `Try`, `Catch` (captures error details), and `Finally` paths.

### Priority 3: Utility & Integration Nodes
- [ ] **`http.request` (REST API & Webhooks)**:
  - Executes HTTP calls (`GET`, `POST`, `PUT`, `DELETE`) with headers, auth, and auto JSON parsing.
- [ ] **`file.system` (File Operations)**:
  - `file.read_text`, `file.write_text`, `file.copy`, `file.delete`.

---

# Upcoming Roadmap: Interactive Debugging Panel TODO List

- [ ] **Visual Breakpoints**:
  - Click on any node's corner to toggle a red breakpoint dot.
  - Runner pauses execution automatically when encountering a breakpoint.
- [ ] **Execution Controls (Debug Toolbar)**:
  - **Step Over (F10)**: Execute single node and pause at next node.
  - **Pause / Resume (F5)**: Pause at any point or resume until next breakpoint.
  - **Stop**: Abort workflow immediately.
  - **Slow-Motion Slider**: Configurable delay (0ms – 2000ms) between steps to visually watch execution on screen.
- [ ] **Live Variable Watcher & Inspector**:
  - Real-time table showing all variables in `context.variables` (name, type, preview value).
  - Ability to click and inspect complex objects/dicts (e.g. current queue item payload).
  - Ability to edit variable values in memory while paused before resuming.
- [ ] **Call Stack & Step History**:
  - Chronological list of completed steps with inputs, outputs, duration, and error details.
