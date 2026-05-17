#!/usr/bin/env python3
"""
Bot 功能模拟验证脚本。
对已启动的 bot 实例发送文本/图片消息，验证基础功能并打印后台日志。

用法:
  python simulations/simulate.py                          # 自动选第一个运行中的 bot
  python simulations/simulate.py --bot-id my-bot          # 指定单个 bot
  python simulations/simulate.py --all                    # 逐个测试所有 bot
  python simulations/simulate.py --all --max-bots 2       # 最多测 2 个
  python simulations/simulate.py --platform qq --all      # 测试所有 QQ bot
  python simulations/simulate.py --no-image --log-lines 0 # 纯文本, 不打印日志

测试步骤 (每个 bot):
  1. 基础问候          2. 简单问答
  3-5. 图片识别 (OCR)  6. 多轮上下文
  7. 角色扮演          8. 角色扮演验证
"""

import argparse
import base64
import json
import os
import sys
import time
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
IMAGES_DIR = os.path.join(HERE, "test_images")
ROOT_DIR = os.path.normpath(os.path.join(HERE, ".."))
BACKEND_DATA = os.path.join(ROOT_DIR, "backend", "data")
BOTS_DIR = os.path.join(BACKEND_DATA, "bots")
CONFIG_SEARCH = [
    os.path.join(BACKEND_DATA, "config.json"),
    os.path.join(BACKEND_DATA, "global_config.json"),
]

BASE_URL = os.getenv("SIMULATOR_API_URL", "http://localhost:8093")
API_KEY = None

# ── 工具函数 ────────────────────────────────────────────────────────

def load_api_key():
    for path in CONFIG_SEARCH:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            key = cfg.get("api_secret_key", "")
            if key:
                return key
    return os.getenv("SIMULATOR_API_KEY", "")


def api(endpoint, data=None, method="POST"):
    url = f"{BASE_URL}{endpoint}"
    body = json.dumps(data).encode("utf-8") if data is not None else None
    headers = {"Content-Type": "application/json", "X-API-Key": API_KEY}
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return {"error": True, "status": e.code, "detail": body[:300]}
    except Exception as e:
        return {"error": True, "detail": str(e)[:300]}


def get_bots():
    r = api("/api/bots")
    return r.get("bots", [])


def discover_bots_from_disk():
    bots = []
    if not os.path.isdir(BOTS_DIR):
        return bots
    for name in os.listdir(BOTS_DIR):
        dir_path = os.path.join(BOTS_DIR, name)
        if not os.path.isdir(dir_path):
            continue
        config_path = os.path.join(dir_path, "config.json")
        if not os.path.isfile(config_path):
            continue
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            bots.append({
                "bot_id": name,
                "platform": cfg.get("platform", "discord"),
                "status": "unknown",
                "enabled": cfg.get("enabled", True),
                "model_name": cfg.get("model_name", ""),
            })
        except Exception:
            pass
    return bots


def merge_bots(api_bots, disk_bots):
    """合并 API 和磁盘数据，API 优先（有运行状态），磁盘补全（未知状态的）"""
    merged = {}
    for b in api_bots:
        merged[b["bot_id"]] = b
    for b in disk_bots:
        if b["bot_id"] not in merged:
            merged[b["bot_id"]] = b
    return list(merged.values())


def get_logs():
    url = f"{BASE_URL}/api/logs"
    req = urllib.request.Request(url, headers={"X-API-Key": API_KEY})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return ""


def print_logs(label, lines=15):
    raw = get_logs()
    if not raw.strip():
        return
    all_lines = raw.splitlines()
    tail = all_lines[-lines:]
    print(f"  --- 日志 {label} (最近 {len(tail)} 行) ---")
    for line in tail:
        print(f"  {line}")


def load_image(name):
    path = os.path.join(IMAGES_DIR, name)
    if os.path.exists(path):
        with open(path, "rb") as f:
            return f.read()
    return None


def send_message(bot_id, content, history=None, image_path=None):
    messages = list(history[-6:]) if history else []
    messages.append({"role": "user", "content": content})

    payload = {
        "messages": messages,
        "bot_id": bot_id,
        "include_system_prompt": True,
    }

    if image_path:
        img_bytes = load_image(image_path)
        if img_bytes:
            payload["attachments"] = [{
                "name": image_path,
                "content_type": "image/png",
                "data_base64": base64.b64encode(img_bytes).decode("ascii"),
                "size": len(img_bytes),
            }]
        else:
            print(f"  [WARN] 图片 {image_path} 未找到, 仅发送文本")

    return api("/api/chat/direct", payload)


# ── 单 bot 测试流程 ──────────────────────────────────────────────────

