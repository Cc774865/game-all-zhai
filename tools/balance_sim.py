"""平衡模拟器：用真实战斗代码跑蒙特卡洛，给调数值提供依据。

不 mock 任何规则——直接构造 Character / Battle 打，所以模拟结果与玩家实际
体验走的是同一套代码。

用法：
    python tools/balance_sim.py                 # 默认报表
    python tools/balance_sim.py --runs 200      # 加大样本
    python tools/balance_sim.py --json out.json # 导出结果
    python tools/balance_sim.py --check         # 回归断言模式（CI 用）

判定口径：
- 「标准玩家」= 区域推荐等级**下限**、精良装备、属性点均分、4 瓶小药。
  这是「不刻意刷级也能过」的最低保障线。
- 「熟练玩家」= 推荐等级上限、稀有装备、主加攻击、3 瓶大药。
  上界参考，用来看内容会不会太简单。
"""
from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.data_loader import areas, skill_map
from backend.modules import equipment as equip_mod
from backend.modules import skill as skill_mod
from backend.modules.battle import Battle
from backend.modules.character import Character

CLASSES = ("warrior", "mage", "ranger", "cleric")
MAX_ROUNDS = 60


def build_character(class_id: str, level: int, tier: int, *, rarity: str = "uncommon",
                    alloc: str = "mix", potions: int = 4, potion_id: str = "potion_hp") -> Character:
    """按给定档位拼一个角色：等级、全槽位装备、加点、药水。"""
    char = Character("模拟", class_id)
    char.level = level
    points = 3 * (level - 1)
    if alloc == "atk":
        char.allocated["atk"] = points
    elif alloc == "hp":
        char.allocated["hp"] = points
    else:
        for key in ("atk", "hp", "def", "agi"):
            char.allocated[key] = points // 4
    skill_mod.unlock_for_level(char)

    # 每个槽位都抽一件，避免「运气好只有武器」造成的方差
    for slot in ("weapon", "armor", "accessory"):
        item = None
        for _ in range(80):
            candidate = equip_mod.roll_equipment(tier, level, class_id, min_rarity=rarity)
            if candidate["slot"] == slot:
                item = candidate
                break
        if item is None:
            continue
        item["req_level"] = 1  # 模拟里不关心门槛，只看数值强度
        char.equipment[slot] = item

    if potions:
        equip_mod.add_consumable(char, potion_id, potions)
    char.hp = char.max_hp
    char.mp = char.max_mp
    return char


def auto_play(battle: Battle, potion_id: str = "potion_hp", threshold: float = 0.4) -> str:
    """一个不聪明但稳定的机器人：血少先自愈/喝药，否则放最强的伤害技能，没蓝就平砍。

    会像真人一样使用治疗与增益技能——否则牧师这种靠奶和增益的职业
    在模拟里会被系统性低估，得出来的平衡结论是错的。
    """
    char = battle.char
    used_buffs: set[str] = set()

    while battle.status == "active" and battle.round <= MAX_ROUNDS:
        # 每回合重新筛选：蓝会被消耗掉，开局算好的可用列表很快就过期
        heal_skills = [
            s for s in skill_map().values()
            if s["id"] in char.skills and s.get("type") == "heal" and char.mp >= s["mp"]
        ]
        buff_skills = [
            s for s in skill_map().values()
            if s["id"] in char.skills and s.get("type") == "buff" and char.mp >= s["mp"]
        ]
        hp_ratio = char.hp / char.max_hp
        # 1) 血量告急：优先治疗技能，其次药水
        if hp_ratio < 0.45 and heal_skills:
            best_heal = max(heal_skills, key=lambda s: s.get("heal_pct", 0) + s.get("power", 0))
            battle.player_action({"action": "skill", "skill_id": best_heal["id"]})
            continue
        if hp_ratio < threshold and any(i.get("item_id") == potion_id for i in char.inventory):
            battle.player_action({"action": "item", "item_id": potion_id})
            continue
        # 2) 开局挂一次增益
        fresh_buffs = [s for s in buff_skills if s["id"] not in used_buffs]
        if fresh_buffs and battle.round <= 2:
            pick = fresh_buffs[0]
            used_buffs.add(pick["id"])
            battle.player_action({"action": "skill", "skill_id": pick["id"]})
            continue
        # 3) 常规输出
        usable = [
            s for s in skill_map().values()
            if s["id"] in char.skills and char.mp >= s["mp"]
            and s["type"] in ("physical", "magic")
        ]
        if usable:
            best = max(usable, key=lambda s: skill_mod.power_of(s, char.skills[s["id"]]["level"]))
            battle.player_action({"action": "skill", "skill_id": best["id"]})
        else:
            battle.player_action({"action": "attack"})
    return battle.status


def simulate(area: dict, class_id: str, level: int, runs: int, *, tier: int | None = None,
             rarity: str = "uncommon", alloc: str = "mix",
             potions: int = 4, potion_id: str = "potion_hp") -> dict:
    tier = area["tier"] if tier is None else tier
    wins = 0
    rounds = []
    for _ in range(runs):
        char = build_character(class_id, level, tier, rarity=rarity, alloc=alloc,
                              potions=potions, potion_id=potion_id)
        battle = Battle(char, [area["boss"]], area["id"], is_boss=True, boss_id=area["boss"])
        status = auto_play(battle, potion_id)
        if status == "won":
            wins += 1
            rounds.append(battle.round)
    return {
        "win_rate": wins / runs,
        "avg_rounds": round(statistics.mean(rounds), 1) if rounds else None,
        "runs": runs,
    }


