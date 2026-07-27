#!/usr/bin/env python3
"""
Unified launcher for Discord-LLMs-ChatBot local development.

Usage:
  python run.py                 Start backend + frontend (foreground, Ctrl+C to stop)
  python run.py start           Same as above
  python run.py start --background   Detached mode (logs to .local-run/)
  python run.py start --backend-only
  python run.py start --frontend-only
  python run.py stop            Stop background processes
  python run.py restart         Restart background processes
  python run.py status          Show process / port status
  python run.py install         Install/sync dependencies only

Environment variables:
  BACKEND_PORT   default 8093
  FRONTEND_PORT  default 8094
  REDIS_HOST     default localhost
  REDIS_PORT     default 6379
"""

import argparse
import asyncio
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

try:
    import httpx
except ImportError:
    httpx = None

ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"
RUN_DIR = ROOT_DIR / ".local-run"
LOG_DIR = RUN_DIR / "logs"

BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8093"))
FRONTEND_PORT = int(os.getenv("FRONTEND_PORT", "8094"))
VITE_PROXY = os.getenv("VITE_API_PROXY_TARGET", f"http://localhost:{BACKEND_PORT}")

IS_WINDOWS = os.name == "nt"
PY_VER = sys.version_info


def _check_python_compat() -> None:
    if PY_VER >= (3, 14):
        _log("compat", f"Python {PY_VER.major}.{PY_VER.minor} detected – requires websockets>=15.0", colour="Y")
        _log("compat", "If you see 'proxy' keyword error, run: pip install 'websockets>=15.0'", colour="Y")

# ── tiny colour helpers ──────────────────────────────────────────────
_COL = {
    "R": "\033[91m", "G": "\033[92m", "Y": "\033[93m",
    "B": "\033[94m", "C": "\033[96m", "W": "\033[97m",
    "D": "\033[90m", "Z": "\033[0m",
}

def c(code: str, text: str) -> str:
    return f"{_COL.get(code, '')}{text}{_COL['Z']}"


def _log(tag: str, msg: str, *, colour: str = "C") -> None:
    print(f"{c(colour, f'[{tag}]')} {msg}")


def _die(msg: str) -> None:
    print(f"{c('R', '[ERROR]')} {msg}", file=sys.stderr)
    sys.exit(1)


# ── filesystem helpers ───────────────────────────────────────────────
def _pid_file(name: str) -> Path:
    return RUN_DIR / f"{name}.pid"


def _read_pid(name: str) -> int | None:
    pf = _pid_file(name)
    if not pf.exists():
        return None
    try:
        return int(pf.read_text().strip())
    except (ValueError, OSError):
        return None


def _write_pid(name: str, pid: int) -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    _pid_file(name).write_text(str(pid))


def _clear_pid(name: str) -> None:
    pf = _pid_file(name)
    if pf.exists():
        pf.unlink()


# ── tool discovery ───────────────────────────────────────────────────
def _find_python() -> str:
    for cmd in ("python3", "python", "py"):
        try:
            if subprocess.run([cmd, "--version"], capture_output=True, timeout=5).returncode == 0:
                return cmd
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
    for p in Path.home().glob("scoop/apps/python/current/python.exe"):
        return str(p)
    _die("Python 3.10+ not found.")


def _find_npm() -> str | None:
    for cmd in ("npm", "npm.cmd"):
        try:
            if subprocess.run([cmd, "--version"], capture_output=True, timeout=5).returncode == 0:
                return cmd
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
    return None


def _venv_python() -> Path:
    if IS_WINDOWS:
        return BACKEND_DIR / ".venv" / "Scripts" / "python.exe"
    return BACKEND_DIR / ".venv" / "bin" / "python"


def _ensure_venv() -> Path:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    vp = _venv_python()
    if not vp.exists():
        py = _find_python()
        _log("venv", f"Creating {BACKEND_DIR / '.venv'}")
        subprocess.run([py, "-m", "venv", str(BACKEND_DIR / ".venv")], check=True)
    return vp


# ── port check ───────────────────────────────────────────────────────
def _port_open(port: int) -> bool:
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.4)
    try:
        s.connect(("127.0.0.1", port))
        return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False
    finally:
        s.close()


