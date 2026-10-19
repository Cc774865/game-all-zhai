"""角色模块：属性成长、等级经验、装备加成、加点与序列化。"""
from __future__ import annotations

import random

from ..data_loader import class_def, classes

EQUIP_SLOTS = ("weapon", "armor", "accessory")

# 每点自由属性提供的收益
POINT_GAIN = {"hp": 14, "mp": 8, "atk": 2, "def": 2, "agi": 1}

STAT_LABEL = {
    "hp": "生命",
    "mp": "法力",
    "atk": "攻击",
    "def": "防御",
    "agi": "敏捷",
    "crit": "暴击",
    "dodge": "闪避",
}


def exp_to_next(level: int) -> int:
    """升到下一级所需经验。"""
    return int(50 * (level ** 1.35))


class Character:
    """玩家角色。所有持久化字段都可通过 to_dict / from_dict 往返。"""

    def __init__(self, name: str, class_id: str):
        if class_id not in classes():
            raise ValueError(f"未知职业: {class_id}")
        self.name = name.strip()[:12] or "无名旅人"
        self.class_id = class_id
        self.level = 1
        self.exp = 0
        self.points = 0
        self.allocated = {"hp": 0, "mp": 0, "atk": 0, "def": 0, "agi": 0}
        self.gold = 120
        self.equipment: dict[str, dict | None] = {s: None for s in EQUIP_SLOTS}
        self.inventory: list[dict] = []
        self.skills: dict[str, dict] = {}
        self.kills = 0
        self.boss_kills = 0
        self.deaths = 0
        self.hp = self.max_hp
        self.mp = self.max_mp

    # ---------- 属性计算 ----------
    @property
    def cls(self) -> dict:
        return class_def(self.class_id)

    def _growth_stat(self, key: str) -> float:
        base = self.cls["base"].get(key, 0)
        growth = self.cls["growth"].get(key, 0)
        return base + growth * (self.level - 1)

    def _equip_bonus(self, key: str) -> int:
        total = 0
        for item in self.equipment.values():
            if item:
                total += int(item.get("stats", {}).get(key, 0))
        return total

    def base_stat(self, key: str) -> int:
        """不含装备的裸属性（加点后）。"""
        if key in ("hp", "mp", "atk", "def", "agi"):
            value = self._growth_stat(key) + self.allocated.get(key, 0) * POINT_GAIN[key]
            return int(round(value))
        if key == "crit":
            return round(self._growth_stat("crit") + self._growth_stat("agi") * 0.12, 1)
        if key == "dodge":
            return round(min(30.0, 3.0 + self._growth_stat("agi") * 0.45), 1)
        return 0

    @property
    def max_hp(self) -> int:
        return self.base_stat("hp") + self._equip_bonus("hp")

    @property
    def max_mp(self) -> int:
        return self.base_stat("mp") + self._equip_bonus("mp")

    @property
    def atk(self) -> int:
        return self.base_stat("atk") + self._equip_bonus("atk")

    @property
    def defense(self) -> int:
        return self.base_stat("def") + self._equip_bonus("def")

    @property
    def agi(self) -> int:
        return self.base_stat("agi") + self._equip_bonus("agi")

    @property
    def crit(self) -> float:
        return round(self.base_stat("crit") + self._equip_bonus("crit"), 1)

    @property
    def dodge(self) -> float:
        return round(min(45.0, self.base_stat("dodge") + self._equip_bonus("dodge")), 1)

    def stats(self) -> dict:
        return {
            "max_hp": self.max_hp,
            "max_mp": self.max_mp,
            "atk": self.atk,
            "def": self.defense,
            "agi": self.agi,
            "crit": self.crit,
            "dodge": self.dodge,
        }

    # ---------- 生命 / 法力 ----------
    def heal(self, amount: int) -> int:
        before = self.hp
        self.hp = min(self.max_hp, self.hp + int(amount))
        return self.hp - before

    def restore_mp(self, amount: int) -> int:
        before = self.mp
        self.mp = min(self.max_mp, self.mp + int(amount))
        return self.mp - before

    def take_damage(self, amount: int) -> int:
        amount = max(0, int(amount))
        self.hp = max(0, self.hp - amount)
        return amount

    def is_alive(self) -> bool:
        return self.hp > 0

    # ---------- 经验与升级 ----------
    @property
    def exp_need(self) -> int:
        return exp_to_next(self.level)

    def gain_exp(self, amount: int) -> list[dict]:
        """返回升级事件列表；可能一次升多级。"""
        events: list[dict] = []
        self.exp += int(amount)
        while self.level < 30 and self.exp >= self.exp_need:
            self.exp -= self.exp_need
            self.level += 1
            self.points += 3
            self.hp = self.max_hp
            self.mp = self.max_mp
            events.append({"level": self.level, "points": 3})
        return events

    def allocate(self, stat: str) -> None:
        if stat not in POINT_GAIN:
            raise ValueError("属性点只能加在 hp/mp/atk/def/agi 上")
        if self.points <= 0:
            raise ValueError("没有可用的属性点")
        self.points -= 1
        self.allocated[stat] += 1
        if stat == "hp":
            self.hp = min(self.max_hp, self.hp + POINT_GAIN["hp"])
        if stat == "mp":
            self.mp = min(self.max_mp, self.mp + POINT_GAIN["mp"])

    # ---------- 序列化 ----------
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "class_id": self.class_id,
            "level": self.level,
            "exp": self.exp,
            "points": self.points,
            "allocated": dict(self.allocated),
            "gold": self.gold,
            "equipment": {k: (dict(v) if v else None) for k, v in self.equipment.items()},
            "inventory": [dict(i) for i in self.inventory],
            "skills": {k: dict(v) for k, v in self.skills.items()},
            "kills": self.kills,
            "boss_kills": self.boss_kills,
            "deaths": self.deaths,
            "hp": self.hp,
            "mp": self.mp,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Character":
        char = cls(data["name"], data["class_id"])
        char.level = int(data.get("level", 1))
        char.exp = int(data.get("exp", 0))
        char.points = int(data.get("points", 0))
        char.allocated.update({k: int(v) for k, v in data.get("allocated", {}).items()})
        char.gold = int(data.get("gold", 0))
        for slot in EQUIP_SLOTS:
            char.equipment[slot] = data.get("equipment", {}).get(slot)
        char.inventory = list(data.get("inventory", []))
        char.skills = {k: dict(v) for k, v in data.get("skills", {}).items()}
        char.kills = int(data.get("kills", 0))
        char.boss_kills = int(data.get("boss_kills", 0))
        char.deaths = int(data.get("deaths", 0))
        char.hp = int(data.get("hp", char.max_hp))
        char.mp = int(data.get("mp", char.max_mp))
        char.hp = max(0, min(char.hp, char.max_hp))
        char.mp = max(0, min(char.mp, char.max_mp))
        return char

    # ---------- 展示 ----------
    def view(self) -> dict:
        return {
            "name": self.name,
            "class_id": self.class_id,
            "class_name": self.cls["name"],
            "class_emoji": self.cls["emoji"],
            "class_title": self.cls["title"],
            "level": self.level,
            "exp": self.exp,
            "exp_need": self.exp_need,
            "points": self.points,
            "allocated": dict(self.allocated),
            "gold": self.gold,
            "hp": self.hp,
            "mp": self.mp,
            "stats": self.stats(),
            "equipment": {k: (dict(v) if v else None) for k, v in self.equipment.items()},
            "inventory": [dict(i) for i in self.inventory],
            "skills": {k: dict(v) for k, v in self.skills.items()},
            "kills": self.kills,
            "boss_kills": self.boss_kills,
            "deaths": self.deaths,
        }


def roll_damage(atk: float, power: float, defense: float, *, pierce: float = 0.0,
                crit_chance: float = 0.0, crit_mult: float = 1.75,
                variance: float = 0.08) -> tuple[int, bool]:
    """伤害公式：攻方攻击 × 技能倍率 × 护甲减伤，暴击与浮动在最后结算。"""
    effective_def = max(0.0, defense * (1.0 - pierce))
    mitigation = 100.0 / (100.0 + effective_def * 1.55)
    damage = atk * power * mitigation
    is_crit = random.random() * 100 < crit_chance
    if is_crit:
        damage *= crit_mult
    damage *= random.uniform(1 - variance, 1 + variance)
    return max(1, int(round(damage))), is_crit
