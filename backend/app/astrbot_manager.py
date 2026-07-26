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
        self._bot_configs: Dict[str, Dict[str, Any]] = {}  # retained for auto-restart
        self._monitor_tasks: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start(self, bot_id: str, bot_config: Dict[str, Any]) -> None:
        """Start an AstrBot process for the given bot.

        Raises:
            AstrBotProcessError: If the bot is already running or startup fails.
        """
        self._bot_configs[bot_id] = bot_config

        async with self._lock:
            # Cancel any existing monitor task for this bot
            self._cancel_monitor(bot_id)

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
                self._bot_configs.pop(bot_id, None)
                raise

        # Start background monitor for this process (outside lock to avoid deadlock)
        self._monitor_tasks[bot_id] = asyncio.create_task(
            self._process_monitor(bot_id, astrbot_proc)
        )

    async def stop(self, bot_id: str) -> None:
        """Stop a running AstrBot process gracefully.

        Sends SIGTERM first, then SIGKILL after a timeout.
        """
        # Cancel monitor first so it won't trigger a restart after we stop
        self._cancel_monitor(bot_id)

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
            self._bot_configs.pop(bot_id, None)
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
        # Ensure all monitor tasks are cancelled
        for bot_id in list(self._monitor_tasks.keys()):
            self._cancel_monitor(bot_id)
        self._bot_configs.clear()
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

    # ------------------------------------------------------------------
    # Process monitor & auto-reconnect
    # ------------------------------------------------------------------

    MAX_RECONNECT_ATTEMPTS = 10
    RECONNECT_BASE_DELAY = 1.0
    RECONNECT_MAX_DELAY = 60.0

    def _cancel_monitor(self, bot_id: str) -> None:
        """Cancel the background monitor task for *bot_id* if one exists."""
        task = self._monitor_tasks.pop(bot_id, None)
        if task is not None and not task.done():
            task.cancel()

    async def _process_monitor(
        self, bot_id: str, astrbot_proc: AstrBotProcess,
    ) -> None:
        """Background task: watch the AstrBot subprocess and auto-restart on crash.

        Performs the monitoring loop *outside* ``self._lock`` so that concurrent
        ``stop()`` calls are not blocked.  The loop exits when:
        * the process is explicitly stopped (status != "running"), or
        * the max reconnect attempts are exhausted.
        """
        attempt = 0

        try:
            while attempt < self.MAX_RECONNECT_ATTEMPTS:
                # Check process health every HEALTH_CHECK_INTERVAL seconds
                try:
                    if astrbot_proc.process.returncode is not None:
                        # Process has exited — this is the crash / unexpected exit
                        attempt += 1
                        logger.error(
                            "AstrBot '%s' exited unexpectedly (returncode=%s, attempt %d/%d)",
                            bot_id, astrbot_proc.process.returncode,
                            attempt, self.MAX_RECONNECT_ATTEMPTS,
                        )

                        # Only auto-restart if the process is supposed to be running
                        if astrbot_proc.status != "running":
                            logger.info(
                                "AstrBot '%s' no longer in 'running' status, stopping monitor",
                                bot_id,
                            )
                            break

                        await self._reconnect_process(bot_id, attempt)
                        if attempt >= self.MAX_RECONNECT_ATTEMPTS:
                            break

                        # After reconnect, get the new process reference
                        async with self._lock:
                            new_proc = self._processes.get(bot_id)
                            if new_proc is None:
                                logger.info(
                                    "AstrBot '%s' removed during reconnect, stopping monitor",
                                    bot_id,
                                )
                                break
                            astrbot_proc = new_proc
                        continue

                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    attempt += 1
                    logger.error(
                        "AstrBot '%s' monitor error (attempt %d/%d): %s",
                        bot_id, attempt, self.MAX_RECONNECT_ATTEMPTS, exc,
                    )
                    if astrbot_proc.status == "running":
                        await self._reconnect_process(bot_id, attempt)
                    continue

                await asyncio.sleep(HEALTH_CHECK_INTERVAL)

        except asyncio.CancelledError:
            logger.debug("AstrBot '%s' monitor cancelled", bot_id)
            return

        # Exhausted retries
        if attempt >= self.MAX_RECONNECT_ATTEMPTS:
            logger.error(
                "AstrBot '%s' exceeded max reconnect attempts (%d). Marking as error.",
                bot_id, self.MAX_RECONNECT_ATTEMPTS,
            )
            async with self._lock:
                proc = self._processes.get(bot_id)
                if proc is not None:
                    proc.status = "error"
                    self._processes.pop(bot_id, None)
                self._bot_configs.pop(bot_id, None)
            self._cancel_monitor(bot_id)

    async def _reconnect_process(self, bot_id: str, attempt: int) -> None:
        """Reconnect an AstrBot subprocess with exponential backoff.

        Backoff sequence: 1s, 2s, 4s, 8s, … capped at ``RECONNECT_MAX_DELAY``.
        """
        delay = min(
            self.RECONNECT_BASE_DELAY * (2 ** (attempt - 1)),
            self.RECONNECT_MAX_DELAY,
        )

        logger.warning(
            "AstrBot '%s' reconnecting in %.1fs (attempt %d/%d) ...",
            bot_id, delay, attempt, self.MAX_RECONNECT_ATTEMPTS,
        )
        await asyncio.sleep(delay)

        bot_config = self._bot_configs.get(bot_id)
        if bot_config is None:
            logger.warning(
                "AstrBot '%s' no stored config for reconnect, giving up", bot_id,
            )
            return

        # Acquire lock, clean up old process, and re-start
        async with self._lock:
            # Remove the old (dead) process entry so start() doesn't see a conflict
            old_proc = self._processes.pop(bot_id, None)
            if old_proc is not None:
                await self._kill_process(bot_id, old_proc)

            try:
                write_astrbot_config(bot_id, bot_config)
                process = await self._spawn_process(bot_id)
                new_proc = AstrBotProcess(bot_id, process)
                new_proc.started_at = asyncio.get_event_loop().time()
                self._processes[bot_id] = new_proc
                await self._wait_for_ready(bot_id, new_proc)
                new_proc.status = "running"
                logger.info(
                    "AstrBot '%s' reconnected successfully (attempt %d, PID %d)",
                    bot_id, attempt, process.pid,
                )
            except Exception:
                logger.error(
                    "AstrBot '%s' reconnect attempt %d failed",
                    bot_id, attempt, exc_info=True,
                )
                self._processes.pop(bot_id, None)
                raise

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
