"""地图模块：区域解锁、移动、探索随机事件。"""
from __future__ import annotations

import random

from ..data_loader import area_def, area_map, areas, consumables

ENCOUNTER_CHANCE = 0.72
GOLD_CHANCE = 0.16


def initial_world() -> dict:
    return {
        "area": "village",
        # 晨曦村与迷雾森林开局即可前往，其余区域需击败前一区域 Boss
        "unlocked": ["village", "forest"],
        "visited": ["village"],
        "bosses": [],
        "steps": 0,
        "playtime": 0,
        "finished": False,
        "story": {"ending_seen": False},
    }


def is_unlocked(world: dict, area_id: str) -> bool:
    return area_id in world["unlocked"]


def can_travel(world: dict, area_id: str) -> tuple[bool, str]:
    if area_id not in area_map():
        return False, "不存在的地图区域"
    if not is_unlocked(world, area_id):
        return False, "该区域尚未解锁，先击败前一处区域的 Boss"
    return True, ""


def travel(world: dict, area_id: str) -> dict:
    ok, reason = can_travel(world, area_id)
    if not ok:
        raise ValueError(reason)
    world["area"] = area_id
    if area_id not in world["visited"]:
        world["visited"].append(area_id)
    world["steps"] += 1
    return {"area": area_id, "name": area_def(area_id)["name"]}


def unlock_next(world: dict, area_id: str) -> list[dict]:
    """击败 Boss 后解锁后继区域。"""
    area = area_def(area_id)
    unlocked = []
    for next_id in area.get("next", []):
        if next_id not in world["unlocked"]:
            world["unlocked"].append(next_id)
            unlocked.append({"id": next_id, "name": area_map()[next_id]["name"]})
    if area_id not in world["bosses"]:
        world["bosses"].append(area_id)
    if area.get("next") == [] and area["id"] == "void":
        world["finished"] = True
    return unlocked


def roll_explore(area_id: str, char) -> dict:
    """探索一次：战斗 / 金币 / 道具 / 空手而归。"""
    area = area_def(area_id)
    if area["safe"]:
        raise ValueError("安全区域没有可探索的内容")
    roll = random.random()
    if roll < ENCOUNTER_CHANCE:
        count = 1
        extra = random.random()
        if extra > 0.62:
            count = 2
        if extra > 0.9 and char.level >= 8:
            count = 3
        pool = area["enemies"]
        picks = random.sample(pool, k=min(count, len(pool)))
        return {"kind": "battle", "enemy_ids": picks}
    if roll < ENCOUNTER_CHANCE + GOLD_CHANCE:
        amount = int((8 + area["level_range"][1] * 4) * random.uniform(0.7, 1.4))
        return {"kind": "gold", "amount": amount}
    if roll < 0.96:
        item_id = random.choices(
            ["potion_hp", "potion_mp", "antidote", "potion_hp_big"],
            weights=[45, 30, 15, 10], k=1,
        )[0]
        return {"kind": "item", "item_id": item_id, "name": consumables()[item_id]["name"]}
    return {"kind": "nothing"}


def world_view(world: dict) -> dict:
    current = world["area"]
    nodes = []
    for area in areas():
        nodes.append({
            "id": area["id"],
            "name": area["name"],
            "emoji": area["emoji"],
            "safe": area["safe"],
            "tier": area["tier"],
            "level_range": area["level_range"],
            "desc": area["desc"],
            "unlocked": area["id"] in world["unlocked"],
            "visited": area["id"] in world["visited"],
            "cleared": area["id"] in world["bosses"],
            "boss": area["boss"],
            "enemies": area["enemies"],
            "features": area.get("features", []),
            "next": area.get("next", []),
            "current": area["id"] == current,
        })
    return {
        "current": current,
        "unlocked": list(world["unlocked"]),
        "visited": list(world["visited"]),
        "bosses": list(world["bosses"]),
        "steps": world["steps"],
        "finished": world.get("finished", False),
        "areas": nodes,
    }
