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
from backend.modules import skill as skill_mod
from backend.modules import story as story_mod
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
        service.do_action("challenge_boss", {"confirmed": True})
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
        service.do_action("challenge_boss", {"confirmed": True})
        service.battle.enemies[0].base_atk = 9999
        for _ in range(10):
            if service.battle is None:
                break
            service.battle_action({"action": "attack"})
        self.assertEqual(service.world["area"], "village")
        self.assertGreater(service.char.hp, 0)
        self.assertIsNone(service.battle)


class StoryTest(unittest.TestCase):
    """叙事：章节覆盖、目标推进、Boss 对话闸门、进区旁白只播一次、结局解锁。"""

    def test_every_area_has_chapter(self):
        for area in areas():
            chapter = story_mod.chapter_for(area["id"])
            self.assertIsNotNone(chapter, f"{area['id']} 缺少章节")
            self.assertTrue(chapter["goal"], f"{area['id']} 缺少目标文本")
            self.assertTrue(chapter["enter"], f"{area['id']} 缺少进区旁白")
            if area["boss"]:
                self.assertTrue(chapter["boss_pre"], f"{area['id']} 缺少 Boss 前对话")
                self.assertTrue(chapter["boss_post"], f"{area['id']} 缺少 Boss 后对话")

    def test_prologue_and_ending_present(self):
        self.assertTrue(story_mod.prologue()["lines"])
        self.assertTrue(story_mod.ending()["lines"])
        self.assertTrue(story_mod.ending()["epilogue"])

    def test_objective_advances_with_bosses(self):
        world = {"bosses": [], "finished": False}
        first = story_mod.objective(world)
        self.assertEqual(first["index"], 1)
        self.assertEqual(first["area"], "village")
        self.assertIn("薄雾森林", first["goal"])

        world["bosses"] = ["forest"]
        second = story_mod.objective(world)
        self.assertEqual(second["index"], 3, "村庄无 Boss，击败森林后应指向第三章")
        self.assertEqual(second["area"], "mine")

        world["bosses"] = [a["id"] for a in areas() if a["boss"]]
        world["finished"] = True
        last = story_mod.objective(world)
        self.assertTrue(last["finished"])
        self.assertEqual(last["index"], last["total"])

    def test_boss_dialogue_gate(self):
        service = GameService()
        service.new_game("对话测试", "warrior")
        service.world["area"] = "forest"
        service.world["unlocked"] = ["village", "forest"]

        res = service.do_action("challenge_boss", {})
        self.assertTrue(res.get("awaiting"), "首次挑战应先播对话")
        self.assertIn("dialogue", res)
        self.assertIsNone(service.battle, "对话阶段不应开战")

        service.do_action("challenge_boss", {"confirmed": True})
        self.assertIsNotNone(service.battle)
        self.assertTrue(service.battle.is_boss)

    def test_enter_narration_plays_once(self):
        service = GameService()
        service.new_game("旁白测试", "ranger")
        res = service.do_action("travel", {"area_id": "forest"})
        self.assertEqual(res["narration"]["kind"], "enter")
        self.assertEqual(res["narration"]["title"], "雾里的刻痕")

        service.do_action("travel", {"area_id": "village"})
        again = service.do_action("travel", {"area_id": "forest"})
        self.assertNotIn("narration", again, "重复进入不应再次播放旁白")

    def test_ending_unlocks_and_marks_seen(self):
        service = GameService()
        service.new_game("终局测试", "warrior")
        service.char.level = 20
        service.char.hp = service.char.max_hp
        service.world["area"] = "void"
        service.world["unlocked"] = ["village", "void"]
        service.world["bosses"] = [a["id"] for a in areas() if a["boss"] and a["id"] != "void"]

        service.do_action("challenge_boss", {"confirmed": True})
        service.battle.enemies[0].hp = 1
        result = service.battle_action({"action": "attack"})
        self.assertTrue(result["narration"]["ending_ready"], "击败终局 Boss 应解锁结局")

        state = service.state()
        self.assertTrue(state["story"]["ending_ready"])
        self.assertIsNotNone(state["story"]["ending"])
        self.assertTrue(state["story"]["objective"]["finished"])

        seen = service.do_action("story_seen", {"kind": "ending"})
        self.assertFalse(seen["state"]["story"]["ending_ready"], "看过的结局不应反复弹出")
        self.assertIsNone(seen["state"]["story"]["ending"])


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


