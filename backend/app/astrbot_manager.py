"""AstrBot Subprocess Manager.

Manages AstrBot instances as asyncio subprocesses, one per Discord bot account.
Handles spawning, health-checking, stopping, and restarting AstrBot processes.

Each AstrBot instance runs as:
    astrbot run --config data/bots/{bot_id}/astrbot/config.yml
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import aiohttp

from .astrbot_config_gen import generate_astrbot_config, write_astrbot_config, remove_astrbot_config
from .config_cache import get_bot_dir

logger = logging.getLogger(__name__)

# Default timeout values (seconds)
PROCESS_START_TIMEOUT = 60
PROCESS_STOP_TIMEOUT = 30
HEALTH_CHECK_INTERVAL = 5
HEALTH_CHECK_MAX_RETRIES = 12  # 60s total with 5s interval


class AstrBotProcessError(Exception):
    """Raised when an AstrBot subprocess operation fails."""
    pass


class AstrBotProcess:
    """Represents a single running AstrBot subprocess."""

    def __init__(self, bot_id: str, process: asyncio.subprocess.Process):
        self.bot_id = bot_id
        self.process = process
        self.status: str = "starting"
        self.started_at: Optional[float] = None
        self._health_check_task: Optional[asyncio.Task] = None

    @property
    def pid(self) -> Optional[int]:
        return self.process.pid if self.process else None


class AstrBotProcessManager:
    """Manages the lifecycle of AstrBot subprocesses.

    Usage:
        manager = AstrBotProcessManager()
        await manager.start("bot_01", bot_config)
        await manager.stop("bot_01")
    """

    def __init__(self):
        self._processes: Dict[str, AstrBotProcess] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start(self, bot_id: str, bot_config: Dict[str, Any]) -> None:
        """Start an AstrBot process for the given bot.

        Raises:
            AstrBotProcessError: If the bot is already running or startup fails.
        """
        async with self._lock:
            if bot_id in self._processes:
                existing = self._processes[bot_id]
                if existing.process is not None and existing.process.returncode is None:
                    raise AstrBotProcessError(f"Bot '{bot_id}' is already running (PID {existing.pid})")
                # Clean up stale entry
                del self._processes[bot_id]

            # Generate config before spawning
            write_astrbot_config(bot_id, bot_config)

            process = await self._spawn_process(bot_id)
            astrbot_proc = AstrBotProcess(bot_id, process)
            astrbot_proc.started_at = asyncio.get_event_loop().time()
            self._processes[bot_id] = astrbot_proc

            try:
                await self._wait_for_ready(bot_id, astrbot_proc)
                astrbot_proc.status = "running"
                logger.info("AstrBot '%s' started successfully (PID %d)", bot_id, process.pid)
            except Exception:
                # Startup failed — clean up
                await self._kill_process(bot_id, astrbot_proc)
                del self._processes[bot_id]
                raise

    async def stop(self, bot_id: str) -> None:
        """Stop a running AstrBot process gracefully.

        Sends SIGTERM first, then SIGKILL after a timeout.
        """
        async with self._lock:
            astrbot_proc = self._processes.get(bot_id)
            if not astrbot_proc or not astrbot_proc.process:
                return

            astrbot_proc.status = "stopping"
            process = astrbot_proc.process

            try:
                if sys.platform == "win32":
                    process.terminate()
                else:
                    process.send_signal(signal.SIGTERM)

                try:
                    await asyncio.wait_for(process.wait(), timeout=PROCESS_STOP_TIMEOUT)
                except asyncio.TimeoutError:
                    logger.warning("AstrBot '%s' did not stop gracefully, force killing", bot_id)
                    if sys.platform == "win32":
                        process.kill()
                    else:
                        process.send_signal(signal.SIGKILL)
                    await process.wait()
            except ProcessLookupError:
                pass  # Already dead
            except Exception as e:
                logger.error("Error stopping AstrBot '%s': %s", bot_id, e, exc_info=True)

            astrbot_proc.status = "stopped"
            del self._processes[bot_id]
            # Keep config files (they'll be regenerated on next start)
            logger.info("AstrBot '%s' stopped", bot_id)

    async def restart(self, bot_id: str, bot_config: Dict[str, Any]) -> None:
        """Restart an AstrBot process (stop + regenerate config + start)."""
        await self.stop(bot_id)
        # Brief wait for port release
        await asyncio.sleep(1)
        await self.start(bot_id, bot_config)

    def is_running(self, bot_id: str) -> bool:
        """Check if an AstrBot process is running."""
        proc = self._processes.get(bot_id)
        if not proc or not proc.process:
            return False
        return proc.process.returncode is None and proc.status == "running"

    def get_status(self, bot_id: str) -> Optional[Dict[str, Any]]:
        """Get status info for a bot's AstrBot process."""
        proc = self._processes.get(bot_id)
        if not proc:
            return None
        return {
            "bot_id": bot_id,
            "status": proc.status,
            "pid": proc.pid,
            "started_at": proc.started_at,
            "returncode": proc.process.returncode if proc.process else None,
        }

    def list_all(self) -> Dict[str, Dict[str, Any]]:
        """Return status dicts for all managed processes."""
        return {
            bot_id: {
                "status": proc.status,
                "pid": proc.pid,
                "started_at": proc.started_at,
            }
            for bot_id, proc in self._processes.items()
        }

    async def shutdown(self) -> None:
        """Stop all running AstrBot processes."""
        bot_ids = list(self._processes.keys())
        for bot_id in bot_ids:
            try:
                await self.stop(bot_id)
            except Exception as e:
                logger.error("Error shutting down AstrBot '%s': %s", bot_id, e, exc_info=True)
        logger.info("All AstrBot processes shut down")

    async def health_check(self, bot_id: str) -> bool:
        """Check if the AstrBot instance is healthy.

        Uses process liveness check since multiple instances can't share a port.
        """
        proc = self._processes.get(bot_id)
        if not proc or proc.status != "running":
            return False

        if proc.process and proc.process.returncode is not None:
            return False

        return True

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _spawn_process(self, bot_id: str) -> asyncio.subprocess.Process:
        """Spawn an AstrBot subprocess."""
        bot_dir = get_bot_dir(bot_id)
        config_dir = bot_dir / "astrbot"
        log_dir = bot_dir / "astrbot" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        log_file = open(str(log_dir / "astrbot.log"), "a", encoding="utf-8")

        cmd = [
            sys.executable, "-m", "astrbot", "run",
            "--config", str(config_dir / "config.yml"),
        ]

        logger.info("Spawning AstrBot '%s': %s", bot_id, " ".join(cmd))

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=log_file,
            stderr=asyncio.subprocess.STDOUT,
        )
        return process

    async def _wait_for_ready(self, bot_id: str, astrbot_proc: AstrBotProcess) -> None:
        """Wait for the AstrBot process to report readiness.

        Since multiple AstrBot instances can't share a single health port,
        we check process liveness (not exited) plus log-based readiness markers.
        """
        import time
        log_path = get_bot_dir(bot_id) / "astrbot" / "logs" / "astrbot.log"

        for attempt in range(1, HEALTH_CHECK_MAX_RETRIES + 1):
            # Check if process crashed
            if astrbot_proc.process.returncode is not None:
                raise AstrBotProcessError(
                    f"AstrBot '{bot_id}' exited prematurely with code {astrbot_proc.process.returncode}"
                )

            # Check log file for a "ready" marker (AstrBot outputs when initialized)
            try:
                if log_path.exists():
                    log_content = log_path.read_text(encoding="utf-8", errors="replace")
                    if "AstrBot is running" in log_content or "started" in log_content.lower():
                        logger.debug("AstrBot '%s' ready (detected via log marker, attempt %d)", bot_id, attempt)
                        return
            except Exception:
                pass

            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

        raise AstrBotProcessError(
            f"AstrBot '{bot_id}' did not become ready within "
            f"{HEALTH_CHECK_MAX_RETRIES * HEALTH_CHECK_INTERVAL}s"
        )

    async def _kill_process(self, bot_id: str, astrbot_proc: AstrBotProcess) -> None:
        """Forcefully terminate an AstrBot process."""
        try:
            if astrbot_proc.process and astrbot_proc.process.returncode is None:
                if sys.platform == "win32":
                    astrbot_proc.process.kill()
                else:
                    astrbot_proc.process.send_signal(signal.SIGKILL)
                await asyncio.wait_for(astrbot_proc.process.wait(), timeout=5)
        except Exception:
            pass
