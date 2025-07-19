# backend/app/usage_tracker.py
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List
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
                            "by_model": {}
                        }, data.get("daily", {})),
                        "providers": defaultdict(lambda: defaultdict(int), data.get("providers", {}))
                    }
            except Exception as e:
                print(f"Error loading usage data: {e}")
        return {
            "daily": defaultdict(lambda: {
                "requests": 0, 
                "input_tokens": 0, 
                "output_tokens": 0, 
                "total_tokens": 0,
                "by_model": {}
            }),
            "providers": defaultdict(lambda: defaultdict(int))
        }
    
    async def save_data(self):
        async with self.lock:
            # 转换 defaultdict 为普通 dict 以便序列化
            data_to_save = {
                "daily": dict(self.usage_data["daily"]),
                "providers": {k: dict(v) for k, v in self.usage_data["providers"].items()}
            }
            with open(self.data_file, 'w') as f:
                json.dump(data_to_save, f, indent=2)
    
    async def record_usage(self, provider: str, model: str, input_tokens: int, output_tokens: int):
        async with self.lock:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            
            # 记录每日统计
            if today not in self.usage_data["daily"]:
                self.usage_data["daily"][today] = {
                    "requests": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "by_model": {}
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
            
        # 异步保存
        asyncio.create_task(self.save_data())
    
    async def get_statistics(self, period: str = "today") -> Dict[str, Any]:
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
                "by_model": defaultdict(lambda: {
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
                    
                    for model_key, model_data in data.get("by_model", {}).items():
                        total_stats["by_model"][model_key]["requests"] += model_data["requests"]
                        total_stats["by_model"][model_key]["input_tokens"] += model_data["input_tokens"]
                        total_stats["by_model"][model_key]["output_tokens"] += model_data["output_tokens"]
            
            return {
                "period": period,
                "start_date": start_date,
                "end_date": end_date,
                "stats": {
                    **total_stats,
                    "by_model": dict(total_stats["by_model"])
                }
            }

# 全局实例
usage_tracker = UsageTracker()