class BalanceRegressionTest(unittest.TestCase):
    """数值回归：这几条对应实际出现过的「卡死 / 破功」问题，改数值时不能退化。"""

    def test_physics_has_armor_pierce(self):
        """物理技能必须有穿透，否则高护甲 Boss 对物理职业无解。

        历史问题：物理 pierce=0、法术 0.5，剑士打炽天使 Lv18 胜率 0%。
        """
        physical = [s for s in skills() if s["type"] == "physical"]
        magic = [s for s in skills() if s["type"] == "magic"]
        self.assertTrue(physical)
        for skill in physical:
            self.assertGreater(skill_mod.pierce_of(skill, 1), 0,
                               f"{skill['name']} 物理技能没有穿透")
        # 法术仍应保持穿透优势，只是不再是 0 与 50% 的二元差距
        self.assertGreater(skill_mod.pierce_of(magic[0], 1), skill_mod.pierce_of(physical[0], 1))

    def test_pierce_grows_with_proficiency(self):
        """熟练度应该让物理穿透变强，这是「练技能」的回报之一。"""
        low = skill_mod.pierce_of({"type": "physical"}, 1)
        high = skill_mod.pierce_of({"type": "physical"}, skill_mod.MAX_SKILL_LEVEL)
        self.assertGreater(high, low)
        # 显式写死的穿透优先于默认值
        self.assertEqual(skill_mod.pierce_of({"type": "magic", "pierce": 1.0}, 1), 1.0)

    def test_mana_pool_supports_boss_fight(self):
        """蓝池必须撑得住一场 Boss 战的主技能循环。

        历史问题：剑士 Lv13 只有 66 蓝，主技能 19 蓝 → 3 发就干，
        剩下 6 个回合全靠平砍，Boss 战里等于罚站。
        """
        for class_id in classes():
            char = make_hero(class_id, 13)
            dps_skills = [
                s for s in skills()
                if s["class"] == class_id and s["type"] in ("physical", "magic")
            ]
            self.assertTrue(dps_skills, f"{class_id} 没有伤害技能")
            avg_cost = sum(s["mp"] for s in dps_skills) / len(dps_skills)
            casts = char.max_mp / avg_cost
            self.assertGreaterEqual(
                casts, 8,
                f"{class_id} 满蓝只够放 {casts:.1f} 次技能，Boss 战会长期罚站",
            )

    def test_no_class_locked_out_of_final_boss(self):
        """任何职业在推荐等级都不该被 Boss 数值彻底锁死。

        历史问题：剑士打炽天使 Lv18 胜率 0%（敌方每回合自疗 300，
        而剑士单回合物理输出只有 156），等级打满也只有 55%。
        """
        final = area_map()["void"]
        for class_id in classes():
            char = make_hero(class_id, final["level_range"][1])
            battle = Battle(char, [final["boss"]], "void", is_boss=True, boss_id=final["boss"])
            # 只验证「打得动」：3 回合内伤害必须超过 Boss 的自愈能力
            before = battle.enemies[0].hp
            for _ in range(3):
                if battle.status != "active":
                    break
                self._strongest_attack(char, battle)
            self.assertLess(battle.enemies[0].hp, before, f"{class_id} 打不动终局 Boss")

    @staticmethod
    def _strongest_attack(char: Character, battle: Battle) -> None:
        usable = [
            s for s in skills()
            if s["id"] in char.skills and char.mp >= s["mp"]
            and s["type"] in ("physical", "magic")
        ]
        if usable:
            best = max(usable, key=lambda s: skill_mod.power_of(s, char.skills[s["id"]]["level"]))
            battle.player_action({"action": "skill", "skill_id": best["id"]})
        else:
            battle.player_action({"action": "attack"})

    def test_enemy_heal_has_cooldown(self):
        """敌方治疗必须受冷却或次数限制，否则治疗量高于玩家 DPS 时无解。"""
        for area in areas():
            if not area["boss"]:
                continue
            for skill in enemy_def(area["boss"]).get("skills", []):
                if skill.get("type") == "heal":
                    self.assertTrue(
                        skill.get("cooldown") or skill.get("max_uses"),
                        f"{area['boss']} 的【{skill['name']}】治疗没有冷却也没有次数限制",
                    )

    def test_multi_hit_skill_switches_target(self):
        """多段技能在主目标倒下后应转火，而不是继续鞭尸。

        历史问题：targets[0] if not alive else targets[0] 是恒等表达式，
        第 2 段仍记在 0 血目标上，实际伤害凭空消失。
        """
        char = make_hero("warrior", 10)
        char.allocated["atk"] = 20
        battle = Battle(char, ["e_wolf", "e_boar"], "forest")
        battle.enemies[0].hp = 1
        multi = next(s for s in skills()
                     if s["class"] == "warrior" and s.get("hits", 1) > 1)
        battle.player_action({"action": "skill", "skill_id": multi["id"]})
        second = battle.enemies[1]
        self.assertLess(
            second.hp, second.max_hp,
            "主目标死亡后，剩余段数没有打到别的敌人",
        )


