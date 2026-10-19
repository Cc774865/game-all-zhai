"""技能模块：技能解锁、熟练度成长、等级倍率与展示。"""
from __future__ import annotations

from ..data_loader import skill_map, skills_for_class

MAX_SKILL_LEVEL = 5
POWER_PER_LEVEL = 0.15


def proficiency_need(level: int) -> int:
    """从当前熟练等级升到下一级所需的施展次数。"""
    return 8 * level


def unlock_for_level(char) -> list[dict]:
    """按角色等级自动解锁技能，返回本次新解锁的技能信息。"""
    unlocked: list[dict] = []
    for skill in skills_for_class(char.class_id):
        if skill["unlock_level"] <= char.level and skill["id"] not in char.skills:
            char.skills[skill["id"]] = {"level": 1, "exp": 0}
            unlocked.append({"id": skill["id"], "name": skill["name"], "icon": skill["icon"]})
    return unlocked


def is_known(char, skill_id: str) -> bool:
    return skill_id in char.skills


def power_of(skill: dict, level: int) -> float:
    return round(skill.get("power", 0) * (1 + POWER_PER_LEVEL * (level - 1)), 3)


def mp_cost(skill: dict, level: int) -> int:
    return int(skill.get("mp", 0))


def train(char, skill_id: str) -> dict:
    """施展技能后增长熟练度，可能升级。"""
    state = char.skills.get(skill_id)
    if not state:
        return {}
    state["exp"] += 1
    result = {"id": skill_id, "gain": 1, "level_up": False}
    if state["level"] < MAX_SKILL_LEVEL and state["exp"] >= proficiency_need(state["level"]):
        state["exp"] -= proficiency_need(state["level"])
        state["level"] += 1
        result["level_up"] = True
        result["level"] = state["level"]
        result["name"] = skill_map()[skill_id]["name"]
    return result


def skill_list(char) -> list[dict]:
    """返回该职业全部技能（含未解锁），供前端展示成长路线。"""
    out = []
    for skill in skills_for_class(char.class_id):
        state = char.skills.get(skill["id"])
        lvl = state["level"] if state else 0
        need = proficiency_need(lvl) if state and lvl < MAX_SKILL_LEVEL else 0
        out.append({
            "id": skill["id"],
            "name": skill["name"],
            "icon": skill["icon"],
            "desc": skill["desc"],
            "type": skill["type"],
            "unlock_level": skill["unlock_level"],
            "unlocked": state is not None,
            "level": lvl,
            "max_level": MAX_SKILL_LEVEL,
            "prof": state["exp"] if state else 0,
            "prof_need": need,
            "mp": mp_cost(skill, lvl or 1),
            "power": power_of(skill, lvl or 1),
            "base_power": skill.get("power", 0),
            "hits": skill.get("hits", 1),
            "aoe": skill.get("aoe", False),
        })
    return out
