# backend/app/usage_tracker.py
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
import asyncio
from collections import defaultdict

class UsageTracker:
    def __init__(self, data_file="usage_data.json"):
        self.data_file = data_file
        self.usage_data = self._load_data()
        self.lock = asyncio.Lock()
        
    def _load_data(self) -> Dict[str, Any]:
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    # 转换字符串键回 defaultdict
                    return {
                        "daily": defaultdict(lambda: {
                            "requests": 0, 
                            "input_tokens": 0, 
                            "output_tokens": 0, 
                            "total_tokens": 0,
                            "by_model": {},
                            "by_user": {},
                            "by_role": {},
                            "by_channel": {},
                            "by_guild": {}
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
                "by_model": {},
                "by_user": {},
                "by_role": {},
                "by_channel": {},
                "by_guild": {}
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
            # 转换 defaultdict 为普通 dict 以便序列化
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
            
            # 记录每日统计
            if today not in self.usage_data["daily"]:
                self.usage_data["daily"][today] = {
                    "requests": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "by_model": {},
                    "by_user": {},
                    "by_role": {},
                    "by_channel": {},
                    "by_guild": {}
                }
            
            daily = self.usage_data["daily"][today]
            daily["requests"] += 1
            daily["input_tokens"] += input_tokens
            daily["output_tokens"] += output_tokens
            daily["total_tokens"] += input_tokens + output_tokens
            
            # 按模型统计
            model_key = f"{provider}:{model}"
            if model_key not in daily["by_model"]:
                daily["by_model"][model_key] = {
                    "requests": 0,
                    "input_tokens": 0,
                    "output_tokens": 0
                }
            
            daily["by_model"][model_key]["requests"] += 1
            daily["by_model"][model_key]["input_tokens"] += input_tokens
            daily["by_model"][model_key]["output_tokens"] += output_tokens
            
            # 按用户统计
            if user_id:
                if user_id not in daily["by_user"]:
                    daily["by_user"][user_id] = {
                        "requests": 0,
                        "input_tokens": 0,
                        "output_tokens": 0
                    }
                daily["by_user"][user_id]["requests"] += 1
                daily["by_user"][user_id]["input_tokens"] += input_tokens
                daily["by_user"][user_id]["output_tokens"] += output_tokens
            
            # 按身份组统计
            if role_id:
                if role_id not in daily["by_role"]:
                    daily["by_role"][role_id] = {
                        "requests": 0,
                        "input_tokens": 0,
                        "output_tokens": 0
                    }
                daily["by_role"][role_id]["requests"] += 1
                daily["by_role"][role_id]["input_tokens"] += input_tokens
                daily["by_role"][role_id]["output_tokens"] += output_tokens
            
            # 按频道统计
            if channel_id:
                if channel_id not in daily["by_channel"]:
                    daily["by_channel"][channel_id] = {
                        "requests": 0,
                        "input_tokens": 0,
                        "output_tokens": 0
                    }
                daily["by_channel"][channel_id]["requests"] += 1
                daily["by_channel"][channel_id]["input_tokens"] += input_tokens
                daily["by_channel"][channel_id]["output_tokens"] += output_tokens
            
            # 按服务器统计
            if guild_id:
                if guild_id not in daily["by_guild"]:
                    daily["by_guild"][guild_id] = {
                        "requests": 0,
                        "input_tokens": 0,
                        "output_tokens": 0
                    }
                daily["by_guild"][guild_id]["requests"] += 1
                daily["by_guild"][guild_id]["input_tokens"] += input_tokens
                daily["by_guild"][guild_id]["output_tokens"] += output_tokens
            
        # 异步保存
        asyncio.create_task(self.save_data())
    
    async def get_statistics(self, period: str = "today", view: str = "model") -> Dict[str, Any]:
        async with self.lock:
            now = datetime.now(timezone.utc)
            
            if period == "today":
                start_date = now.strftime("%Y-%m-%d")
                end_date = start_date
            elif period == "week":
                start_date = (now - timedelta(days=7)).strftime("%Y-%m-%d")
                end_date = now.strftime("%Y-%m-%d")
            elif period == "month":
                start_date = (now - timedelta(days=30)).strftime("%Y-%m-%d")
                end_date = now.strftime("%Y-%m-%d")
            else:  # all time
                dates = list(self.usage_data["daily"].keys())
                start_date = min(dates) if dates else now.strftime("%Y-%m-%d")
                end_date = now.strftime("%Y-%m-%d")
            
            # 聚合数据
            total_stats = {
                "requests": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                f"by_{view}": defaultdict(lambda: {
                    "requests": 0,
                    "input_tokens": 0,
                    "output_tokens": 0
                })
            }
            
            for date_str, data in self.usage_data["daily"].items():
                if start_date <= date_str <= end_date:
                    total_stats["requests"] += data["requests"]
                    total_stats["input_tokens"] += data["input_tokens"]
                    total_stats["output_tokens"] += data["output_tokens"]
                    total_stats["total_tokens"] += data["total_tokens"]
                    
                    # 根据视图类型聚合数据
                    view_data = data.get(f"by_{view}", {})
                    for key, stats in view_data.items():
                        total_stats[f"by_{view}"][key]["requests"] += stats["requests"]
                        total_stats[f"by_{view}"][key]["input_tokens"] += stats["input_tokens"]
                        total_stats[f"by_{view}"][key]["output_tokens"] += stats["output_tokens"]
            
            return {
                "period": period,
                "view": view,
                "start_date": start_date,
                "end_date": end_date,
                "stats": {
                    **total_stats,
                    f"by_{view}": dict(total_stats[f"by_{view}"])
                },
                "metadata": self.usage_data["metadata"]
            }

# 全局实例
usage_tracker = UsageTracker()