def _is_alive(pid: int) -> bool:
    try:
        if IS_WINDOWS:
            r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True)
            return str(pid) in r.stdout
        os.kill(pid, 0)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def _kill(pid: int) -> bool:
    """Kill a process by PID. Returns True if the process was killed."""
    if not _is_alive(pid):
        return False
    try:
        if IS_WINDOWS:
            # /T kills the entire process tree (critical for uvicorn --reload)
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
        else:
            os.kill(pid, signal.SIGTERM)
            time.sleep(0.3)
            if _is_alive(pid):
                os.kill(pid, signal.SIGKILL)
        return True
    except OSError:
        return False


def _kill_port(port: int) -> bool:
    """Kill whichever process is listening on the given port. Returns True if a process was killed."""
    if not _port_open(port):
        return False
    try:
        if IS_WINDOWS:
            # Find PID listening on the port
            r = subprocess.run(
                ["cmd.exe", "/c", f'netstat -ano | findstr ":{port} " | findstr "LISTENING"'],
                capture_output=True, text=True,
            )
            if r.returncode == 0 and r.stdout.strip():
                lines = r.stdout.strip().splitlines()
                killed_pids = set()
                for line in lines:
                    parts = line.strip().split()
                    if parts:
                        pid_str = parts[-1]
                        if pid_str.isdigit() and pid_str not in killed_pids:
                            killed_pids.add(pid_str)
                            subprocess.run(
                                ["taskkill", "/F", "/T", "/PID", pid_str],
                                capture_output=True,
                            )
                return len(killed_pids) > 0
        else:
            r = subprocess.run(
                ["lsof", "-ti", f":{port}"], capture_output=True, text=True
            )
            if r.returncode == 0 and r.stdout.strip():
                for pid_str in r.stdout.strip().splitlines():
                    pid = int(pid_str)
                    os.kill(pid, signal.SIGTERM)
                    time.sleep(0.3)
                    if _is_alive(pid):
                        os.kill(pid, signal.SIGKILL)
                return True
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    return False


async def _wait_for_backend(timeout: float = 60.0) -> bool:
    """Wait for backend HTTP server to respond (application ready)."""
    url = f"http://127.0.0.1:{BACKEND_PORT}/"
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        for proc in CHILD_PROCS:
            if proc.returncode is not None and proc.returncode != 0:
                return False
        if _port_open(BACKEND_PORT):
            if httpx:
                try:
                    async with httpx.AsyncClient(timeout=1.0) as client:
                        r = await client.get(url)
                        if r.status_code < 500:
                            return True
                except Exception:
                    pass
            else:
                return True
        await asyncio.sleep(0.5)

    _log("backend", f"Timed out after {timeout:.0f}s", colour="Y")
    return False


def _wait_for_backend_sync(timeout: float = 60.0) -> bool:
    """Synchronous version for background mode."""
    url = f"http://127.0.0.1:{BACKEND_PORT}/"
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if not _port_open(BACKEND_PORT):
            time.sleep(0.5)
            continue
        if httpx:
            try:
                import httpx as _httpx
                r = _httpx.get(url, timeout=2.0)
                if r.status_code < 500:
                    return True
            except Exception:
                pass
            time.sleep(0.5)
            continue
        return True

    _log("backend", f"Timed out after {timeout:.0f}s", colour="Y")
    return False


