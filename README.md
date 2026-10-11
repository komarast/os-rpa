# OS RPA Tool

An open-source Robotic Process Automation (RPA) engine and visual studio for building, debugging, and running software robots.

---

## Features

- **Robots & Queue Items**: Work queue engine backed by SQLite with FIFO/Priority scheduling, transactional status (`NEW`, `IN_PROGRESS`, `SUCCESS`, `FAILED`), automatic retries, and output payload tracking.
- **Drag-and-Drop Studio Canvas**: Built with React Flow (`@xyflow/react`) for intuitive workflow design.
- **Write Custom Code**: Embedded **Monaco Editor** for custom Python scripts (`script.python`) with context variables and live stdout logging.
- **Automation Actions**:
  - **Browser Automation**: Fast and reliable web actions powered by Playwright (`open_browser`, `navigate`, `click`, `type`, `get_text`, `screenshot`).
  - **Desktop UI Automation**: Windows UI Automation support via `uiautomation` (`find_window`, `click`, `type`, `get_text`, `send_keys`).
  - **Excel & Office**: Native spreadsheet processing via `openpyxl` (`create`, `read_range`, `append_row`, `write_cell`).
  - **Control Flow**: Conditional branching (`logic.condition`), variable assignment, delays, and logging.
- **Live Real-Time Streaming**: WebSocket console for real-time log streaming and canvas node glowing while the robot is running.

---

## Quickstart

### 1. Setup Virtual Environment

```bash
# Python dependencies
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# Playwright browser
.\.venv\Scripts\python.exe -m playwright install chromium
```

### 2. Launch Studio Web App & Engine Server

**Option A (One-Click):**
Simply double-click [`start_app.bat`](file:///c:/Users/tkoma/apps/os-rpa-tool/start_app.bat). It automatically starts the server and opens `http://localhost:8000` in your default browser.

**Option B (Terminal):**
```bash
.\.venv\Scripts\python.exe -m os_rpa.cli server --port 8000
```
Open your browser at **`http://localhost:8000`**.

---

## CLI Usage

### Manage Work Queues
```bash
# List all queues and item metrics
.\.venv\Scripts\python.exe -m os_rpa.cli queue list

# Enqueue an item
.\.venv\Scripts\python.exe -m os_rpa.cli queue add "CustomerQueue" '{"account_id": "ACC-101", "action": "verify"}' --priority 5
```

### Run Workflows Headless
```bash
.\.venv\Scripts\python.exe -m os_rpa.cli run workflows/demo_queue_excel_workflow.json
```

---

## Running Automated Tests

```bash
.\.venv\Scripts\python.exe -m pytest tests -v
```

All 15 unit, integration, and E2E tests will run and verify:
- Queue item lifecycle and retries
- Dynamic expression evaluation
- Excel spreadsheet operations
- Python custom script sandboxing
- Playwright browser automation
- Desktop UI action drivers
- FastAPI REST & WebSocket endpoints

