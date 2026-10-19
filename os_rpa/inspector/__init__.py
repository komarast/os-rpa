"""Element inspector ("indicate on screen") for desktop (UI Automation) and web (Playwright) targets.

Pickers run in their own process (`python -m os_rpa.inspector ...`, see `service.py`) so the
Tk overlay and the Playwright browser never share threads with the API server.
"""