# ── commands ─────────────────────────────────────────────────────────
def do_install() -> None:
    _check_python_compat()
    vp = _ensure_venv()
    _log("1/3", "Upgrading pip / setuptools / wheel")
    subprocess.run([str(vp), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"], check=True)
    req = BACKEND_DIR / "requirements.txt"
    if req.exists():
        _log("2/3", f"Installing {req}")
        subprocess.run([str(vp), "-m", "pip", "install", "-r", str(req)], check=True)
    if _find_npm():
        _log("3/3", "npm install")
        subprocess.run(["cmd.exe", "/c", "npm", "install"], cwd=str(FRONTEND_DIR), check=True) if IS_WINDOWS else subprocess.run(["npm", "install"], cwd=str(FRONTEND_DIR), check=True)
    print(c("G", "\nAll dependencies installed."))


def do_status() -> None:
    bp = _read_pid("backend")
    fp = _read_pid("frontend")
    ba = bp and _is_alive(bp)
    fa = fp and _is_alive(fp)
    bu = _port_open(BACKEND_PORT)
    fu = _port_open(FRONTEND_PORT)
    print(f"  Backend  : {'RUNNING' if ba else 'STOPPED'}  (PID {bp or '-'}, port {BACKEND_PORT} {'open' if bu else 'free'})")
    print(f"  Frontend : {'RUNNING' if fa else 'STOPPED'}  (PID {fp or '-'}, port {FRONTEND_PORT} {'open' if fu else 'free'})")
    if not ba and not fa:
        print(f"\n  Run:  python run.py")


def do_stop() -> None:
    """Stop all managed processes. Falls back to port-based killing if PID is stale."""
    stopped = 0

    # Phase 1: kill by tracked PID
    for name in ("backend", "frontend"):
        pid = _read_pid(name)
        if pid:
            if _kill(pid):
                _log("stop", f"{name} (PID {pid})", colour="G")
                stopped += 1
            elif _is_alive(pid):
                _log("stop", f"{name} PID {pid} — failed to kill, trying port fallback", colour="Y")
            else:
                _log("stop", f"{name} PID {pid} already gone (stale pid file)", colour="Y")
            _clear_pid(name)

    # Phase 2: port-based fallback — kill anything still listening
    port_map = {"backend": BACKEND_PORT, "frontend": FRONTEND_PORT}
    for name, port in port_map.items():
        if _port_open(port):
            _log("stop", f"Port {port} ({name}) still occupied — killing by port", colour="Y")
            if _kill_port(port):
                _log("stop", f"{name} killed by port {port}", colour="G")
                stopped += 1
                # Wait for port to release — retry up to 3s
                for _ in range(30):
                    if not _port_open(port):
                        break
                    time.sleep(0.1)
                else:
                    _log("stop", f"Port {port} still occupied after kill — may need manual intervention", colour="R")
            else:
                _log("stop", f"Could not free port {port} ({name})", colour="R")
            _clear_pid(name)


# ═══════════════════════════════════════════════════════════════════════
#  foreground mode  (async, real-time log interleaving, Ctrl+C ⇒ stop)
# ═══════════════════════════════════════════════════════════════════════
CHILD_PROCS: list[asyncio.subprocess.Process] = []


async def _stream(proc: asyncio.subprocess.Process, tag: str, colour: str) -> None:
    prefix = c(colour, f"[{tag}] ")
    prefix_bytes = prefix.encode("utf-8", errors="replace")
    buf = b""
    while True:
        try:
            line = await proc.stdout.readline()
        except (ValueError, asyncio.exceptions.LimitOverrunError):
            chunk = await proc.stdout.read(65536)
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                try:
                    sys.stdout.buffer.write(prefix_bytes + line + b"\n")
                    sys.stdout.buffer.flush()
                except RuntimeError:
                    pass
            continue
        if not line:
            break
        try:
            sys.stdout.buffer.write(prefix_bytes + line)
            sys.stdout.buffer.flush()
        except RuntimeError:
            pass


async def _run_foreground(procs: list[tuple[str, list[str], Path, dict]]) -> None:
    global CHILD_PROCS
    CHILD_PROCS = []
    tasks: list[asyncio.Task] = []

    backend_entry = None
    frontend_entry = None
    for entry in procs:
        if entry[0] == "backend":
            backend_entry = entry
        elif entry[0] == "frontend":
            frontend_entry = entry

    if backend_entry:
        tag, args, cwd, env_extra = backend_entry
        env = dict(os.environ, **env_extra)
        proc = await asyncio.create_subprocess_exec(
            *args,
            cwd=cwd, env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        CHILD_PROCS.append(proc)
        _log(tag, f"Started (PID {proc.pid})", colour="G")
        tasks.append(asyncio.create_task(_stream(proc, tag, "B")))

        _log("launcher", "Waiting for backend to become ready...", colour="C")
        ready = await _wait_for_backend()
        if ready:
            _log("backend", "Ready – application fully started", colour="G")
        else:
            _log("backend", "Not responding yet – starting frontend anyway", colour="Y")

    if frontend_entry:
        tag, args, cwd, env_extra = frontend_entry
        env = dict(os.environ, **env_extra)
        proc = await asyncio.create_subprocess_exec(
            *args,
            cwd=cwd, env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        CHILD_PROCS.append(proc)
        _log(tag, f"Started (PID {proc.pid})", colour="G")
        tasks.append(asyncio.create_task(_stream(proc, tag, "W")))

    if not tasks:
        return

    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in pending:
            t.cancel()
    except asyncio.CancelledError:
        for t in tasks:
            t.cancel()


_shutting_down = False
_SIGINT_FORCE_TIMEOUT = 5  # seconds before force-kill after first SIGINT


def _on_sigint(signum, frame):
    global _shutting_down
    if _shutting_down:
        # Second Ctrl+C: immediate force-kill
        print(f"\n{c('R', 'Force quitting...')}")
        for p in CHILD_PROCS:
            try:
                if IS_WINDOWS:
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
                else:
                    p.kill()
            except Exception:
                pass
        os._exit(1)

    _shutting_down = True
    print(f"\n{c('Y', 'Shutting down... (press Ctrl+C again to force)')}")

    # Phase 1: graceful terminate (SIGTERM / CTRL_BREAK_EVENT)
    for p in CHILD_PROCS:
        try:
            if IS_WINDOWS:
                # Send CTRL_BREAK_EVENT to the process group (uvicorn handles this)
                try:
                    p.send_signal(signal.CTRL_BREAK_EVENT)
                except Exception:
                    subprocess.run(["taskkill", "/PID", str(p.pid)], capture_output=True)
            else:
                p.terminate()
        except Exception:
            pass

    # Phase 2: after timeout, force kill
    time.sleep(_SIGINT_FORCE_TIMEOUT)
    for p in CHILD_PROCS:
        try:
            if IS_WINDOWS:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
            else:
                p.kill()
        except Exception:
            pass

    # Also clean up via port as final fallback
    _kill_port(BACKEND_PORT)
    _kill_port(FRONTEND_PORT)

    os._exit(0)


def do_start_foreground(backend_only: bool, frontend_only: bool) -> None:
    _check_python_compat()
    signal.signal(signal.SIGINT, _on_sigint)

    vp = _ensure_venv()
    procs: list[tuple[str, list[str], Path, dict]] = []

    if not frontend_only:
        procs.append((
            "backend",
            [str(vp), "-m", "uvicorn", "app.main:app",
             "--host", "0.0.0.0", "--port", str(BACKEND_PORT),
             "--reload",
             "--reload-dir", "app",
             "--reload-dir", "astrbot_stars",
             "--reload-dir", "plugins",
             "--no-use-colors"],
            BACKEND_DIR,
            {"REDIS_HOST": os.getenv("REDIS_HOST", "localhost"),
             "REDIS_PORT": os.getenv("REDIS_PORT", "6379"),
             "FAIL_ON_REDIS_ERROR": os.getenv("FAIL_ON_REDIS_ERROR", "false"),
             "DISABLE_ENCRYPTION": os.getenv("DISABLE_ENCRYPTION", "1")},
        ))

    if not backend_only:
        npm = _find_npm()
        if npm:
            procs.append((
                "frontend",
                [npm, "run", "dev", "--", "--host", "0.0.0.0", "--port", str(FRONTEND_PORT)],
                FRONTEND_DIR,
                {"VITE_API_PROXY_TARGET": VITE_PROXY},
            ))
        else:
            _log("frontend", "npm not found", colour="Y")

    print(c("Y", "Press Ctrl+C to stop all processes.\n"))

    try:
        asyncio.run(_run_foreground(procs))
    except KeyboardInterrupt:
        pass
    finally:
        _on_sigint(None, None)


# ═══════════════════════════════════════════════════════════════════════
#  background mode  (detached, logs to files, pid-file management)
# ═══════════════════════════════════════════════════════════════════════
def _spawn_bg(name: str, args: list[str], cwd: Path, env_extra: dict, port: int) -> subprocess.Popen | None:
    kwargs: dict = {"cwd": str(cwd), "env": dict(os.environ, **env_extra)}
    if IS_WINDOWS:
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS
        kwargs["startupinfo"] = subprocess.STARTUPINFO(
            dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0,
        )
    else:
        kwargs["start_new_session"] = True

    lf = LOG_DIR / f"{name}.log"
    with open(lf, "a", encoding="utf-8") as f:
        f.write(f"\n--- Started {time.ctime()} ---\n")
        proc = subprocess.Popen(args, stdout=f, stderr=subprocess.STDOUT, **kwargs)

    _write_pid(name, proc.pid)
    _log(name, f"Started (PID {proc.pid}, logs: {lf})", colour="G")

    for _ in range(30):
        time.sleep(0.1)
        if _port_open(port):
            return proc
    _log(name, f"Port {port} not open yet – check logs", colour="Y")
    return proc


def do_start_background(backend_only: bool, frontend_only: bool) -> None:
    do_stop()

    # Wait for ports to actually release before starting new processes
    ports_to_check = []
    if not frontend_only:
        ports_to_check.append(("backend", BACKEND_PORT))
    if not backend_only:
        ports_to_check.append(("frontend", FRONTEND_PORT))

    for name, port in ports_to_check:
        for _ in range(50):  # up to 5 seconds
            if not _port_open(port):
                break
            time.sleep(0.1)
        else:
            _log(name, f"Port {port} still occupied — starting anyway, may fail", colour="Y")

    vp = _ensure_venv()

    if not frontend_only:
        _spawn_bg("backend", [
            str(vp), "-m", "uvicorn", "app.main:app",
            "--host", "0.0.0.0", "--port", str(BACKEND_PORT),
            "--reload",
            "--reload-dir", "app",
            "--reload-dir", "astrbot_stars",
            "--reload-dir", "plugins",
            "--no-use-colors",
        ], BACKEND_DIR, {
            "REDIS_HOST": os.getenv("REDIS_HOST", "localhost"),
            "REDIS_PORT": os.getenv("REDIS_PORT", "6379"),
            "FAIL_ON_REDIS_ERROR": os.getenv("FAIL_ON_REDIS_ERROR", "false"),
            "DISABLE_ENCRYPTION": os.getenv("DISABLE_ENCRYPTION", "1"),
        }, BACKEND_PORT)

    backend_started = frontend_only or _wait_for_backend_sync()
    if backend_started:
        _log("backend", "Ready – application fully started", colour="G")
    elif not frontend_only:
        _log("backend", "Not responding yet – starting frontend anyway", colour="Y")

    if not backend_only:
        npm = _find_npm()
        if npm:
            _spawn_bg("frontend", [
                npm, "run", "dev", "--", "--host", "0.0.0.0", "--port", str(FRONTEND_PORT),
            ], FRONTEND_DIR, {"VITE_API_PROXY_TARGET": VITE_PROXY}, FRONTEND_PORT)
        else:
            _log("frontend", "npm not found", colour="Y")

    time.sleep(1.5)
    print()
    print(c("G", "Startup complete."))
    print(f"  Backend:  http://localhost:{BACKEND_PORT}")
    print(f"  Frontend: http://localhost:{FRONTEND_PORT}")
    print(f"  Logs:     {LOG_DIR}")
    print(f"  Status:   python run.py status")
    print(f"  Stop:     python run.py stop")


# ── CLI ──────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="Discord-LLMs-ChatBot Local Launcher")
    sub = parser.add_subparsers(dest="command")

    p_start = sub.add_parser("start", help="Start services (default: foreground)")
    p_start.add_argument("--backend-only", action="store_true")
    p_start.add_argument("--frontend-only", action="store_true")
    p_start.add_argument("--background", action="store_true", help="Detached mode (logs → .local-run/)")

    sub.add_parser("stop", help="Stop background processes")
    sub.add_parser("restart", help="Restart background processes")
    sub.add_parser("status", help="Show status")
    sub.add_parser("install", help="Install/sync dependencies")

    args = parser.parse_args()

    if args.command == "install":
        do_install()
    elif args.command == "stop":
        do_stop()
    elif args.command == "status":
        do_status()
    elif args.command == "restart":
        do_stop()
        time.sleep(1)
        do_start_background(False, False)
    elif args.command == "start":
        if args.background:
            do_start_background(args.backend_only, args.frontend_only)
        else:
            do_start_foreground(args.backend_only, args.frontend_only)
    else:
        do_start_foreground(False, False)


if __name__ == "__main__":
    main()
