# backend/app/usage_tracker.py
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
import asyncio
from collections import defaultdict
import pytz

from .paths import DataPaths

logger = logging.getLogger(__name__)

_DEFAULT_USAGE_FILE = str(DataPaths.USAGE_FILE)


def _default_usage_data() -> Dict[str, Any]:
    """Return the default in-memory usage data structure."""
    return {
        "daily": defaultdict(lambda: {
            "requests": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "detailed": {
                "by_user": {},
                "by_role": {},
                "by_channel": {},
                "by_guild": {}
            }
        }),
        "metadata": {
            "users": {},
            "roles": {},
            "channels": {},
            "guilds": {},
            "channel_users": {}
        }
    }


class UsageTracker:
    def __init__(self, data_file=_DEFAULT_USAGE_FILE, quota_alert_manager=None):
        self.data_file = data_file
        data_dir = os.path.dirname(data_file)
        if data_dir:
            os.makedirs(data_dir, exist_ok=True)
        # Start with defaults; actual file data is loaded later via initialize().
        self.usage_data = _default_usage_data()
        self.lock = asyncio.Lock()
        self._save_pending = False
        self._save_dirty = False
        self._save_task = None
        self._quota_alert_manager = quota_alert_manager

    async def initialize(self) -> None:
        """Load persisted usage data from disk (runs sync I/O in a thread)."""
        data = await asyncio.to_thread(self._load_data_sync)
        self.usage_data = data

    def _load_data_sync(self) -> Dict[str, Any]:
        """Synchronous JSON load — designed to run inside asyncio.to_thread()."""
        if not os.path.exists(self.data_file):
            return _default_usage_data()
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                metadata = data.get("metadata", {})
                if "channel_users" not in metadata:
                    metadata["channel_users"] = {}
                return {
                    "daily": defaultdict(lambda: {
                        "requests": 0,
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "total_tokens": 0,
                        "detailed": {
                            "by_user": {},
                            "by_role": {},
                            "by_channel": {},
                            "by_guild": {}
                        }
                    }, data.get("daily", {})),
                    "metadata": metadata
                }
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Error loading usage data from %s: %s. Backing up corrupt file.", self.data_file, e)
            try:
                os.replace(self.data_file, self.data_file + ".corrupt")
            except OSError:
                pass
            return _default_usage_data()
    
    async def save_data(self):
        async with self.lock:
            data_to_save = {
                "daily": dict(self.usage_data["daily"]),
                "metadata": self.usage_data["metadata"]
            }
            tmp_file = self.data_file + ".tmp"
            await asyncio.to_thread(self._write_json_atomic, tmp_file, data_to_save)

    def _write_json_atomic(self, tmp_file: str, data: dict) -> None:
        with open(tmp_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_file, self.data_file)
    
    async def record_usage(
        self, 
        provider: str, 
        model: str, 
        input_tokens: int, 
        output_tokens: int,
        user_id: Optional[str] = None,
        user_name: Optional[str] = None,
        user_display_name: Optional[str] = None,
        role_id: Optional[str] = None,
        role_name: Optional[str] = None,
        channel_id: Optional[str] = None,
        channel_name: Optional[str] = None,
        guild_id: Optional[str] = None,
        guild_name: Optional[str] = None,
        bot_id: Optional[str] = None
    ):
        async with self.lock:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            model_key = f"{provider}:{model}"
            
            # 更新元数据
            if user_id:
                self.usage_data["metadata"]["users"][user_id] = {
                    "name": user_name,
                    "display_name": user_display_name
                }
            if role_id:
                self.usage_data["metadata"]["roles"][role_id] = {
                    "name": role_name
                }
            if channel_id:
                self.usage_data["metadata"]["channels"][channel_id] = {
                    "name": channel_name
                }
                channel_users = self.usage_data["metadata"].setdefault("channel_users", {})
                per_channel = channel_users.setdefault(channel_id, {"user_ids": []})
                if "user_ids" not in per_channel or not isinstance(per_channel.get("user_ids"), list):
                    per_channel["user_ids"] = []
                if user_id and user_id not in per_channel["user_ids"]:
                    per_channel["user_ids"].append(user_id)
            if guild_id:
                self.usage_data["metadata"]["guilds"][guild_id] = {
                    "name": guild_name
                }
            
            # 初始化当天数据
            if today not in self.usage_data["daily"]:
                self.usage_data["daily"][today] = {
                    "requests": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "detailed": {
                        "by_user": {},
                        "by_role": {},
                        "by_channel": {},
                        "by_guild": {}
                    }
                }
            
            daily = self.usage_data["daily"][today]
            daily["requests"] += 1
            daily["input_tokens"] += input_tokens
            daily["output_tokens"] += output_tokens
            daily["total_tokens"] += input_tokens + output_tokens
            
            # 记录用户-模型详细数据
            if user_id:
                if user_id not in daily["detailed"]["by_user"]:
                    daily["detailed"]["by_user"][user_id] = {
                        "total": {"requests": 0, "input_tokens": 0, "output_tokens": 0},
                        "models": {}
                    }
                
                user_data = daily["detailed"]["by_user"][user_id]
                user_data["total"]["requests"] += 1
                user_data["total"]["input_tokens"] += input_tokens
                user_data["total"]["output_tokens"] += output_tokens
                
                if model_key not in user_data["models"]:
                    user_data["models"][model_key] = {"requests": 0, "input_tokens": 0, "output_tokens": 0}
                
                user_data["models"][model_key]["requests"] += 1
                user_data["models"][model_key]["input_tokens"] += input_tokens
                user_data["models"][model_key]["output_tokens"] += output_tokens
            
            # 记录身份组-模型详细数据
            if role_id:
                if role_id not in daily["detailed"]["by_role"]:
                    daily["detailed"]["by_role"][role_id] = {
                        "total": {"requests": 0, "input_tokens": 0, "output_tokens": 0},
                        "models": {}
                    }
                
                role_data = daily["detailed"]["by_role"][role_id]
                role_data["total"]["requests"] += 1
                role_data["total"]["input_tokens"] += input_tokens
                role_data["total"]["output_tokens"] += output_tokens
                
                if model_key not in role_data["models"]:
                    role_data["models"][model_key] = {"requests": 0, "input_tokens": 0, "output_tokens": 0}
                
                role_data["models"][model_key]["requests"] += 1
                role_data["models"][model_key]["input_tokens"] += input_tokens
                role_data["models"][model_key]["output_tokens"] += output_tokens
            
            # 记录频道-模型详细数据
            if channel_id:
                if channel_id not in daily["detailed"]["by_channel"]:
                    daily["detailed"]["by_channel"][channel_id] = {
                        "total": {"requests": 0, "input_tokens": 0, "output_tokens": 0},
                        "models": {}
                    }
                
                channel_data = daily["detailed"]["by_channel"][channel_id]
                channel_data["total"]["requests"] += 1
                channel_data["total"]["input_tokens"] += input_tokens
                channel_data["total"]["output_tokens"] += output_tokens
                
                if model_key not in channel_data["models"]:
                    channel_data["models"][model_key] = {"requests": 0, "input_tokens": 0, "output_tokens": 0}
                
                channel_data["models"][model_key]["requests"] += 1
                channel_data["models"][model_key]["input_tokens"] += input_tokens
                channel_data["models"][model_key]["output_tokens"] += output_tokens
            
            # 记录服务器-模型详细数据
            if guild_id:
                if guild_id not in daily["detailed"]["by_guild"]:
                    daily["detailed"]["by_guild"][guild_id] = {
                        "total": {"requests": 0, "input_tokens": 0, "output_tokens": 0},
                        "models": {}
                    }
                
                guild_data = daily["detailed"]["by_guild"][guild_id]
                guild_data["total"]["requests"] += 1
                guild_data["total"]["input_tokens"] += input_tokens
                guild_data["total"]["output_tokens"] += output_tokens
                
                if model_key not in guild_data["models"]:
                    guild_data["models"][model_key] = {"requests": 0, "input_tokens": 0, "output_tokens": 0}
                
                guild_data["models"][model_key]["requests"] += 1
                guild_data["models"][model_key]["input_tokens"] += input_tokens
                guild_data["models"][model_key]["output_tokens"] += output_tokens

            # Capture snapshot for async quota alert (P1-5: 在锁内捕获, 锁外异步执行)
            _quota_snapshot = (
                (today, dict(self.usage_data["daily"].get(today, {})))
                if self._quota_alert_manager and bot_id
                else None
            )

        # P1-1/P1-5 修复: 在锁外部异步触发配额告警, 不阻塞关键路径
        if _quota_snapshot is not None:
            _today, _daily_usage = _quota_snapshot
            _daily_quota = self._read_bot_quota_config(bot_id)
            asyncio.create_task(
                self._quota_alert_manager.check_and_alert(
                    bot_id=bot_id,
                    user_id=user_id,
                    daily_usage=_daily_usage,
                    daily_quota=_daily_quota,
                )
            )

        # 异步保存
        self._schedule_save()

    async def _safe_save(self):
        try:
            await self.save_data()
        except Exception as e:
            logger.error(f"Failed to save usage data: {e}", exc_info=True)

    def _schedule_save(self) -> None:
        self._save_dirty = True
        if self._save_pending:
            return
        self._save_pending = True
        self._save_task = asyncio.create_task(self._debounced_save())
        self._save_task.add_done_callback(self._on_save_done)

    async def _debounced_save(self):
        await asyncio.sleep(1.5)
        self._save_pending = False
        if self._save_dirty:
            self._save_dirty = False
            await self._safe_save()

    def _on_save_done(self, task: asyncio.Task) -> None:
        try:
            task.result()
        except Exception as e:
            logger.error(f"Unhandled error in scheduled usage save: {e}", exc_info=True)
    
    def _read_bot_quota_config(self, bot_id: str) -> Dict[str, Any]:
        """从 Bot config 读取配额设置.

        Args:
            bot_id: Bot 标识.

        Returns:
            dict 包含 token_limit 和 request_limit，如果未配置则使用默认值.
        """
        try:
            from .app_context import AppContext
            ctx = AppContext.get()
            if ctx.bot_manager is None:
                return {}
            instance = ctx.bot_manager.get(bot_id)
            if instance is None:
                return {}
            config = instance.config
            if not config:
                return {}
            quota_alert = config.get("quota_alert", {})
            if not quota_alert or not quota_alert.get("enabled", False):
                # 不存在或未启用 → 使用默认配额限制
                return {"token_limit": 1000000, "request_limit": 1000}
            return {
                "token_limit": quota_alert.get("token_limit", 1000000),
                "request_limit": quota_alert.get("request_limit", 1000),
            }
        except Exception:
            logger.debug("Failed to read quota config for bot '%s'", bot_id, exc_info=True)
            return {}

    async def close(self) -> None:
        if hasattr(self, '_save_task') and self._save_task and not self._save_task.done():
            self._save_task.cancel()
            try:
                await self._save_task
            except asyncio.CancelledError:
                pass
        if self._save_dirty:
            await self._safe_save()

    async def get_statistics(self, period: str = "today", view: str = "user", timezone_str: str = "UTC") -> Dict[str, Any]:
        async with self.lock:
            try:
                user_tz = pytz.timezone(timezone_str)
            except pytz.UnknownTimeZoneError:
                user_tz = pytz.utc

            now_in_user_tz = datetime.now(user_tz)
            
            if period == "today":
                start_date = now_in_user_tz.strftime("%Y-%m-%d")
                end_date = start_date
            elif period == "week":
                # 以用户时区的“今天”为基准，往前推7天
                start_of_today = now_in_user_tz.replace(hour=0, minute=0, second=0, microsecond=0)
                start_date_dt = start_of_today - timedelta(days=6) # 包括今天在内总共7天
                start_date = start_date_dt.strftime("%Y-%m-%d")
                end_date = now_in_user_tz.strftime("%Y-%m-%d")
            elif period == "month":
                # 以用户时区的“今天”为基准，往前推30天
                start_of_today = now_in_user_tz.replace(hour=0, minute=0, second=0, microsecond=0)
                start_date_dt = start_of_today - timedelta(days=29) # 包括今天在内总共30天
                start_date = start_date_dt.strftime("%Y-%m-%d")
                end_date = now_in_user_tz.strftime("%Y-%m-%d")
            else:  # all time
                dates = list(self.usage_data["daily"].keys())
                start_date = min(dates) if dates else now_in_user_tz.strftime("%Y-%m-%d")
                end_date = now_in_user_tz.strftime("%Y-%m-%d")
            
            # 聚合数据
            total_stats = {
                "requests": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "detailed_by_" + view: {}
            }
            
            for date_str, data in self.usage_data["daily"].items():
                if start_date <= date_str <= end_date:
                    total_stats["requests"] += data["requests"]
                    total_stats["input_tokens"] += data["input_tokens"]
                    total_stats["output_tokens"] += data["output_tokens"]
                    total_stats["total_tokens"] += data["total_tokens"]
                    
                    # 聚合详细数据
                    view_data = data.get("detailed", {}).get("by_" + view, {})
                    for key, item_data in view_data.items():
                        if key not in total_stats["detailed_by_" + view]:
                            total_stats["detailed_by_" + view][key] = {
                                "total": {"requests": 0, "input_tokens": 0, "output_tokens": 0},
                                "models": {}
                            }
                        
                        dest = total_stats["detailed_by_" + view][key]
                        dest["total"]["requests"] += item_data["total"]["requests"]
                        dest["total"]["input_tokens"] += item_data["total"]["input_tokens"]
                        dest["total"]["output_tokens"] += item_data["total"]["output_tokens"]
                        
                        for model_key, model_stats in item_data.get("models", {}).items():
                            if model_key not in dest["models"]:
                                dest["models"][model_key] = {"requests": 0, "input_tokens": 0, "output_tokens": 0}
                            
                            dest["models"][model_key]["requests"] += model_stats["requests"]
                            dest["models"][model_key]["input_tokens"] += model_stats["input_tokens"]
                            dest["models"][model_key]["output_tokens"] += model_stats["output_tokens"]
            
            return {
                "period": period,
                "view": view,
                "start_date": start_date,
                "end_date": end_date,
                "stats": total_stats,
                "metadata": self.usage_data["metadata"]
            }

# Module-level singleton removed (G3).
# Use AppContext.get().usage_tracker or Depends(get_usage_tracker_dep) instead.
