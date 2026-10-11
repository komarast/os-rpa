import base64
import io
import os
from pathlib import Path
from typing import Optional


def capture_desktop_screenshot(save_path: Optional[str] = None) -> Optional[str]:
    """Captures an interactive desktop screenshot and returns either file path or base64 data URL.
    
    Uses Pillow ImageGrab if available, with graceful fallback.
    """
    try:
        from PIL import ImageGrab

        # Pillow grab
        img = ImageGrab.grab()
        if save_path:
            p = Path(save_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            img.save(p, format="PNG")
            return str(p)
        else:
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            return f"data:image/png;base64,{b64}"
    except Exception as e:
        # Fallback simulation or non-GUI environment
        return None
