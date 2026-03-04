from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ScreenCaptureResult:
    ok: bool
    path: str = ""
    backend: str = ""
    error: str = ""


def capture_screen_to_file(output_dir: str, prefix: str = "screen") -> ScreenCaptureResult:
    out_dir = str(output_dir or "").strip() or os.path.join("monitor", "screenshots")
    os.makedirs(out_dir, exist_ok=True)
    safe_prefix = _safe_name(prefix or "screen")
    ts = time.strftime("%Y%m%d_%H%M%S")
    out_path = os.path.abspath(os.path.join(out_dir, f"{safe_prefix}_{ts}.png"))

    err: Optional[str] = None
    try:
        from PIL import ImageGrab  # type: ignore

        img = ImageGrab.grab(all_screens=True)
        img.save(out_path, "PNG")
        return ScreenCaptureResult(ok=True, path=out_path, backend="pillow")
    except Exception as e:
        err = f"{type(e).__name__}: {e}"

    try:
        _capture_with_powershell(out_path)
        return ScreenCaptureResult(ok=True, path=out_path, backend="powershell")
    except Exception as e:
        err2 = f"{type(e).__name__}: {e}"
        if err:
            err2 = f"{err}; fallback={err2}"
        return ScreenCaptureResult(ok=False, error=err2)


def _capture_with_powershell(out_path: str) -> None:
    p = out_path.replace("'", "''")
    script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "Add-Type -AssemblyName System.Drawing; "
        "$bounds = [System.Windows.Forms.SystemInformation]::VirtualScreen; "
        "$bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height; "
        "$g = [System.Drawing.Graphics]::FromImage($bmp); "
        "$g.CopyFromScreen($bounds.Left, $bounds.Top, 0, 0, $bmp.Size); "
        "$bmp.Save('{0}', [System.Drawing.Imaging.ImageFormat]::Png); "
        "$g.Dispose(); "
        "$bmp.Dispose();"
    ).format(p)
    cp = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    if cp.returncode != 0:
        stderr = (cp.stderr or cp.stdout or "").strip()
        raise RuntimeError(stderr or "powershell_capture_failed")
    if not os.path.exists(out_path):
        raise RuntimeError("screenshot_not_created")


def _safe_name(name: str) -> str:
    out = []
    for ch in str(name):
        if ch.isalnum() or ch in {"-", "_"}:
            out.append(ch)
    return "".join(out) or "screen"
