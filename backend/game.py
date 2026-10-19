"""游戏服务层：串联角色、地图、战斗、装备、技能与存档，对外暴露统一操作接口。"""
from __future__ import annotations

import time

from .data_loader import area_def, area_map, class_def, classes, enemy_def
from .modules import equipment as equip_mod
from .modules import map as map_mod
from .modules import save as save_mod
from .modules import skill as skill_mod
from .modules.battle import Battle
from .modules.character import Character

VERSION = "1.0.0"


class GameError(ValueError):
    """可直接展示给玩家的业务错误。"""


class GameService:
    def __init__(self):
        self.char: Character | None = None
        self.world: dict | None = None
        self.battle: Battle | None = None
        self.session_start = time.time()
        self.last_message: str = ""

    # ---------- 基础 ----------
    def _require(self) -> None:
        if not self.char or not self.world:
            raise GameError("还没有进行中的游戏")

    def _playtime(self) -> int:
        base = int(self.world.get("playtime", 0)) if self.world else 0
        return base + int(time.time() - self.session_start)

    def _meta(self) -> dict:
        area = area_def(self.world["area"])
        return {
            "name": self.char.name,
            "class_id": self.char.class_id,
            "class_name": self.char.cls["name"],
            "class_emoji": self.char.cls["emoji"],
            "level": self.char.level,
            "area_name": area["name"],
            "gold": self.char.gold,
            "playtime": self._playtime(),
            "finished": bool(self.world.get("finished")),
        }

    def _payload(self) -> tuple[dict, dict, dict | None]:
        battle = self.battle.to_dict() if self.battle and self.battle.status == "active" else None
        return self.char.to_dict(), dict(self.world), battle

    def autosave(self) -> None:
        if not self.char:
            return
        self.world["playtime"] = self._playtime()
        char, world, battle = self._payload()
        save_mod.save("auto", char, world, battle, self._meta())

    # ---------- 新游戏 / 读档 ----------
    def new_game(self, name: str, class_id: str) -> dict:
        if class_id not in classes():
            raise GameError("请选择一个有效职业")
        char = Character(name, class_id)
        cls = class_def(class_id)
        for slot, template_id in cls.get("start_equipment", {}).items():
            item = equip_mod.make_item(template_id, "common", 1)
            char.equipment[slot] = item
        for item_id, qty in cls.get("start_items", {}).items():
            equip_mod.add_consumable(char, item_id, qty)
        char.hp = char.max_hp
        char.mp = char.max_mp
        skill_mod.unlock_for_level(char)

        self.char = char
        self.world = map_mod.initial_world()
        self.battle = None
        self.session_start = time.time()
        self.last_message = f"{char.name} 的旅程开始了。"
        self.autosave()
        return self.state()

    def load_game(self, slot: str) -> dict:
        data = save_mod.load(slot)
        if not data:
            raise GameError("该存档不存在")
        char = Character.from_dict(data["character"])
        self.char = char
        self.world = data.get("world") or map_mod.initial_world()
        self.world.setdefault("playtime", 0)
        self.world.setdefault("bosses", [])
        self.world.setdefault("visited", [])
        self.world.setdefault("unlocked", ["village"])
        self.world.setdefault("finished", False)
        self.battle = None
        battle_data = data.get("battle")
        if battle_data and battle_data.get("status") == "active":
            self.battle = Battle.from_dict(battle_data, char)
        skill_mod.unlock_for_level(char)
        self.session_start = time.time()
        self.last_message = f"读取存档：{char.name} · Lv.{char.level}"
        return self.state()

    def leave(self) -> dict:
        """返回标题界面：清空内存会话（存档文件保留）。"""
        if self.char:
            self.world["playtime"] = self._playtime()
            self.autosave()
        self.char = None
        self.world = None
        self.battle = None
        self.last_message = "已返回标题界面。"
        return self.state()

    def save_game(self, slot: str) -> dict:
        self._require()
        if slot == "auto":
            raise GameError("自动存档不可手动覆盖，请选择 1-3 号槽位")
        self.world["playtime"] = self._playtime()
        char, world, battle = self._payload()
        info = save_mod.save(slot, char, world, battle, self._meta())
        self.last_message = f"已保存到 {slot.replace('slot', '槽位 ')}"
        return {"save": info, "state": self.state()}

    def delete_save(self, slot: str) -> dict:
        if slot == "auto":
            raise GameError("自动存档不可删除")
        save_mod.delete(slot)
        return self.state()

    # ---------- 状态输出 ----------
    def state(self) -> dict:
        if not self.char or not self.world:
            return {
                "active": False,
                "version": VERSION,
                "saves": save_mod.list_saves(),
                "message": self.last_message,
            }
        area = area_def(self.world["area"])
        boss_preview = None
        if area["boss"] and area["id"] not in self.world["bosses"]:
            b = enemy_def(area["boss"])
            boss_preview = {
                "id": b["id"], "name": b["name"], "emoji": b["emoji"],
                "level": b["level"], "hp": b["hp"], "title": b.get("title", ""),
            }
        return {
            "active": True,
            "version": VERSION,
            "character": self.char.view(),
            "world": map_mod.world_view(self.world),
            "area": {
                "id": area["id"],
                "name": area["name"],
                "emoji": area["emoji"],
                "safe": area["safe"],
                "tier": area["tier"],
                "level_range": area["level_range"],
                "desc": area["desc"],
                "features": area.get("features", []),
                "boss": boss_preview,
                "cleared": area["id"] in self.world["bosses"],
            },
            "battle": self.battle.view() if self.battle and self.battle.status == "active" else None,
            "skills": skill_mod.skill_list(self.char),
            "shop": equip_mod.shop_stock(),
            "saves": save_mod.list_saves(),
            "playtime": self._playtime(),
            "message": self.last_message,
        }

    # ---------- 世界行动 ----------
    def do_action(self, action: str, payload: dict) -> dict:
        self._require()
        # 存档/删档在战斗中同样允许，这是「中断后继续」的关键
        if action == "save":
            return self.save_game(payload.get("slot", ""))
        if action == "delete_save":
            return {"state": self.delete_save(payload.get("slot", ""))}
        if self.battle and self.battle.status == "active":
            raise GameError("战斗中无法进行其他操作")
        handler = {
            "explore": self._explore,
            "travel": self._travel,
            "rest": self._rest,
            "challenge_boss": self._challenge_boss,
            "equip": self._equip,
            "unequip": self._unequip,
            "sell": self._sell,
            "use_item": self._use_item,
            "buy": self._buy,
            "allocate": self._allocate,
        }.get(action)
        if not handler:
            raise GameError(f"未知操作: {action}")
        result = handler(payload)
        self.autosave()
        result["state"] = self.state()
        return result

    def _explore(self, payload: dict) -> dict:
        area_id = self.world["area"]
        event = map_mod.roll_explore(area_id, self.char)
        out = {"event": event, "events": []}
        if event["kind"] == "battle":
            self.battle = Battle(self.char, event["enemy_ids"], area_id)
            out["battle"] = self.battle.view()
            self.last_message = "遭遇战！"
        elif event["kind"] == "gold":
            self.char.gold += event["amount"]
            out["events"].append({"type": "loot", "text": f"你在废墟中翻出 {event['amount']} 金币。"})
        elif event["kind"] == "item":
            if equip_mod.add_consumable(self.char, event["item_id"], 1):
                out["events"].append({"type": "loot", "text": f"你拾获【{event['name']}】。"})
            else:
                self.char.gold += 30
                out["events"].append({"type": "loot", "text": "背包已满，物品折算为 30 金币。"})
        else:
            out["events"].append({"type": "system", "text": "四下无人，只有风声。"})
        self.world["steps"] += 1
        return out

    def _travel(self, payload: dict) -> dict:
        area_id = payload.get("area_id", "")
        info = map_mod.travel(self.world, area_id)
        self.last_message = f"抵达 {info['name']}"
        return {"events": [{"type": "system", "text": f"你来到了【{info['name']}】。"}]}

    def _rest(self, payload: dict) -> dict:
        area = area_def(self.world["area"])
        if not area["safe"]:
            raise GameError("只能在安全区域休整")
        healed = self.char.heal(self.char.max_hp)
        restored = self.char.restore_mp(self.char.max_mp)
        self.last_message = "在晨曦村休整完毕。"
        return {"events": [{"type": "system", "text": f"你美美睡了一觉，恢复 {healed} 生命、{restored} 法力。"}]}

    def _challenge_boss(self, payload: dict) -> dict:
        area_id = self.world["area"]
        area = area_def(area_id)
        if not area["boss"]:
            raise GameError("这里没有 Boss")
        if area_id in self.world["bosses"]:
            raise GameError("该区域的 Boss 已被击败")
        self.battle = Battle(self.char, [area["boss"]], area_id, is_boss=True, boss_id=area["boss"])
        self.last_message = "Boss 战开始！"
        return {"battle": self.battle.view(), "events": []}

    # ---------- 角色操作 ----------
    def _equip(self, payload: dict) -> dict:
        info = equip_mod.equip_item(self.char, payload.get("uid", ""))
        self.last_message = f"装备了【{info['equipped']['name']}】"
        return {"events": [{"type": "system", "text": self.last_message}]}

    def _unequip(self, payload: dict) -> dict:
        info = equip_mod.unequip(self.char, payload.get("slot", ""))
        return {"events": [{"type": "system", "text": f"卸下【{info['item']['name']}】"}]}

    def _sell(self, payload: dict) -> dict:
        info = equip_mod.sell_item(self.char, payload.get("uid", ""))
        return {"events": [{"type": "loot", "text": f"出售【{info['name']}】，获得 {info['gold']} 金币。"}]}

    def _use_item(self, payload: dict) -> dict:
        info = equip_mod.use_consumable(self.char, payload.get("item_id", ""))
        parts = []
        if info["hp"]:
            parts.append(f"生命 +{info['hp']}")
        if info["mp"]:
            parts.append(f"法力 +{info['mp']}")
        if info["cleansed"]:
            parts.append("解除异常")
        return {"events": [{"type": "system", "text": f"使用【{info['name']}】：" + ("、".join(parts) or "无效果")}]}

    def _buy(self, payload: dict) -> dict:
        info = equip_mod.buy(self.char, payload.get("item_id", ""))
        return {"events": [{"type": "loot", "text": f"购买了【{info['name']}】，花费 {info['gold']} 金币。"}]}

    def _allocate(self, payload: dict) -> dict:
        stat = payload.get("stat", "")
        self.char.allocate(stat)
        label = {"hp": "生命", "mp": "法力", "atk": "攻击", "def": "防御", "agi": "敏捷"}.get(stat, stat)
        return {"events": [{"type": "system", "text": f"{label} +1"}]}

    # ---------- 战斗 ----------
    def battle_action(self, payload: dict) -> dict:
        self._require()
        if not self.battle or self.battle.status != "active":
            raise GameError("当前没有进行中的战斗")
        result = self.battle.player_action(payload)
        view = result["battle"]
        status = view["status"]

        if status == "won":
            if self.battle.is_boss and self.battle.boss_id:
                unlocked = map_mod.unlock_next(self.world, self.world["area"])
                if unlocked:
                    result["unlocked_areas"] = unlocked
                    result["events"].append({
                        "type": "system",
                        "text": "🗺️ 新区域解锁：" + "、".join(a["name"] for a in unlocked),
                    })
            self.last_message = "战斗胜利！"
            self.battle = None
        elif status == "lost":
            lost_gold = int(self.char.gold * 0.1)
            self.char.gold -= lost_gold
            self.char.hp = max(1, self.char.max_hp // 2)
            self.char.mp = self.char.max_mp // 2
            self.world["area"] = "village"
            result["events"].append({
                "type": "system",
                "text": f"你在晨曦村的床上醒来，损失了 {lost_gold} 金币。",
            })
            self.last_message = "你被击败了……"
            self.battle = None
        elif status == "fled":
            self.last_message = "你逃离了战斗。"
            self.battle = None

        self.autosave()
        result["state"] = self.state()
        return result