class ShopEconomyTest(unittest.TestCase):
    """商店买卖不能形成正收益循环。"""

    def test_cannot_profit_by_reselling(self):
        """历史问题：买入按模板标价 60、卖出按当前等级生成价 45%（Lv23 时 62），
        高等级玩家可以无限刷金币。"""
        char = make_hero("warrior", 23)
        char.gold = 1000
        template_id = "w_iron_sword"
        for _ in range(3):
            gold_before = char.gold
            bought = equip_mod.buy(char, template_id)
            sold = equip_mod.sell_item(char, bought["item"]["uid"])
            gained = sold["gold"] - bought["gold"]
            self.assertLessEqual(
                gained, 0,
                f"买入 {bought['gold']} 卖出 {sold['gold']}，每轮净赚 {gained}",
            )
            # 余额必须严格等于「初始 - 买入 + 卖出」，一分钱都不能凭空出现
            self.assertEqual(char.gold, gold_before - bought["gold"] + sold["gold"])

    def test_shop_quotes_match_generated_price(self):
        """报价必须与真正生成的那件物品同价，否则差价就是刷钱漏洞。"""
        for level in (1, 10, 23):
            stock = {s["item_id"]: s for s in equip_mod.shop_stock(level)}
            for template in equip_mod.equipment_templates():
                if template["tier"] != 1:
                    continue
                actual = equip_mod.make_item(template["id"], "common", level)
                self.assertEqual(
                    stock[template["id"]]["price"], actual["price"],
                    f"Lv{level} 的【{template['name']}】报价与实际生成价不一致",
                )


class BalanceSimTest(unittest.TestCase):
    """跑真实战斗模拟，守住整体难度曲线（样本较小，只抓大幅偏移）。"""

    RUNS = 24
    FLOOR = 0.20   # 推荐等级下限，任何职业都不该低于这个胜率
    CEILING = 1.0

    def test_win_rate_floor_across_bosses(self):
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from tools.balance_sim import standard

        random.seed(20261020)
        failures = []
        for area in areas():
            if not area["boss"]:
                continue
            for class_id in classes():
                rate = standard(area, class_id, self.RUNS)["win_rate"]
                if rate < self.FLOOR:
                    failures.append(f"{area['boss']}/{class_id} = {rate * 100:.0f}%")
        self.assertFalse(
            failures,
            "以下组合在推荐等级下限过难（<20%），等于卡关：" + "；".join(failures),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
