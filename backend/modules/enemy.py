"""敌人模块：实例化、等级浮动、状态（增益/持续伤害/眩晕）与展示。"""
from __future__ import annotations

import random

from ..data_loader import enemy_def


class Enemy:
    """一场战斗中的一个敌人实例。"""

    def __init__(self, template_id: str, index: int = 0, boss: bool = False):
        tpl = enemy_def(template_id)
        self.template_id = template_id
        self.index = index
        self.name = tpl["name"]
        self.emoji = tpl["emoji"]
        self.level = int(tpl.get("level", 1))
        self.max_hp = int(tpl["hp"] * random.uniform(0.95, 1.05))
        self.hp = self.max_hp
        self.base_atk = tpl["atk"]
        self.base_def = tpl["def"]
        self.base_agi = tpl["agi"]
        self.crit = tpl.get("crit", 5)
        self.exp = tpl.get("exp", 10)
        self.gold = tpl.get("gold", 5)
        self.skills = tpl.get("skills", [])
        self.drops = tpl.get("drops", [])
        self.is_boss = boss or bool(tpl.get("title"))
        self.title = tpl.get("title")
        self.enrage_at = tpl.get("enrage")
        self.enraged = False
        self.final_boss = bool(tpl.get("final_boss"))
        self.guaranteed_equipment = bool(tpl.get("guaranteed_equipment"))
        self.buffs: list[dict] = []
        self.dots: list[dict] = []
        self.stun_rounds = 0
        self.shield = 0
        # 技能冷却：skill_uses 累计使用次数，skill_last 记录最近使用的回合。
        # 只对数据里带 cooldown / max_uses 的技能生效，旧数据不受影响。
        self.skill_uses: dict[str, int] = {}
        self.skill_last: dict[str, int] = {}

    # ---------- 有效属性 ----------
    def buff_mult(self, stat: str) -> float:
        total = 0.0
        for buff in self.buffs:
            if buff["stat"] == stat:
                total += buff["pct"]
        return max(0.2, 1 + total)

    @property
    def atk(self) -> float:
        return self.base_atk * self.buff_mult("atk")

    @property
    def defense(self) -> float:
        return self.base_def * self.buff_mult("def")

    @property
    def agi(self) -> float:
        return self.base_agi * self.buff_mult("agi")

    @property
    def dodge(self) -> float:
        return min(18.0, 2.0 + self.base_agi * 0.25)

    def is_alive(self) -> bool:
        return self.hp > 0

    def take_damage(self, amount: int) -> int:
        amount = max(0, int(amount))
        if self.shield > 0:
            absorbed = min(self.shield, amount)
            self.shield -= absorbed
            amount -= absorbed
        self.hp = max(0, self.hp - amount)
        return amount

    def heal(self, amount: int) -> int:
        before = self.hp
        self.hp = min(self.max_hp, self.hp + int(amount))
        return self.hp - before

    # ---------- 技能冷却 ----------
    def skill_ready(self, skill: dict, round_no: int) -> bool:
        """冷却未走完、或用尽了本场次数，就不能再选这个技能。"""
        max_uses = skill.get("max_uses")
        if max_uses is not None and self.skill_uses.get(skill["name"], 0) >= max_uses:
            return False
        cooldown = skill.get("cooldown")
        if cooldown:
            last = self.skill_last.get(skill["name"])
            if last is not None and round_no - last < cooldown:
                return False
        return True

    def note_skill_used(self, skill: dict, round_no: int) -> None:
        name = skill["name"]
        self.skill_uses[name] = self.skill_uses.get(name, 0) + 1
        self.skill_last[name] = round_no

    # ---------- 序列化 ----------
    def to_dict(self) -> dict:
        return {
            "template_id": self.template_id,
            "index": self.index,
            "name": self.name,
            "emoji": self.emoji,
            "level": self.level,
            "max_hp": self.max_hp,
            "hp": self.hp,
            "base_atk": self.base_atk,
            "base_def": self.base_def,
            "base_agi": self.base_agi,
            "crit": self.crit,
            "exp": self.exp,
            "gold": self.gold,
            "skills": self.skills,
            "drops": self.drops,
            "is_boss": self.is_boss,
            "title": self.title,
            "enrage_at": self.enrage_at,
            "enraged": self.enraged,
            "final_boss": self.final_boss,
            "guaranteed_equipment": self.guaranteed_equipment,
            "buffs": self.buffs,
            "dots": self.dots,
            "stun_rounds": self.stun_rounds,
            "shield": self.shield,
            "skill_uses": self.skill_uses,
            "skill_last": self.skill_last,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Enemy":
        enemy = cls(data["template_id"], data.get("index", 0), data.get("is_boss", False))
        enemy.name = data.get("name", enemy.name)
        enemy.emoji = data.get("emoji", enemy.emoji)
        enemy.level = data.get("level", enemy.level)
        enemy.max_hp = data.get("max_hp", enemy.max_hp)
        enemy.hp = data.get("hp", enemy.hp)
        enemy.base_atk = data.get("base_atk", enemy.base_atk)
        enemy.base_def = data.get("base_def", enemy.base_def)
        enemy.base_agi = data.get("base_agi", enemy.base_agi)
        enemy.crit = data.get("crit", enemy.crit)
        enemy.exp = data.get("exp", enemy.exp)
        enemy.gold = data.get("gold", enemy.gold)
        enemy.skills = data.get("skills", enemy.skills)
        enemy.drops = data.get("drops", enemy.drops)
        enemy.is_boss = data.get("is_boss", enemy.is_boss)
        enemy.title = data.get("title", enemy.title)
        enemy.enrage_at = data.get("enrage_at", enemy.enrage_at)
        enemy.enraged = data.get("enraged", False)
        enemy.final_boss = data.get("final_boss", False)
        enemy.guaranteed_equipment = data.get("guaranteed_equipment", False)
        enemy.buffs = list(data.get("buffs", []))
        enemy.dots = list(data.get("dots", []))
        enemy.stun_rounds = int(data.get("stun_rounds", 0))
        enemy.shield = int(data.get("shield", 0))
        enemy.skill_uses = dict(data.get("skill_uses", {}))
        enemy.skill_last = dict(data.get("skill_last", {}))
        return enemy

    def view(self) -> dict:
        return {
            "index": self.index,
            "name": self.name,
            "emoji": self.emoji,
            "level": self.level,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "atk": int(round(self.atk)),
            "def": int(round(self.defense)),
            "agi": int(round(self.agi)),
            "is_boss": self.is_boss,
            "title": self.title,
            "enraged": self.enraged,
            "shield": self.shield,
            "buffs": [{"stat": b["stat"], "pct": b["pct"], "rounds": b["rounds"]} for b in self.buffs],
            "dots": [{"id": d["id"], "rounds": d["rounds"]} for d in self.dots],
            "stunned": self.stun_rounds > 0,
            "alive": self.is_alive(),
        }