def required_level(area: dict, class_id: str, runs: int, target: float = 0.5,
                   **kwargs) -> int | None:
    """二分式扫描：达到目标胜率所需的最低等级。"""
    for level in range(1, 31):
        if simulate(area, class_id, level, runs, **kwargs)["win_rate"] >= target:
            return level
    return None


def standard(area: dict, class_id: str, runs: int, **kwargs) -> dict:
    return simulate(area, class_id, area["level_range"][0], runs, **kwargs)


def veteran(area: dict, class_id: str, runs: int, **kwargs) -> dict:
    return simulate(area, class_id, area["level_range"][1], runs,
                    rarity="rare", alloc="atk", potions=3, potion_id="potion_hp_big", **kwargs)


def boss_areas() -> list[dict]:
    return [a for a in areas() if a["boss"]]


def report(runs: int) -> dict:
    out = {"runs": runs, "standard": {}, "veteran": {}, "required_level": {}}
    for area in boss_areas():
        key = area["id"]
        out["standard"][key] = {c: standard(area, c, runs) for c in CLASSES}
        out["veteran"][key] = {c: veteran(area, c, runs) for c in CLASSES}
        out["required_level"][key] = {c: required_level(area, c, max(10, runs // 4))
                                      for c in CLASSES}
    return out


def print_report(data: dict) -> None:
    areas_by_id = {a["id"]: a for a in areas()}
    print("=" * 78)
    print("标准玩家：推荐等级下限 / 精良装备 / 均分加点 / 4 瓶小药")
    print("=" * 78)
    header = f"{'守关者':<12}{'推荐':<8}" + "".join(f"{c:<10}" for c in CLASSES)
    print(header)
    for key, row in data["standard"].items():
        area = areas_by_id[key]
        boss = area["boss"]
        cells = "".join(f"{row[c]['win_rate'] * 100:>5.0f}%    " for c in CLASSES)
        print(f"{boss:<12}Lv{area['level_range'][0]:<6}{cells}")

    print()
    print("=" * 78)
    print("熟练玩家：推荐等级上限 / 稀有装备 / 主加攻击 / 3 瓶大药")
    print("=" * 78)
    print(header)
    for key, row in data["veteran"].items():
        area = areas_by_id[key]
        boss = area["boss"]
        cells = "".join(f"{row[c]['win_rate'] * 100:>5.0f}%    " for c in CLASSES)
        rounds = [row[c]["avg_rounds"] for c in CLASSES if row[c]["avg_rounds"]]
        avg = f"{statistics.mean(rounds):.1f} 回合" if rounds else "-"
        print(f"{boss:<12}Lv{area['level_range'][1]:<6}{cells}{avg}")

    print()
    print("=" * 78)
    print("达到 50% 胜率所需等级 vs 区域推荐区间")
    print("=" * 78)
    print(f"{'守关者':<12}{'推荐区间':<14}" + "".join(f"{c:<10}" for c in CLASSES))
    for key, row in data["required_level"].items():
        area = areas_by_id[key]
        lo, hi = area["level_range"]
        cells = "".join(f"{('Lv%s' % row[c]) if row[c] else '>30':<10}" for c in CLASSES)
        flag = ""
        if any(row[c] and row[c] > hi for c in CLASSES):
            flag = "  <-- 超出推荐上限"
        print(f"{area['boss']:<12}{f'{lo}-{hi}':<14}{cells}{flag}")


def check(runs: int) -> int:
    """回归断言：任何职业在推荐等级下限都应落在 30%-95% 之间。"""
    failures = []
    for area in boss_areas():
        for class_id in CLASSES:
            result = standard(area, class_id, runs)
            rate = result["win_rate"]
            if rate < 0.30:
                failures.append(f"{area['boss']} / {class_id} 太难：{rate * 100:.0f}%（下限 30%）")
            elif rate > 0.95:
                failures.append(f"{area['boss']} / {class_id} 太简单：{rate * 100:.0f}%（上限 95%）")
    if failures:
        print("[FAIL] 平衡回归未通过：")
        for line in failures:
            print("  -", line)
        return 1
    print("[OK] 平衡回归通过：所有守关者在推荐等级下限的胜率都在 30%-95% 之间。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="十域九王 平衡模拟器")
    parser.add_argument("--runs", type=int, default=120, help="每格模拟次数")
    parser.add_argument("--json", dest="json_path", help="把结果写到 JSON")
    parser.add_argument("--check", action="store_true", help="只跑回归断言，返回退出码")
    parser.add_argument("--seed", type=int, default=None, help="固定随机种子以便复现")
    args = parser.parse_args()

    if args.runs < 10:
        parser.error("--runs 至少 10，样本太小没有意义")
    if args.seed is not None:
        random.seed(args.seed)

    if args.check:
        return check(args.runs)

    data = report(args.runs)
    print_report(data)
    if args.json_path:
        with open(args.json_path, "w", encoding="utf-8") as fp:
            json.dump(data, fp, ensure_ascii=False, indent=2)
        print(f"\n结果已写入 {args.json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())