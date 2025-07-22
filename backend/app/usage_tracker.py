# backend/app/usage_tracker.py
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
import asyncio
from collections import defaultdict
import pytz

class UsageTracker:
    def __init__(self, data_file="data/usage_data.json"):
        self.data_file = data_file
        # 确保数据目录存在
        data_dir = os.path.dirname(data_file)
        if data_dir:
            os.makedirs(data_dir, exist_ok=True)
            
        self.usage_data = self._load_data()
        self.lock = asyncio.Lock()
        
    def _load_data(self) -> Dict[str, Any]:
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
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
                        "metadata": data.get("metadata", {
                            "users": {},
                            "roles": {},
                            "channels": {},
                            "guilds": {}
                        })
                    }
            except Exception as e:
                print(f"Error loading usage data: {e}")
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
                "guilds": {}
            }
        }
    
    async def save_data(self):
        async with self.lock:
            data_to_save = {
                "daily": dict(self.usage_data["daily"]),
                "metadata": self.usage_data["metadata"]
            }
            with open(self.data_file, 'w') as f:
                json.dump(data_to_save, f, indent=2)
    
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
        guild_name: Optional[str] = None
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
            
        # 异步保存
        asyncio.create_task(self.save_data())
    
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

# 全局实例
usage_tracker = UsageTracker()
