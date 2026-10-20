"""内容数据加载层：统一读取 backend/data 下的 JSON 配置。

所有静态游戏内容（职业、技能、装备、敌人、地图）都集中在这里加载并缓存，
业务模块只通过本模块取数据，方便后续把 JSON 换成数据库或编辑器导出的文件。
"""
from __future__ import annotations

import json
import os
from typing import Any

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

_cache: dict[str, Any] = {}


def _load(filename: str) -> Any:
    if filename not in _cache:
        path = os.path.join(DATA_DIR, filename)
        with open(path, "r", encoding="utf-8") as fp:
            _cache[filename] = json.load(fp)
    return _cache[filename]


def classes() -> dict[str, dict]:
    return _load("classes.json")


def class_def(class_id: str) -> dict:
    return classes()[class_id]


def skills() -> list[dict]:
    return _load("skills.json")


def skill_map() -> dict[str, dict]:
    if "_skill_map" not in _cache:
        _cache["_skill_map"] = {s["id"]: s for s in skills()}
    return _cache["_skill_map"]


def skills_for_class(class_id: str) -> list[dict]:
    return sorted(
        [s for s in skills() if s["class"] == class_id],
        key=lambda s: s["unlock_level"],
    )


def equipment_data() -> dict:
    return _load("equipment.json")


def rarities() -> dict[str, dict]:
    return equipment_data()["rarities"]


def equipment_templates() -> list[dict]:
    return equipment_data()["templates"]


def template_map() -> dict[str, dict]:
    if "_template_map" not in _cache:
        _cache["_template_map"] = {t["id"]: t for t in equipment_templates()}
    return _cache["_template_map"]


def consumables() -> dict[str, dict]:
    return equipment_data()["consumables"]


def enemies() -> dict[str, dict]:
    if "_enemies" not in _cache:
        data = _load("enemies.json")
        merged = {e["id"]: e for e in data["enemies"]}
        merged.update({b["id"]: b for b in data["bosses"]})
        _cache["_enemies"] = merged
        _cache["_bosses"] = {b["id"]: b for b in data["bosses"]}
    return _cache["_enemies"]


def enemy_def(enemy_id: str) -> dict:
    return enemies()[enemy_id]


def bosses() -> dict[str, dict]:
    enemies()
    return _cache["_bosses"]


def areas() -> list[dict]:
    return _load("areas.json")


def area_map() -> dict[str, dict]:
    if "_area_map" not in _cache:
        _cache["_area_map"] = {a["id"]: a for a in areas()}
    return _cache["_area_map"]


def area_def(area_id: str) -> dict:
    return area_map()[area_id]


def story_data() -> dict:
    return _load("story.json")
