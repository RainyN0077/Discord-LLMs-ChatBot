import asyncio
import json
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config_cache import DATA_DIR

logger = logging.getLogger(__name__)

INTERACTIONS_DIR = DATA_DIR / "interactions"

_write_locks: Dict[str, asyncio.Lock] = {}


def _get_lock(key: str) -> asyncio.Lock:
    if key not in _write_locks:
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


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


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
        _ensure_dir(jsonl_path.parent)

        lock_key = f"{bot_id}:{guild_id}:{date_str}"
        lock = _get_lock(lock_key)
        async with lock:
            with open(jsonl_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

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
        _ensure_dir(images_dir)
        for index, img_bytes in enumerate(image_data_list):
            img_path = images_dir / f"{message_id}_{index}.png"
            if not img_bytes:
                continue
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, lambda: img_path.write_bytes(img_bytes))

    def get_disk_usage(self, bot_id: Optional[str] = None) -> int:
        target = _get_bot_dir(bot_id) if bot_id else _get_interactions_dir()
        if not target.exists():
            return 0
        total = 0
        for root, _dirs, files in os.walk(str(target)):
            for fname in files:
                try:
                    total += os.path.getsize(os.path.join(root, fname))
                except OSError:
                    pass
        return total

    def list_members(self, bot_id: str, guild_id: str) -> List[str]:
        guild_path = _get_bot_dir(bot_id) / guild_id
        if not guild_path.exists():
            return []
        members = set()
        for role_dir in guild_path.iterdir():
            if not role_dir.is_dir():
                continue
            for channel_dir in role_dir.iterdir():
                if not channel_dir.is_dir():
                    continue
                for member_dir in channel_dir.iterdir():
                    if not member_dir.is_dir():
                        continue
                    members.add(member_dir.name)
        return sorted(members)

    def get_member_info(self, bot_id: str, guild_id: str, member_id: str) -> List[Dict[str, Any]]:
        guild_path = _get_bot_dir(bot_id) / guild_id
        if not guild_path.exists():
            return []
        results = []
        for role_dir in guild_path.iterdir():
            if not role_dir.is_dir():
                continue
            for channel_dir in role_dir.iterdir():
                if not channel_dir.is_dir():
                    continue
                member_dir = channel_dir / member_id
                if not member_dir.is_dir():
                    continue
                results.append({
                    "role_id": role_dir.name,
                    "channel_id": channel_dir.name,
                    "member_id": member_id,
                })
        return results

    def list_tree(
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
            if not bot_path.exists():
                return results
            for gid in sorted(p.name for p in bot_path.iterdir() if p.is_dir()):
                results.extend(self.list_tree(bot_id, guild_id=gid))
            return results

        guild_path = _get_bot_dir(bot_id) / guild_id
        if not guild_path.exists():
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
                        if jsonl_file.exists():
                            try:
                                msg_count = sum(1 for _ in open(jsonl_file, "r", encoding="utf-8"))
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

    def read_messages(
        self,
        bot_id: str,
        guild_id: str,
        role_id: str,
        channel_id: str,
        member_id: str,
        date_str: str,
    ) -> List[Dict[str, Any]]:
        jsonl_path = _get_jsonl_path(bot_id, guild_id, role_id, channel_id, member_id, date_str)
        if not jsonl_path.exists():
            return []
        messages = []
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    messages.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return messages

    def delete_records(
        self,
        bot_id: str,
        guild_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        member_id: Optional[str] = None,
        date_str: Optional[str] = None,
    ) -> int:
        deleted_count = 0

        def _should_delete(path: Path) -> bool:
            parts = path.relative_to(_get_bot_dir(bot_id)).parts
            if len(parts) < 5:
                return False
            _gid, _rid, _cid, _mid, _date = parts[0], parts[1], parts[2], parts[3], parts[4]
            if guild_id and _gid != guild_id:
                return False
            if channel_id and _cid != channel_id:
                return False
            if member_id and _mid != member_id:
                return False
            if date_str and _date != date_str:
                return False
            return True

        bot_path = _get_bot_dir(bot_id)
        if not bot_path.exists():
            return 0

        for date_dir in bot_path.rglob("*-*-*"):
            if not date_dir.is_dir():
                continue
            if not _should_delete(date_dir):
                continue
            try:
                shutil.rmtree(str(date_dir))
                deleted_count += 1
            except OSError as e:
                logger.error(f"Failed to delete {date_dir}: {e}")

        return deleted_count

    def prune_oldest(self, bot_id: str, max_bytes: int) -> int:
        current_usage = self.get_disk_usage(bot_id)
        if current_usage <= max_bytes:
            return 0

        target = int(max_bytes * 0.8)
        pruned = 0

        bot_path = _get_bot_dir(bot_id)
        if not bot_path.exists():
            return 0

        date_dirs = []
        for date_dir in bot_path.rglob("*-*-*"):
            if not date_dir.is_dir():
                continue
            try:
                mtime = date_dir.stat().st_mtime
            except OSError:
                mtime = 0
            date_dirs.append((mtime, date_dir))

        date_dirs.sort(key=lambda x: x[0])

        for _mtime, date_dir in date_dirs:
            if self.get_disk_usage(bot_id) <= target:
                break
            try:
                shutil.rmtree(str(date_dir))
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
