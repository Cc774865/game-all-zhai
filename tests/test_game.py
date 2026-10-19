"""核心逻辑测试：内容完整性、成长、战斗、掉落、存档往返与中断续玩。

运行：python tests/test_game.py
"""
from __future__ import annotations

import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.data_loader import area_map, areas, classes, enemy_def, skills
from backend.game import GameService
from backend.modules import equipment as equip_mod
from backend.modules import save as save_mod
from backend.modules.battle import Battle
from backend.modules.character import Character, exp_to_next


def make_hero(class_id: str = "warrior", level: int = 1) -> Character:
    char = Character("测试者", class_id)
    char.level = level
    char.hp = char.max_hp
    char.mp = char.max_mp
    from backend.modules import skill as skill_mod
    skill_mod.unlock_for_level(char)
    return char


def auto_battle(battle: Battle, max_rounds: int = 200) -> Battle:
    """自动战斗策略，用于跑通流程与观察节奏。"""
    while battle.status == "active" and battle.round <= max_rounds:
        char = battle.char
        heal_item = next((i for i in char.inventory
                          if i["type"] == "consumable" and i.get("item_id") in ("potion_hp", "potion_hp_big")), None)
        if char.hp / char.max_hp < 0.35 and heal_item:
            battle.player_action({"action": "item", "item_id": heal_item["item_id"]})
            continue
        heal_skill = next((s for s in char.skills
                           if s.startswith("cle_heal") and char.mp >= 11), None)
        if heal_skill and char.hp / char.max_hp < 0.45:
            battle.player_action({"action": "skill", "skill_id": heal_skill})
            continue
        usable = [
            (sid, state) for sid, state in char.skills.items()
            if char.mp >= next(s["mp"] for s in skills() if s["id"] == sid)
            and next(s for s in skills() if s["id"] == sid)["type"] in ("physical", "magic")
        ]
        if usable:
            sid = max(usable, key=lambda item: next(
                s["power"] for s in skills() if s["id"] == item[0]) * (1 + 0.15 * (item[1]["level"] - 1)))[0]
            battle.player_action({"action": "skill", "skill_id": sid})
        else:
            battle.player_action({"action": "attack"})
    return battle


class ContentTest(unittest.TestCase):
    def test_counts(self):
        self.assertEqual(len(classes()), 4, "必须有 4 种职业")
        self.assertEqual(len(areas()), 10, "必须有 10 个地图区域")
        bosses = [a for a in areas() if a["boss"]]
        self.assertEqual(len(bosses), 9, "必须有 9 个 Boss")
        self.assertEqual(len({a["boss"] for a in bosses}), 9, "Boss 不可重复")
        self.assertEqual(len(skills()), 24, "4 职业 × 6 技能")

    def test_references(self):
        for area in areas():
            for enemy_id in area["enemies"]:
                self.assertTrue(enemy_def(enemy_id)["hp"] > 0)
            if area["boss"]:
                self.assertIn("title", enemy_def(area["boss"]))
        for skill in skills():
            self.assertIn(skill["class"], classes())
            self.assertGreaterEqual(skill["unlock_level"], 1)

    def test_each_class_has_six_skills(self):
        for class_id in classes():
            owned = [s for s in skills() if s["class"] == class_id]
            self.assertEqual(len(owned), 6, f"{class_id} 应有 6 个技能")
            self.assertEqual(sorted(s["unlock_level"] for s in owned), [1, 3, 5, 8, 12, 16])


class CharacterTest(unittest.TestCase):
    def test_growth(self):
        char = make_hero("warrior", 1)
        base_hp = char.max_hp
        events = char.gain_exp(exp_to_next(1) + 10)
        self.assertEqual(char.level, 2)
        self.assertEqual(char.points, 3)
        self.assertGreater(char.max_hp, base_hp)
        self.assertTrue(events)

    def test_allocate(self):
        char = make_hero("mage", 2)
        char.points = 2
        atk = char.atk
        char.allocate("atk")
        self.assertEqual(char.atk, atk + 2)
        self.assertEqual(char.points, 1)

    def test_equipment_changes_stats(self):
        char = make_hero("warrior", 5)
        item = equip_mod.make_item("w_steel_blade", "rare", 5)
        char.inventory.append(item)
        before = char.atk
        equip_mod.equip_item(char, item["uid"])
        self.assertGreater(char.atk, before)
        self.assertIsNotNone(char.equipment["weapon"])
        equip_mod.unequip(char, "weapon")
        self.assertIsNone(char.equipment["weapon"])
        self.assertEqual(char.atk, before)


