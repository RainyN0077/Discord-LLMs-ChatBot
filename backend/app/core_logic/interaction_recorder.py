import asyncio
import json
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..paths import DataPaths

logger = logging.getLogger(__name__)

INTERACTIONS_DIR = DataPaths.DATA_DIR / "interactions"

_write_locks: Dict[str, asyncio.Lock] = {}
_MAX_WRITE_LOCKS = 256


def _collect_date_dirs_sorted(bot_path: str) -> List[tuple]:
    """Collect date directories sorted by mtime (oldest first)."""
    date_dirs = []
    for date_dir in Path(bot_path).rglob("*-*-*"):
        if not date_dir.is_dir():
            continue
        try:
            mtime = date_dir.stat().st_mtime
        except OSError:
            mtime = 0
        date_dirs.append((mtime, date_dir))
    date_dirs.sort(key=lambda x: x[0])
    return date_dirs


def _delete_records_sync(
    bot_path: str, bot_id: str,
    guild_id: Optional[str], channel_id: Optional[str],
    member_id: Optional[str], date_str: Optional[str],
) -> int:
    """Synchronously delete matching interaction date directories."""
    deleted_count = 0
    for date_dir in Path(bot_path).rglob("*-*-*"):
        if not date_dir.is_dir():
            continue
        parts = date_dir.relative_to(Path(bot_path)).parts
        if len(parts) < 5:
            continue
        _gid, _cid, _mid, _date = parts[0], parts[2], parts[3], parts[4]
        if guild_id and _gid != guild_id:
            continue
        if channel_id and _cid != channel_id:
            continue
        if member_id and _mid != member_id:
            continue
        if date_str and _date != date_str:
            continue
        try:
            shutil.rmtree(str(date_dir))
            deleted_count += 1
        except OSError as e:
            logger.error(f"Failed to delete {date_dir}: {e}")
    return deleted_count


def _search_member_dirs(guild_path: str, member_id: str) -> List[Dict[str, Any]]:
    """Find all role/channel paths containing *member_id* (sync)."""
    results: List[Dict[str, Any]] = []
    for role_entry in os.scandir(guild_path):
        if not role_entry.is_dir():
            continue
        for channel_entry in os.scandir(role_entry.path):
            if not channel_entry.is_dir():
                continue
            member_dir = os.path.join(channel_entry.path, member_id)
            if os.path.isdir(member_dir):
                results.append({
                    "role_id": role_entry.name,
                    "channel_id": channel_entry.name,
                    "member_id": member_id,
                })
    return results


def _list_subdir_names(root: str, depth: int) -> List[str]:
    """Collect directory names at the given depth below *root* (sync)."""
    names = set()
    for entry in os.scandir(root):
        if not entry.is_dir():
            continue
        if depth <= 1:
            names.add(entry.name)
        else:
            names.update(_list_subdir_names(entry.path, depth - 1))
    return sorted(names)


def _calc_disk_usage(path: str) -> int:
    """Calculate total disk usage of a directory tree synchronously."""
    total = 0
    for root, _dirs, files in os.walk(path):
        for fname in files:
            try:
                total += os.path.getsize(os.path.join(root, fname))
            except OSError:
                pass
    return total


def _read_jsonl(path: str) -> List[Dict[str, Any]]:
    """Read all messages from a JSONL file synchronously."""
    messages = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                messages.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return messages


