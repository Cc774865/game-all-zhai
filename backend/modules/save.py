"""存档模块：文件持久化、原子写入、槽位管理与元信息。

存档为纯 JSON，位于 storage/saves/<slot>.json，可手工备份或迁移。
写入采用「临时文件 + os.replace」，避免中途断电产生半截存档。
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAVE_DIR = os.path.join(BASE_DIR, "storage", "saves")
SAVE_VERSION = 1
SLOT_RE = re.compile(r"^[a-z0-9_]{1,20}$")
DEFAULT_SLOTS = ["auto", "slot1", "slot2", "slot3"]


def _ensure_dir() -> None:
    os.makedirs(SAVE_DIR, exist_ok=True)


def _path(slot: str) -> str:
    if not SLOT_RE.match(slot or ""):
        raise ValueError("非法存档槽位")
    return os.path.join(SAVE_DIR, f"{slot}.json")


def save(slot: str, character: dict, world: dict, battle: dict | None,
         meta: dict | None = None) -> dict:
    _ensure_dir()
    payload = {
        "version": SAVE_VERSION,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "timestamp": int(time.time()),
        "meta": meta or {},
        "character": character,
        "world": world,
        "battle": battle,
    }
    path = _path(slot)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=1)
        fp.flush()
        os.fsync(fp.fileno())
    os.replace(tmp, path)
    return {"slot": slot, "saved_at": payload["saved_at"], "meta": payload["meta"]}


def load(slot: str) -> dict | None:
    path = _path(slot)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as fp:
        data = json.load(fp)
    if data.get("version") != SAVE_VERSION:
        # 预留版本迁移入口
        data.setdefault("version", SAVE_VERSION)
    return data


def delete(slot: str) -> bool:
    path = _path(slot)
    if os.path.exists(path):
        os.remove(path)
        return True
    return False


def list_saves() -> list[dict]:
    _ensure_dir()
    result = []
    for filename in os.listdir(SAVE_DIR):
        if not filename.endswith(".json"):
            continue
        slot = filename[:-5]
        try:
            data = load(slot)
        except (json.JSONDecodeError, OSError):
            continue
        if not data:
            continue
        meta = data.get("meta", {})
        result.append({
            "slot": slot,
            "saved_at": data.get("saved_at", ""),
            "timestamp": data.get("timestamp", 0),
            "name": meta.get("name", "未知"),
            "class_name": meta.get("class_name", ""),
            "class_emoji": meta.get("class_emoji", ""),
            "level": meta.get("level", 1),
            "area_name": meta.get("area_name", ""),
            "gold": meta.get("gold", 0),
            "playtime": meta.get("playtime", 0),
            "in_battle": bool(data.get("battle")),
            "finished": meta.get("finished", False),
        })
    order = {slot: i for i, slot in enumerate(DEFAULT_SLOTS)}
    result.sort(key=lambda s: (order.get(s["slot"], 99), -s["timestamp"]))
    return result


def has_any_save() -> bool:
    return bool(list_saves())