class BattleTest(unittest.TestCase):
    def setUp(self):
        random.seed(20261019)

    def test_battle_to_victory(self):
        char = make_hero("warrior", 5)
        battle = Battle(char, ["e_wolf"], "forest")
        auto_battle(battle)
        self.assertEqual(battle.status, "won")
        self.assertGreater(char.exp, 0)
        self.assertGreater(char.gold, 120)
        self.assertTrue(battle.rewards["exp"] > 0)

    def test_dodge_action(self):
        char = make_hero("ranger", 8)
        battle = Battle(char, ["e_bandit"], "forest")
        result = battle.player_action({"action": "dodge"})
        self.assertTrue(any(b["stat"] == "dodge" for b in battle.player_buffs) or
                        any("闪避" in e["text"] for e in result["events"]))

    def test_boss_flow_and_unlock(self):
        service = GameService()
        service.new_game("屠龙者", "warrior")
        service.char.level = 12
        service.char.points = 0
        service.char.hp = service.char.max_hp
        service.char.mp = service.char.max_mp
        service.world["area"] = "forest"
        service.world["unlocked"] = ["village", "forest"]
        service.do_action("challenge_boss", {})
        self.assertTrue(service.battle.is_boss)
        service.battle.enemies[0].hp = 1
        service.battle_action({"action": "attack"})
        self.assertIn("forest", service.world["bosses"])
        self.assertIn("mine", service.world["unlocked"])
        self.assertIsNone(service.battle)

    def test_defeat_revives_in_village(self):
        service = GameService()
        service.new_game("倒霉蛋", "mage")
        service.world["area"] = "void"
        service.world["unlocked"] = ["village", "void"]
        service.char.hp = 1
        service.do_action("challenge_boss", {})
        service.battle.enemies[0].base_atk = 9999
        for _ in range(10):
            if service.battle is None:
                break
            service.battle_action({"action": "attack"})
        self.assertEqual(service.world["area"], "village")
        self.assertGreater(service.char.hp, 0)
        self.assertIsNone(service.battle)


class SaveTest(unittest.TestCase):
    def tearDown(self):
        for slot in ("slot1", "slot2"):
            save_mod.delete(slot)

    def test_roundtrip(self):
        service = GameService()
        service.new_game("存档测试", "ranger")
        service.char.gold = 777
        service.char.level = 6
        service.char.hp = 66
        service.char.inventory.append(equip_mod.make_item("w_wind_bow", "epic", 6))
        service.do_action("save", {"slot": "slot1"})

        other = GameService()
        other.load_game("slot1")
        self.assertEqual(other.char.name, "存档测试")
        self.assertEqual(other.char.gold, 777)
        self.assertEqual(other.char.level, 6)
        self.assertEqual(other.char.hp, 66)
        self.assertEqual(len(other.char.inventory), 3)  # 2 种初始药水堆叠 + 1 件装备

    def test_resume_mid_battle(self):
        service = GameService()
        service.new_game("中断测试", "cleric")
        service.world["area"] = "forest"
        service.world["unlocked"] = ["village", "forest"]
        service.do_action("explore", {})
        if not service.battle:
            service.battle = Battle(service.char, ["e_boar"], "forest")
        service.battle.player_action({"action": "attack"})
        service.do_action("save", {"slot": "slot2"})

        other = GameService()
        other.load_game("slot2")
        self.assertIsNotNone(other.battle, "读档后应恢复战斗")
        self.assertEqual(other.battle.round, service.battle.round)
        self.assertEqual(other.battle.enemies[0].hp, service.battle.enemies[0].hp)


if __name__ == "__main__":
    unittest.main(verbosity=2)
