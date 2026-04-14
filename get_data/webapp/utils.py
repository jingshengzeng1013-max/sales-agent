# -*- coding: utf-8 -*-
import json
import locale
import logging
import os
import queue
import socket
import subprocess
import sys
import time
from typing import Any, Optional, TextIO, Iterator
import contextlib

logger = logging.getLogger("get_data.webapp.utils")

def ensure_dir(path: Any) -> None:
    from pathlib import Path
    Path(path).mkdir(parents=True, exist_ok=True)

def decode_subprocess_bytes(raw: Optional[bytes]) -> str:
    if not raw:
        return ""
    if raw.startswith(b"\xef\xbb\xbf"):
        try:
            return raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            pass
    for enc in ("utf-8", "gb18030", "gbk", "cp936"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    pref = locale.getpreferredencoding(False) or ""
    if pref.lower() not in ("utf-8", "gbk", "gb18030", "cp936"):
        try:
            return raw.decode(pref)
        except (UnicodeDecodeError, LookupError):
            pass
    return raw.decode("utf-8", errors="replace")

def subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env

@contextlib.contextmanager
def tee_flow_stdout_stderr(
    q: queue.Queue,
    log_fp: Optional[TextIO],
    *,
    mirror_to_server_console: bool = True,
) -> Iterator[None]:
    outer_out = sys.stdout
    outer_err = sys.stderr

    class _Tee:
        def write(self, s: str) -> int:
            if not s:
                return 0
            try:
                q.put(s)
            except Exception:
                pass
            if log_fp is not None:
                log_fp.write(s)
                log_fp.flush()
            if mirror_to_server_console:
                try:
                    outer_out.write(s)
                except Exception:
                    pass
            return len(s)

        def flush(self) -> None:
            if log_fp is not None:
                log_fp.flush()
            if mirror_to_server_console:
                try:
                    outer_out.flush()
                except Exception:
                    pass

        def isatty(self) -> bool:
            return False

    tee = _Tee()
    sys.stdout = tee  # type: ignore[assignment]
    sys.stderr = tee  # type: ignore[assignment]
    try:
        yield
    finally:
        sys.stdout = outer_out
        sys.stderr = outer_err

def guess_lan_ipv4s() -> list[str]:
    found: set[str] = set()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 1))
            ip = s.getsockname()[0]
            if ip and not ip.startswith("127."):
                found.add(ip)
    except OSError:
        pass
    try:
        hn = socket.gethostname()
        for res in socket.getaddrinfo(hn, None, socket.AF_INET):
            ip = res[4][0]
            if ip and not ip.startswith("127."):
                found.add(ip)
    except OSError:
        pass
    return sorted(found)

def shorten_cell(val: Any, max_len: int = 12000) -> Any:
    if val is None:
        return None
    if isinstance(val, (bytes, memoryview)):
        return f"<binary {len(val)} bytes>"
    s = str(val).replace("\r\n", "\n")
    if len(s) > max_len:
        return s[: max_len - 1] + "…"
    return s

def sqlite_row_to_jsonable(row: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k in row.keys():
        v = row[k]
        if isinstance(v, (bytes, memoryview)):
            out[k] = f"<binary {len(v)} bytes>"
        else:
            out[k] = v
    return out

def terminate_listeners_on_port(port: int) -> None:
    """终止占用指定端口的进程（兼容 Windows 和 Unix）"""
    import platform
    if platform.system() == "Windows":
        try:
            out = subprocess.check_output(
                f"netstat -ano | findstr :{port}", shell=True, text=True
            )
            for line in out.splitlines():
                if "LISTENING" in line:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        if pid != "0":
                            logger.info(f"Kill process {pid} listening on port {port}")
                            subprocess.call(f"taskkill /F /PID {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            pass
    else:
        try:
            out = subprocess.check_output(
                f"lsof -i :{port} -t", shell=True, text=True
            )
            for pid in out.splitlines():
                pid = pid.strip()
                if pid:
                    logger.info(f"Kill process {pid} listening on port {port}")
                    subprocess.call(f"kill -9 {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            pass