def _count_jsonl_lines(path: str) -> int:
    """Return the number of non-empty lines in a JSONL file (sync)."""
    with open(path, "r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def _append_jsonl(path: str, entry: dict) -> None:
    """Synchronous JSONL append — designed to run inside asyncio.to_thread()."""
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _get_lock(key: str) -> asyncio.Lock:
    if key not in _write_locks:
        # Evict oldest idle locks when at capacity to prevent unbounded growth.
        if len(_write_locks) >= _MAX_WRITE_LOCKS:
            for k in list(_write_locks.keys()):
                if not _write_locks[k].locked():
                    del _write_locks[k]
                    if len(_write_locks) < _MAX_WRITE_LOCKS:
                        break
        _write_locks[key] = asyncio.Lock()
    return _write_locks[key]


def _get_interactions_dir() -> Path:
    INTERACTIONS_DIR.mkdir(parents=True, exist_ok=True)
    return INTERACTIONS_DIR


def _get_bot_dir(bot_id: str) -> Path:
    return _get_interactions_dir() / bot_id


def _get_date_path(bot_id: str, guild_id: str, role_id: str, channel_id: str, member_id: str, date_str: str) -> Path:
    return _get_bot_dir(bot_id) / guild_id / role_id / channel_id / member_id / date_str


def _get_jsonl_path(bot_id: str, guild_id: str, role_id: str, channel_id: str, member_id: str, date_str: str) -> Path:
    return _get_date_path(bot_id, guild_id, role_id, channel_id, member_id, date_str) / "messages.jsonl"


async def _ensure_dir(path: Path) -> None:
    await asyncio.to_thread(lambda: path.mkdir(parents=True, exist_ok=True))


class InteractionRecorder:
    def __init__(self, base_dir: Optional[Path] = None):
        self._base_dir = base_dir or _get_interactions_dir()

    async def record_message(
        self,
        bot_id: str,
        guild_id: str,
        channel_id: str,
        member_id: str,
        member_name: str,
        role_id: str,
        content: str,
        message_id: str,
        attachments: List[str],
        is_bot_reply: bool,
        trigger_source: str,
    ) -> None:
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y-%m-%d")
        timestamp = now.isoformat()

        entry = {
            "timestamp": timestamp,
            "message_id": message_id,
            "author_id": member_id,
            "author_name": member_name,
            "content": content,
            "attachments": attachments,
            "is_bot_reply": is_bot_reply,
            "trigger_source": trigger_source,
        }

        jsonl_path = _get_jsonl_path(bot_id, guild_id, role_id, channel_id, member_id, date_str)
        await _ensure_dir(jsonl_path.parent)

        lock_key = f"{bot_id}:{guild_id}:{date_str}"
        lock = _get_lock(lock_key)
        async with lock:
            await asyncio.to_thread(
                _append_jsonl, str(jsonl_path), entry
            )

    async def record_images(
        self,
        bot_id: str,
        guild_id: str,
        channel_id: str,
        member_id: str,
        role_id: str,
        date_str: str,
        message_id: str,
        image_data_list: List[bytes],
    ) -> None:
        images_dir = _get_date_path(bot_id, guild_id, role_id, channel_id, member_id, date_str) / "images"
        await _ensure_dir(images_dir)
        for index, img_bytes in enumerate(image_data_list):
            img_path = images_dir / f"{message_id}_{index}.png"
            if not img_bytes:
                continue
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, lambda: img_path.write_bytes(img_bytes))

    async def get_disk_usage(self, bot_id: Optional[str] = None) -> int:
        target = _get_bot_dir(bot_id) if bot_id else _get_interactions_dir()
        exists = await asyncio.to_thread(lambda: target.exists())
        if not exists:
            return 0
        return await asyncio.to_thread(_calc_disk_usage, str(target))

    async def list_members(self, bot_id: str, guild_id: str) -> List[str]:
        guild_path = _get_bot_dir(bot_id) / guild_id
        exists = await asyncio.to_thread(lambda: guild_path.exists())
        if not exists:
            return []
        return await asyncio.to_thread(_list_subdir_names, str(guild_path), depth=3)

    async def get_member_info(self, bot_id: str, guild_id: str, member_id: str) -> List[Dict[str, Any]]:
        guild_path = _get_bot_dir(bot_id) / guild_id
        exists = await asyncio.to_thread(lambda: guild_path.exists())
        if not exists:
            return []
        return await asyncio.to_thread(_search_member_dirs, str(guild_path), member_id)

    async def list_tree(
        self,
        bot_id: str,
        guild_id: Optional[str] = None,
        role_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        member_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        results = []
        if not guild_id:
            bot_path = _get_bot_dir(bot_id)
            exists = await asyncio.to_thread(lambda: bot_path.exists())
            if not exists:
                return results
            for gid in sorted(p.name for p in bot_path.iterdir() if p.is_dir()):
                results.extend(await self.list_tree(bot_id, guild_id=gid))
            return results

        guild_path = _get_bot_dir(bot_id) / guild_id
        exists = await asyncio.to_thread(lambda: guild_path.exists())
        if not exists:
            return results

        for rid in sorted(p.name for p in guild_path.iterdir() if p.is_dir()):
            if role_id and rid != role_id:
                continue
            role_path = guild_path / rid
            for cid in sorted(p.name for p in role_path.iterdir() if p.is_dir()):
                if channel_id and cid != channel_id:
                    continue
                channel_path = role_path / cid
                for mid in sorted(p.name for p in channel_path.iterdir() if p.is_dir()):
                    if member_id and mid != member_id:
                        continue
                    member_path = channel_path / mid
                    for date_str in sorted(p.name for p in member_path.iterdir() if p.is_dir()):
                        jsonl_file = member_path / date_str / "messages.jsonl"
                        exists = await asyncio.to_thread(lambda: jsonl_file.exists())
                        if exists:
                            try:
                                msg_count = await asyncio.to_thread(_count_jsonl_lines, str(jsonl_file))
                            except Exception:
                                msg_count = 0
                        else:
                            msg_count = 0
                        results.append({
                            "guild_id": guild_id,
                            "role_id": rid,
                            "channel_id": cid,
                            "member_id": mid,
                            "date": date_str,
                            "message_count": msg_count,
                        })
        return results

    async def read_messages(
        self,
        bot_id: str,
        guild_id: str,
        role_id: str,
        channel_id: str,
        member_id: str,
        date_str: str,
    ) -> List[Dict[str, Any]]:
        jsonl_path = _get_jsonl_path(bot_id, guild_id, role_id, channel_id, member_id, date_str)
        exists = await asyncio.to_thread(lambda: jsonl_path.exists())
        if not exists:
            return []
        return await asyncio.to_thread(_read_jsonl, str(jsonl_path))

    async def delete_records(
        self,
        bot_id: str,
        guild_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        member_id: Optional[str] = None,
        date_str: Optional[str] = None,
    ) -> int:
        bot_path = _get_bot_dir(bot_id)
        exists = await asyncio.to_thread(lambda: bot_path.exists())
        if not exists:
            return 0

        return await asyncio.to_thread(
            _delete_records_sync,
            str(bot_path), bot_id, guild_id, channel_id, member_id, date_str,
        )

    async def prune_oldest(self, bot_id: str, max_bytes: int) -> int:
        current_usage = await self.get_disk_usage(bot_id)
        if current_usage <= max_bytes:
            return 0

        target = int(max_bytes * 0.8)
        pruned = 0

        bot_path = _get_bot_dir(bot_id)
        exists = await asyncio.to_thread(lambda: bot_path.exists())
        if not exists:
            return 0

        date_dirs = await asyncio.to_thread(_collect_date_dirs_sorted, str(bot_path))

        # Optimisation: track disk usage incrementally instead of re-scanning
        # the entire tree on every iteration (O(n²) -> O(n log n)).
        for _mtime, date_dir in date_dirs:
            if current_usage <= target:
                break
            try:
                # Measure the size of this single date directory before deletion
                dir_size = await asyncio.to_thread(_calc_disk_usage, str(date_dir))
                await asyncio.to_thread(shutil.rmtree, str(date_dir))
                current_usage -= dir_size
                pruned += 1
            except OSError as e:
                logger.error(f"Failed to prune {date_dir}: {e}")

        return pruned


_recorder_instance: Optional[InteractionRecorder] = None


def get_interaction_recorder() -> InteractionRecorder:
    global _recorder_instance
    if _recorder_instance is None:
        _recorder_instance = InteractionRecorder()
    return _recorder_instance
