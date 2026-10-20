"""战斗模块：回合制流程、行动顺序、闪避/暴击、状态效果、Boss 狂暴、奖励结算。

设计要点
- 一次 HTTP 请求结算一整个回合：玩家行动 + 所有敌人行动按速度排序执行。
- 战斗状态完全可序列化，存档后可从任意回合恢复。
- 所有随机都走 random，便于测试时设种子复现。
"""
from __future__ import annotations

import random

from ..data_loader import area_def, consumables, skill_map
from . import equipment as equip_mod
from . import skill as skill_mod
from .character import Character, roll_damage
from .enemy import Enemy

MAX_LOG = 120


def _pct(value: float) -> str:
    return f"{int(round(value * 100))}%"


class Battle:
    def __init__(self, char: Character, enemy_ids: list[str], area_id: str,
                 is_boss: bool = False, boss_id: str | None = None):
        self.char = char
        self.area_id = area_id
        self.enemies = [Enemy(eid, i, is_boss) for i, eid in enumerate(enemy_ids)]
        self.round = 1
        self.status = "active"          # active / won / lost / fled
        self.is_boss = is_boss
        self.boss_id = boss_id
        self.log: list[dict] = []
        self.player_buffs: list[dict] = []
        self.player_dots: list[dict] = []
        self.player_shield = 0
        self.player_stun = 0
        self.defending = False
        self.rewards: dict | None = None
        self.escaped = False
        self._log("system", f"遭遇 {self._enemy_names()}！" if not is_boss else f"⚠️ Boss 战开始：{self._enemy_names()}")

    # ---------- 基础工具 ----------
    def _enemy_names(self) -> str:
        return "、".join(e.name for e in self.enemies)

    def _log(self, kind: str, text: str, **extra) -> dict:
        entry = {"round": self.round, "type": kind, "text": text}
        entry.update(extra)
        self.log.append(entry)
        if len(self.log) > MAX_LOG:
            self.log = self.log[-MAX_LOG:]
        return entry

    def _alive_enemies(self) -> list[Enemy]:
        return [e for e in self.enemies if e.is_alive()]

    def _pick_target(self, index: int | None) -> Enemy | None:
        alive = self._alive_enemies()
        if not alive:
            return None
        if index is not None:
            for enemy in alive:
                if enemy.index == index:
                    return enemy
        return alive[0]

    def _buff_mult(self, stat: str) -> float:
        total = sum(b["pct"] for b in self.player_buffs if b["stat"] == stat)
        return max(0.25, 1 + total)

    def player_stats(self) -> dict:
        s = self.char.stats()
        dodge_bonus = sum(b["pct"] * 100 for b in self.player_buffs if b["stat"] == "dodge")
        return {
            "atk": s["atk"] * self._buff_mult("atk"),
            "def": s["def"] * self._buff_mult("def") * (1.6 if self.defending else 1.0),
            "agi": s["agi"] * self._buff_mult("agi"),
            "crit": s["crit"],
            "dodge": min(75.0, s["dodge"] + dodge_bonus),
            "max_hp": s["max_hp"],
            "max_mp": s["max_mp"],
        }

    def _add_buff(self, stat: str, pct: float, rounds: int, name: str) -> None:
        self.player_buffs.append({
            "stat": stat, "pct": pct, "rounds": rounds,
            "expires": self.round + rounds, "name": name,
        })

    # ---------- 主流程 ----------
    def player_action(self, action: dict) -> dict:
        if self.status != "active":
            raise ValueError("战斗已经结束")
        kind = action.get("action")
        events_start = len(self.log)

        if kind == "flee":
            self._try_flee()
            return self._result(events_start)

        plan = self._prepare_player_action(action)
        intents = [(e, self._choose_enemy_action(e)) for e in self._alive_enemies()]

        order: list[tuple[float, str, object]] = []
        stats = self.player_stats()
        order.append((stats["agi"] + random.uniform(-1.5, 1.5), "player", None))
        for enemy, intent in intents:
            order.append((enemy.agi + random.uniform(-1.5, 1.5), "enemy", (enemy, intent)))
        order.sort(key=lambda x: x[0], reverse=True)

        for _, side, payload in order:
            if self.status != "active":
                break
            if side == "player":
                if not self.char.is_alive():
                    continue
                if self.player_stun > 0:
                    self.player_stun -= 1
                    self._log("system", "你被震慑，无法行动！")
                    continue
                self._do_player(plan)
            else:
                enemy, intent = payload
                if not enemy.is_alive():
                    continue
                if enemy.stun_rounds > 0:
                    enemy.stun_rounds -= 1
                    self._log("player", f"{enemy.name} 被眩晕，行动中断。")
                    continue
                self._do_enemy(enemy, intent)
            self._check_end()

        if self.status == "active":
            self._end_round()

        return self._result(events_start)

    def _prepare_player_action(self, action: dict) -> dict:
        kind = action.get("action")
        if kind == "attack":
            return {"kind": "attack", "target": action.get("target")}
        if kind == "skill":
            skill = skill_map().get(action.get("skill_id"))
            if not skill:
                raise ValueError("未知技能")
            if not skill_mod.is_known(self.char, skill["id"]):
                raise ValueError("尚未学会该技能")
            state = self.char.skills[skill["id"]]
            cost = skill_mod.mp_cost(skill, state["level"])
            if self.char.mp < cost:
                raise ValueError("法力不足")
            return {"kind": "skill", "skill": skill, "state": state,
                    "target": action.get("target"), "cost": cost}
        if kind == "defend":
            return {"kind": "defend"}
        if kind == "dodge":
            return {"kind": "dodge"}
        if kind == "item":
            item_id = action.get("item_id")
            entry = next((i for i in self.char.inventory
                          if i["type"] == "consumable" and i["item_id"] == item_id), None)
            if not entry:
                raise ValueError("没有这件道具")
            return {"kind": "item", "item_id": item_id, "entry": entry}
        raise ValueError("未知行动")

    # ---------- 玩家行动 ----------
    def _do_player(self, plan: dict) -> None:
        kind = plan["kind"]
        if kind == "attack":
            target = self._pick_target(plan.get("target"))
            if target:
                self._player_hit(target, 1.0, "普通攻击")
            return

        if kind == "defend":
            self.defending = True
            restored = self.char.restore_mp(int(self.char.max_mp * 0.08))
            self._log("player", f"你举盾防御，防御力提升 60%" + (f"，回复 {restored} 点法力。" if restored else "。"))
            return

        if kind == "dodge":
            self._add_buff("dodge", 0.35, 2, "闪避姿态")
            self._log("player", "你压低身形进入闪避姿态，闪避率大幅提升（2 回合）。")
            return

        if kind == "item":
            self._use_item(plan["item_id"], plan["entry"])
            return

        if kind == "skill":
            skill = plan["skill"]
            state = plan["state"]
            self.char.mp -= plan["cost"]
            self._log("player", f"你施展【{skill['name']}】(Lv.{state['level']})。", skill=skill["name"])
            self._cast_player_skill(skill, state, plan.get("target"))
            train = skill_mod.train(self.char, skill["id"])
            if train.get("level_up"):
                self._log("system", f"✨ 技能【{train['name']}】熟练度提升至 Lv.{train['level']}！", level_up=True)

    def _player_hit(self, target: Enemy, power: float, label: str,
                    crit_bonus: float = 0.0, pierce: float = 0.0) -> int:
        if random.random() * 100 < target.dodge:
            self._log("enemy", f"{target.name} 闪避了你的{label}！", miss=True, target=target.index)
            return 0
        damage, crit = roll_damage(
            self.player_stats()["atk"], power, target.defense,
            pierce=pierce, crit_chance=self.player_stats()["crit"] + crit_bonus,
        )
        dealt = target.take_damage(damage)
        self._log("player", f"{label}命中 {target.name}，造成 {dealt} 点伤害" + ("（暴击！）" if crit else "。"),
                  dmg=dealt, crit=crit, target=target.index)
        return dealt

    def _cast_player_skill(self, skill: dict, state: dict, target_index: int | None) -> None:
        level = state["level"]
        power = skill_mod.power_of(skill, level)
        effects = skill.get("effects", [])
        skill_type = skill["type"]

        # 纯辅助技能
        if skill_type in ("heal", "buff"):
            self._apply_player_effects(effects, None, skill["name"])
            return

        crit_bonus = sum(e.get("value", 0) for e in effects if e["kind"] == "crit_bonus")
        pierce = skill_mod.pierce_of(skill, level)
        hits = max(1, int(skill.get("hits", 1)))
        targets = self._alive_enemies() if skill.get("aoe") else [self._pick_target(target_index)]
        targets = [t for t in targets if t]
        if not targets:
            return

        def power_vs(target: Enemy) -> float:
            """斩首 / 裁决等条件增伤在这里结算。"""
            value = power
            for effect in effects:
                if effect["kind"] == "execute" and target.hp / target.max_hp <= effect["threshold"]:
                    value *= 1 + effect["bonus"]
                if effect["kind"] == "bonus_vs_debuff":
                    has_debuff = bool(target.dots) or any(b["pct"] < 0 for b in target.buffs)
                    if has_debuff:
                        value *= 1 + effect["bonus"]
            return value

        total = 0
        if skill.get("aoe") and hits == 1:
            # 群体技能：每个存活敌人各吃一次伤害
            for target in list(self._alive_enemies()):
                total += self._player_hit(target, power_vs(target), skill["name"],
                                          crit_bonus=crit_bonus, pierce=pierce)
        else:
            for hit in range(hits):
                alive = self._alive_enemies()
                if not alive:
                    break
                if skill.get("aoe"):
                    # 群体多段：每段重新挑选目标，优先打还站着的
                    target = random.choice(alive)
                elif not targets[0].is_alive():
                    # 主目标已倒下：段数转到下一个存活目标，而不是继续鞭尸
                    target = alive[0]
                else:
                    target = targets[0]
                label = f"{skill['name']}·第 {hit + 1} 段" if hits > 1 else skill["name"]
                total += self._player_hit(target, power_vs(target), label,
                                          crit_bonus=crit_bonus, pierce=pierce)

        # 伤害后的附加效果作用于主目标（AOE 则全部）
        effect_targets = self._alive_enemies() if skill.get("aoe") else [t for t in targets if t.is_alive()]
        for enemy in effect_targets:
            self._apply_player_effects(effects, enemy, skill["name"])

        lifesteal = skill.get("lifesteal")
        if lifesteal and total:
            healed = self.char.heal(int(total * lifesteal))
            if healed:
                self._log("player", f"吸取生命，回复 {healed} 点生命。", heal=healed)

    def _apply_player_effects(self, effects: list[dict], enemy: Enemy | None, skill_name: str) -> None:
        for effect in effects:
            kind = effect["kind"]
            chance = effect.get("chance", 1.0)
            if kind == "crit_bonus":
                continue
            if kind == "execute":
                continue
            if random.random() > chance:
                continue
            if kind == "buff":
                stat = effect["stat"]
                if stat == "dodge":
                    self._add_buff("dodge", effect["pct"], effect["rounds"], skill_name)
                else:
                    self._add_buff(stat, effect["pct"], effect["rounds"], skill_name)
                label = {"atk": "攻击", "def": "防御", "agi": "敏捷", "dodge": "闪避"}.get(stat, stat)
                self._log("player", f"你获得【{label}提升 {_pct(effect['pct'])}】，持续 {effect['rounds']} 回合。")
            elif kind == "shield":
                amount = int(self.char.max_hp * effect["pct"])
                self.player_shield += amount
                self._log("player", f"你获得 {amount} 点护盾。", shield=amount)
            elif kind == "heal":
                amount = int(self.char.max_hp * effect.get("pct", 0)) + effect.get("flat", 0)
                healed = self.char.heal(amount)
                self._log("player", f"圣光回复了你 {healed} 点生命。", heal=healed)
            elif kind == "regen":
                self._add_buff("regen", effect["pct"], effect["rounds"], skill_name)
                self._log("player", f"你获得再生效果，每回合恢复 {_pct(effect['pct'])} 最大生命。")
            elif kind == "restore_mp":
                gained = self.char.restore_mp(effect.get("flat", 0))
                if gained:
                    self._log("player", f"回复 {gained} 点法力。")
            elif kind == "cleanse":
                self.player_dots.clear()
                self.player_buffs = [b for b in self.player_buffs if b["pct"] > 0]
                self.player_stun = 0
                self._log("player", "净化之光驱散了所有负面状态。")
            elif kind in ("debuff", "dot", "stun") and enemy and enemy.is_alive():
                if kind == "debuff":
                    enemy.buffs.append({
                        "stat": effect["stat"], "pct": effect["pct"],
                        "rounds": effect["rounds"], "expires": self.round + effect["rounds"],
                    })
                    label = {"atk": "攻击", "def": "防御", "agi": "敏捷"}.get(effect["stat"], effect["stat"])
                    self._log("enemy", f"{enemy.name} 的{label}下降 {_pct(abs(effect['pct']))}。", target=enemy.index)
                elif kind == "dot":
                    enemy.dots.append({
                        "id": effect["id"], "rounds": effect["rounds"],
                        "expires": self.round + effect["rounds"],
                    })
                    name = "中毒" if effect["id"] == "poison" else "灼烧"
                    self._log("enemy", f"{enemy.name} 陷入【{name}】。", target=enemy.index)
                elif kind == "stun":
                    enemy.stun_rounds += effect["rounds"]
                    self._log("enemy", f"{enemy.name} 被眩晕了！", target=enemy.index)

    def _use_item(self, item_id: str, entry: dict) -> None:
        base = consumables()[item_id]
        if base.get("full"):
            healed = self.char.heal(self.char.max_hp)
            restored = self.char.restore_mp(self.char.max_mp)
        else:
            healed = self.char.heal(base.get("heal_hp", 0))
            restored = self.char.restore_mp(base.get("heal_mp", 0))
        if base.get("cleanse"):
            self.player_dots.clear()
            self.player_buffs = [b for b in self.player_buffs if b["pct"] > 0]
            self.player_stun = 0
        entry["qty"] -= 1
        if entry["qty"] <= 0:
            self.char.inventory.remove(entry)
        parts = []
        if healed:
            parts.append(f"生命 +{healed}")
        if restored:
            parts.append(f"法力 +{restored}")
        if base.get("cleanse"):
            parts.append("解除负面状态")
        self._log("player", f"使用【{base['name']}】：" + ("、".join(parts) if parts else "没有效果") + "。")

    def _try_flee(self) -> None:
        if self.is_boss:
            self._log("system", "Boss 的气息锁定了你，无法逃脱！")
            intents = [(e, self._choose_enemy_action(e)) for e in self._alive_enemies()]
            for enemy, intent in intents:
                if self.status == "active":
                    self._do_enemy(enemy, intent)
            self._check_end()
            if self.status == "active":
                self._end_round()
            return
        player_agi = self.player_stats()["agi"]
        enemy_agi = max((e.agi for e in self._alive_enemies()), default=1)
        chance = max(0.2, min(0.85, 0.5 + (player_agi - enemy_agi) * 0.012))
        if random.random() < chance:
            self.status = "fled"
            self.escaped = True
            self._log("system", "你成功脱离了战斗。")
        else:
            self._log("system", "逃跑失败！")
            for enemy, intent in [(e, self._choose_enemy_action(e)) for e in self._alive_enemies()]:
                if self.status == "active":
                    self._do_enemy(enemy, intent)
            self._check_end()
            if self.status == "active":
                self._end_round()

    # ---------- 敌人行动 ----------
    def _choose_enemy_action(self, enemy: Enemy) -> dict:
        # 冷却未走完 / 本场次数用尽的技能直接排除，避免「治疗无 CD」把战斗锁死
        usable = [s for s in enemy.skills if enemy.skill_ready(s, self.round)]
        heal_skills = [s for s in usable if s.get("type") == "heal"]
        if heal_skills and enemy.hp / enemy.max_hp < 0.45 and random.random() < 0.7:
            return {"kind": "skill", "skill": random.choice(heal_skills)}
        for skill in usable:
            if random.random() < skill.get("chance", 0.3):
                return {"kind": "skill", "skill": skill}
        return {"kind": "attack", "skill": None}

    def _do_enemy(self, enemy: Enemy, intent: dict) -> None:
        # Boss 狂暴
        if enemy.enrage_at and not enemy.enraged and enemy.hp / enemy.max_hp <= enemy.enrage_at:
            enemy.enraged = True
            enemy.buffs.append({"stat": "atk", "pct": 0.35, "rounds": 999,
                                "expires": self.round + 999})
            self._log("system", f"💢 {enemy.name} 进入狂暴状态，攻击力大幅提升！", enrage=True)

        if intent["kind"] == "skill":
            skill = intent["skill"]
            name = skill["name"]
            enemy.note_skill_used(skill, self.round)
            if skill.get("type") == "heal":
                amount = int(enemy.max_hp * skill.get("heal_pct", 0.1))
                healed = enemy.heal(amount)
                self._log("enemy", f"{enemy.name} 使用【{name}】，回复 {healed} 点生命。", target=enemy.index)
                return
            if skill.get("type") == "buff":
                for effect in skill.get("effects", []):
                    enemy.buffs.append({
                        "stat": effect["stat"], "pct": effect["pct"],
                        "rounds": effect["rounds"], "expires": self.round + effect["rounds"],
                    })
                self._log("enemy", f"{enemy.name} 使用【{name}】，气势攀升！", target=enemy.index)
                return

            self._log("enemy", f"{enemy.name} 使用【{name}】。", target=enemy.index)
            power = skill.get("power", 1.0)
            pierce = skill_mod.pierce_of(skill, 1)
            hits = max(1, int(skill.get("hits", 1)))
            total = 0
            for _ in range(hits):
                if not self.char.is_alive():
                    break
                total += self._enemy_hit(enemy, power, pierce)
            if skill.get("lifesteal") and total:
                healed = enemy.heal(int(total * skill["lifesteal"]))
                if healed:
                    self._log("enemy", f"{enemy.name} 吸取了 {healed} 点生命。", target=enemy.index)
            for effect in skill.get("effects", []):
                if random.random() <= effect.get("chance", 1.0):
                    self._apply_enemy_effect(enemy, effect)
        else:
            self._enemy_hit(enemy, 1.0, 0.0)

    def _enemy_hit(self, enemy: Enemy, power: float, pierce: float) -> int:
        stats = self.player_stats()
        if random.random() * 100 < stats["dodge"]:
            self._log("player", f"你侧身闪避了 {enemy.name} 的攻击！", dodge=True, target=enemy.index)
            return 0
        damage, crit = roll_damage(enemy.atk, power, stats["def"], pierce=pierce, crit_chance=enemy.crit)
        if self.player_shield > 0:
            absorbed = min(self.player_shield, damage)
            self.player_shield -= absorbed
            damage -= absorbed
            if absorbed:
                self._log("player", f"护盾吸收了 {absorbed} 点伤害。")
        dealt = self.char.take_damage(damage)
        self._log("enemy", f"{enemy.name} 命中你，造成 {dealt} 点伤害" + ("（暴击！）" if crit else "。"),
                  dmg=dealt, crit=crit, target=enemy.index)
        return dealt

    def _apply_enemy_effect(self, enemy: Enemy, effect: dict) -> None:
        kind = effect["kind"]
        if kind == "buff":
            enemy.buffs.append({
                "stat": effect["stat"], "pct": effect["pct"],
                "rounds": effect["rounds"], "expires": self.round + effect["rounds"],
            })
        elif kind == "debuff":
            self._add_buff(effect["stat"], effect["pct"], effect["rounds"], enemy.name)
            label = {"atk": "攻击", "def": "防御", "agi": "敏捷"}.get(effect["stat"], effect["stat"])
            self._log("system", f"你的{label}下降 {_pct(abs(effect['pct']))}。")
        elif kind == "dot":
            self.player_dots.append({
                "id": effect["id"], "rounds": effect["rounds"],
                "expires": self.round + effect["rounds"],
            })
            name = "中毒" if effect["id"] == "poison" else "灼烧"
            self._log("system", f"你陷入【{name}】状态。")
        elif kind == "stun":
            self.player_stun += effect["rounds"]
            self._log("system", "你被震慑，下回合无法行动！")

    # ---------- 回合结束 ----------
    def _end_round(self) -> None:
        # 持续伤害
        for dot in list(self.player_dots):
            if dot["expires"] <= self.round:
                continue
            pct = 0.05 if dot["id"] == "poison" else 0.04
            damage = max(1, int(self.char.max_hp * pct))
            self.char.take_damage(damage)
            name = "中毒" if dot["id"] == "poison" else "灼烧"
            self._log("system", f"你因【{name}】损失 {damage} 点生命。", dmg=damage)
        for enemy in self._alive_enemies():
            for dot in list(enemy.dots):
                if dot["expires"] <= self.round:
                    continue
                pct = 0.05 if dot["id"] == "poison" else 0.04
                damage = max(1, int(enemy.max_hp * pct))
                enemy.take_damage(damage)
                name = "中毒" if dot["id"] == "poison" else "灼烧"
                self._log("enemy", f"{enemy.name} 因【{name}】损失 {damage} 点生命。",
                          dmg=damage, target=enemy.index)

        # 再生
        for buff in self.player_buffs:
            if buff["stat"] == "regen" and buff["expires"] > self.round:
                healed = self.char.heal(int(self.char.max_hp * buff["pct"]))
                if healed:
                    self._log("player", f"再生效果回复 {healed} 点生命。", heal=healed)

        self._check_end()
        if self.status != "active":
            return

        # 过期清理
        self.player_buffs = [b for b in self.player_buffs if b["expires"] > self.round]
        self.player_dots = [d for d in self.player_dots if d["expires"] > self.round]
        for enemy in self.enemies:
            enemy.buffs = [b for b in enemy.buffs if b["expires"] > self.round]
            enemy.dots = [d for d in enemy.dots if d["expires"] > self.round]

        self.defending = False
        self.round += 1
        self._log("system", f"—— 第 {self.round} 回合 ——")

    def _check_end(self) -> None:
        if self.status != "active":
            return
        if not self.char.is_alive():
            self.status = "lost"
            self.char.deaths += 1
            self._log("system", "你倒下了……意识陷入黑暗。")
            return
        if not self._alive_enemies():
            self.status = "won"
            self._settle_victory()

    # ---------- 结算 ----------
    def _settle_victory(self) -> None:
        exp = sum(e.exp for e in self.enemies)
        gold = sum(e.gold for e in self.enemies)
        drops: list[dict] = []
        area = area_def(self.area_id)

        for enemy in self.enemies:
            self.char.kills += 1
            if enemy.is_boss:
                self.char.boss_kills += 1
            for drop in enemy.drops:
                if random.random() <= drop.get("chance", 0):
                    qty = drop.get("qty", 1)
                    if equip_mod.add_consumable(self.char, drop["item"], qty):
                        drops.append({
                            "type": "consumable", "item_id": drop["item"], "qty": qty,
                            "name": consumables()[drop["item"]]["name"],
                            "emoji": consumables()[drop["item"]]["emoji"],
                        })
            if enemy.guaranteed_equipment:
                item = equip_mod.roll_equipment(
                    area["tier"], max(1, enemy.level), self.char.class_id,
                    min_rarity="rare", luck=0.5,
                )
                if equip_mod.add_item(self.char, item):
                    drops.append(item)
                else:
                    self.char.gold += item["price"]
                    drops.append({"type": "gold_convert", "name": item["name"], "gold": item["price"]})

        self.char.gold += gold
        level_ups = self.char.gain_exp(exp)
        unlocked = skill_mod.unlock_for_level(self.char)

        self._log("system", f"战斗胜利！获得 {exp} 经验、{gold} 金币。", exp=exp, gold=gold)
        for item in drops:
            if item["type"] == "gold_convert":
                self._log("loot", f"背包已满，【{item['name']}】自动折算为 {item['gold']} 金币。", item=item)
            else:
                self._log("loot", f"获得【{item['name']}】×{item.get('qty', 1)}。", item=item)
        for up in level_ups:
            self._log("system", f"🎉 升级！当前等级 Lv.{up['level']}，获得 3 点属性点。", level_up=True)
        for skill in unlocked:
            self._log("system", f"📖 解锁新技能【{skill['name']}】！", skill=skill)

        self.rewards = {
            "exp": exp,
            "gold": gold,
            "drops": drops,
            "level_ups": level_ups,
            "unlocked_skills": unlocked,
            "boss_defeated": self.is_boss,
        }

    # ---------- 输出 ----------
    def _result(self, events_start: int) -> dict:
        return {
            "battle": self.view(),
            "events": self.log[events_start:],
        }

    def view(self) -> dict:
        stats = self.player_stats()
        return {
            "round": self.round,
            "status": self.status,
            "is_boss": self.is_boss,
            "boss_id": self.boss_id,
            "area_id": self.area_id,
            "area_name": area_def(self.area_id)["name"],
            "player": {
                "hp": self.char.hp,
                "mp": self.char.mp,
                "max_hp": stats["max_hp"],
                "max_mp": stats["max_mp"],
                "atk": int(round(stats["atk"])),
                "def": int(round(stats["def"])),
                "agi": int(round(stats["agi"])),
                "crit": stats["crit"],
                "dodge": round(stats["dodge"], 1),
                "shield": self.player_shield,
                "defending": self.defending,
                "buffs": [
                    {"stat": b["stat"], "pct": b["pct"], "rounds": max(1, b["expires"] - self.round),
                     "name": b.get("name", "")}
                    for b in self.player_buffs
                ],
                "dots": [
                    {"id": d["id"], "rounds": max(1, d["expires"] - self.round)}
                    for d in self.player_dots
                ],
                "stunned": self.player_stun > 0,
            },
            "enemies": [e.view() for e in self.enemies],
            "log": self.log[-60:],
            "rewards": self.rewards,
            "can_flee": not self.is_boss,
        }

    def to_dict(self) -> dict:
        return {
            "area_id": self.area_id,
            "round": self.round,
            "status": self.status,
            "is_boss": self.is_boss,
            "boss_id": self.boss_id,
            "log": self.log[-MAX_LOG:],
            "player_buffs": self.player_buffs,
            "player_dots": self.player_dots,
            "player_shield": self.player_shield,
            "player_stun": self.player_stun,
            "defending": self.defending,
            "rewards": self.rewards,
            "enemies": [e.to_dict() for e in self.enemies],
        }

    @classmethod
    def from_dict(cls, data: dict, char: Character) -> "Battle":
        battle = cls.__new__(cls)
        battle.char = char
        battle.area_id = data["area_id"]
        battle.round = data.get("round", 1)
        battle.status = data.get("status", "active")
        battle.is_boss = data.get("is_boss", False)
        battle.boss_id = data.get("boss_id")
        battle.log = list(data.get("log", []))
        battle.player_buffs = list(data.get("player_buffs", []))
        battle.player_dots = list(data.get("player_dots", []))
        battle.player_shield = int(data.get("player_shield", 0))
        battle.player_stun = int(data.get("player_stun", 0))
        battle.defending = bool(data.get("defending", False))
        battle.rewards = data.get("rewards")
        battle.enemies = [Enemy.from_dict(e) for e in data.get("enemies", [])]
        battle.escaped = False
        return battle
