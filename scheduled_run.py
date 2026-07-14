#!/usr/bin/env python3
"""按 Cloudflare CDN 中国流量峰谷调度 main.py，并防止任务重叠。"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone


def load_config(path):
    with open(path, "r", encoding="utf-8-sig") as config_file:
        return json.load(config_file)


def is_busy_hour(hour, start, end):
    if start == end:
        return True
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


def should_run(now, config):
    start = int(config.get("SCHEDULE_CF_BUSY_START_HOUR", 18))
    end = int(config.get("SCHEDULE_CF_BUSY_END_HOUR", 24))
    busy_interval = int(config.get("SCHEDULE_BUSY_INTERVAL_MINUTES", 15))
    offpeak_interval = int(config.get("SCHEDULE_OFFPEAK_INTERVAL_MINUTES", 30))
    if not 0 <= start <= 23 or not 0 <= end <= 24:
        raise ValueError("调度忙时小时必须在 0-24 范围内")
    if busy_interval < 1 or offpeak_interval < 1:
        raise ValueError("调度间隔必须大于 0")
    busy = is_busy_hour(now.hour, start, end)
    interval = busy_interval if busy else offpeak_interval
    return (now.hour * 60 + now.minute) % interval == 0, busy, interval


def acquire_lock(lock_path, stale_minutes):
    if os.path.exists(lock_path):
        age_seconds = time.time() - os.path.getmtime(lock_path)
        if age_seconds <= stale_minutes * 60:
            return False
        try:
            os.remove(lock_path)
        except OSError:
            return False
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    with os.fdopen(descriptor, "w", encoding="utf-8") as lock_file:
        lock_file.write(f"{os.getpid()}\n")
    return True


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config = load_config(os.path.join(script_dir, "config.json"))
    if not config.get("ENABLE_SCHEDULED_TASK", True):
        print("自动定时优选已在 config.json 中关闭；如需运行，请手动执行 main.py。")
        return 0

    offset = float(config.get("SCHEDULE_TIMEZONE_OFFSET_HOURS", 8))
    now = datetime.now(timezone(timedelta(hours=offset)))
    run_now, busy, interval = should_run(now, config)
    period_name = "CF CDN 中国忙时" if busy else "CF CDN 中国非忙时"
    if not run_now:
        print(f"[{now:%Y-%m-%d %H:%M}] {period_name}，本轮跳过（每{interval}分钟运行）")
        return 0

    lock_path = os.path.join(script_dir, ".cfnb_schedule.lock")
    stale_minutes = int(config.get("SCHEDULE_LOCK_STALE_MINUTES", 180))
    if not acquire_lock(lock_path, stale_minutes):
        print("检测到上一次优选任务仍在运行，本轮跳过。")
        return 0
    try:
        print(f"[{now:%Y-%m-%d %H:%M}] {period_name}，开始优选（每{interval}分钟）")
        child_env = os.environ.copy()
        child_env.setdefault("PYTHONUTF8", "1")
        child_env.setdefault("PYTHONIOENCODING", "utf-8")
        return subprocess.call(
            [sys.executable, os.path.join(script_dir, "main.py")],
            cwd=script_dir,
            env=child_env,
        )
    finally:
        try:
            os.remove(lock_path)
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())