def run_one(bot_id, platform, skip_image, log_lines):
    history = []
    passed = 0
    total = 0

    def step(n, label, msg, img=None, log_label=""):
        nonlocal passed, total
        total += 1
        print(f"  [{n}] {label}: {msg[:80]}", end="")
        if img:
            print(f" +img({img})", end="")
        print(flush=True)

        t0 = time.time()
        result = send_message(bot_id, msg, history, img)
        elapsed = time.time() - t0

        if result.get("error"):
            print(f"  FAIL ({elapsed:.1f}s) {result.get('detail','')[:120]}")
        else:
            resp = result.get("response", "")
            usage = result.get("usage", {})
            print(f"  OK ({elapsed:.1f}s, {len(resp)} chars)")
            if usage:
                print(f"  tokens: in={usage.get('input_tokens','?')} out={usage.get('output_tokens','?')}")
            print(f"  bot: {resp[:200]}")
            history.append({"role": "user", "content": msg})
            history.append({"role": "assistant", "content": resp})
            passed += 1

        if log_lines > 0:
            print_logs(log_label or label, log_lines)
        time.sleep(2)

    step(1, "greet", "你好，请用一句话介绍你自己。", log_label="问候")
    step(2, "math", "圆周率小数点后前 6 位是多少？只回答数字。", log_label="问答")

    if not skip_image:
        step(3, "ocr_en", "请识别这张图片中的文字，用中文回复。", img="ocr_test.png", log_label="OCR_EN")
        if os.path.exists(os.path.join(IMAGES_DIR, "ocr_test2.png")):
            step(4, "ocr_cn", "识别图片文字并用中文回复。", img="ocr_test2.png", log_label="OCR_CN")
        if os.path.exists(os.path.join(IMAGES_DIR, "ocr_test3.png")):
            step(5, "ocr_zh", "识别图片文字并用中文回复。", img="ocr_test3.png", log_label="OCR_ZH")
    else:
        print("  (图片测试已跳过)")

    base = 5 if skip_image else 6
    step(base, "context", "上一条消息我发了什么？简短回答。", log_label="上下文")
    step(base + 1, "rp1", "从现在开始你是一只叫喵喵的小猫，所有回复都要带'喵~'。打个招呼吧。", log_label="扮演1")
    step(base + 2, "rp2", "喵喵，你最喜欢吃什么？", log_label="扮演2")

    return passed, total


# ── 主入口 ────────────────────────────────────────────────────────────

def main():
    global BASE_URL, API_KEY

    parser = argparse.ArgumentParser(description="Bot 功能模拟验证")
    parser.add_argument("--bot-id", help="指定单个 bot ID")
    parser.add_argument("--all", action="store_true", help="逐个测试所有符合条件的 bot")
    parser.add_argument("--max-bots", type=int, default=0, help="最多测几个 bot (0=不限制)")
    parser.add_argument("--platform", choices=["discord", "qq"], default="discord")
    parser.add_argument("--api-url", default=BASE_URL)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--no-image", action="store_true")
    parser.add_argument("--log-lines", type=int, default=15)
    args = parser.parse_args()
    BASE_URL = args.api_url.rstrip("/")
    API_KEY = args.api_key or load_api_key()

    if not API_KEY:
        print("[ERR] Missing api_secret_key. Set SIMULATOR_API_KEY or ensure backend/data/config.json exists.")
        sys.exit(1)

    # 收集所有候选 bot
    api_bots = get_bots()
    disk_bots = discover_bots_from_disk()
    all_bots = merge_bots(api_bots, disk_bots)
    candidates = [b for b in all_bots if b.get("platform") == args.platform]

    if not candidates:
        print(f"[ERR] 未找到 {args.platform} bot")
        print(f"  API: {[(b['bot_id'], b.get('status','?')) for b in api_bots]}")
        print(f"  Disk: {[(b['bot_id'], b.get('platform','?')) for b in disk_bots]}")
        sys.exit(1)

    # 选择要测试的 bot 列表
    if args.bot_id:
        target = next((b for b in candidates if b["bot_id"] == args.bot_id), None)
        if not target:
            print(f"[ERR] Bot '{args.bot_id}' 不在候选列表中")
            print(f"  候选: {[b['bot_id'] for b in candidates]}")
            sys.exit(1)
        selected = [target]
    elif args.all:
        selected = candidates
        if args.max_bots > 0:
            selected = selected[:args.max_bots]
        print(f"全部测试: {len(selected)} 个 bot ({' '.join(b['bot_id'] for b in selected)})")
    else:
        selected = [candidates[0]]
        print(f"默认测试: [{selected[0]['bot_id']}] (用 --all 测试全部)")

    # 逐个运行
    overall = []
    for i, bot in enumerate(selected):
        if i > 0:
            print(f"\n{'=' * 55}")
        print(f"\n>>> [{i+1}/{len(selected)}] Bot: {bot['bot_id']}  platform={bot.get('platform','?')}  model={bot.get('model_name','?')}")
        print(f"{'=' * 55}")

        passed, total = run_one(bot["bot_id"], bot.get("platform", args.platform), args.no_image, args.log_lines)
        overall.append((bot["bot_id"], passed, total))
        time.sleep(3)

    # 汇总
    print(f"\n{'#' * 55}")
    print(f"  Summary")
    print(f"{'#' * 55}")
    for bot_id, p, t in overall:
        mark = "[OK]" if p == t else f"[{p}/{t}]"
        print(f"  {mark} {bot_id}")
    total_passed = sum(p for _, p, _ in overall)
    total_steps = sum(t for _, _, t in overall)
    print(f"\n  Total: {total_passed}/{total_steps}")
    print(f"{'#' * 55}\n")

    return 0 if total_passed == total_steps else 1


if __name__ == "__main__":
    sys.exit(main())
