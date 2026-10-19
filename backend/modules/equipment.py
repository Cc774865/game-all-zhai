"""装备与道具模块：随机掉落、稀有度、穿戴、背包、买卖。"""
from __future__ import annotations

import random
import uuid

from ..data_loader import consumables, equipment_templates, rarities, template_map

INVENTORY_CAP = 40
SLOT_LABEL = {"weapon": "武器", "armor": "护甲", "accessory": "饰品"}
SLOT_WEIGHTS = [("weapon", 0.38), ("armor", 0.34), ("accessory", 0.28)]
STAT_LABEL = {"atk": "攻击", "def": "防御", "hp": "生命", "mp": "法力", "agi": "敏捷", "crit": "暴击", "dodge": "闪避"}


def _uid() -> str:
    return uuid.uuid4().hex[:10]


def _scale_stats(template: dict, rarity_mult: float, level: int) -> dict:
    scale = rarity_mult * (1 + 0.055 * (level - 1))
    stats = {}
    for key, value in template["stats"].items():
        stats[key] = max(1, int(round(value * scale)))
    return stats


def make_item(template_id: str, rarity: str, level: int) -> dict:
    template = template_map()[template_id]
    rarity_def = rarities()[rarity]
    stats = _scale_stats(template, rarity_def["mult"], level)
    name = template["name"] if rarity == "common" else f"{rarity_def['name']}·{template['name']}"
    price = int(template["price"] * rarity_def["mult"] * (1 + 0.06 * (level - 1)))
    return {
        "uid": _uid(),
        "type": "equipment",
        "template_id": template_id,
        "name": name,
        "base_name": template["name"],
        "emoji": template["emoji"],
        "slot": template["slot"],
        "rarity": rarity,
        "rarity_name": rarity_def["name"],
        "color": rarity_def["color"],
        "level": level,
        "req_level": max(1, level - 2),
        "stats": stats,
        "price": price,
    }


def roll_rarity(min_rarity: str | None = None, luck: float = 0.0) -> str:
    table = rarities()
    order = ["common", "uncommon", "rare", "epic", "legendary"]
    weights = []
    for key in order:
        weight = table[key]["weight"]
        if key in ("rare", "epic", "legendary"):
            weight *= (1 + luck)
        weights.append(weight)
    rarity = random.choices(order, weights=weights, k=1)[0]
    if min_rarity:
        floor = order.index(min_rarity)
        if order.index(rarity) < floor:
            rarity = min_rarity
    return rarity


def roll_equipment(area_tier: int, level: int, class_id: str,
                   min_rarity: str | None = None, luck: float = 0.0) -> dict:
    """按地图层级与职业随机生成一件装备。"""
    slot = random.choices([s for s, _ in SLOT_WEIGHTS], weights=[w for _, w in SLOT_WEIGHTS], k=1)[0]
    pool = []
    for template in equipment_templates():
        if template["slot"] != slot:
            continue
        if template["tier"] > area_tier:
            continue
        allowed = template.get("classes")
        if allowed and class_id not in allowed:
            continue
        pool.append(template)
    if not pool:
        pool = [t for t in equipment_templates() if t["slot"] == slot]
    template = random.choice(pool)
    rarity = roll_rarity(min_rarity, luck)
    return make_item(template["id"], rarity, level)


# ---------- 消耗品 ----------
def make_consumable(item_id: str, qty: int = 1) -> dict:
    base = consumables()[item_id]
    return {
        "uid": _uid(),
        "type": "consumable",
        "item_id": item_id,
        "name": base["name"],
        "emoji": base["emoji"],
        "desc": base["desc"],
        "price": base["price"],
        "qty": qty,
        "rarity": "common",
        "rarity_name": "消耗品",
        "color": "#9aa4b2",
    }


def add_consumable(char, item_id: str, qty: int = 1) -> bool:
    for item in char.inventory:
        if item["type"] == "consumable" and item["item_id"] == item_id:
            item["qty"] += qty
            return True
    if len(char.inventory) >= INVENTORY_CAP:
        return False
    char.inventory.append(make_consumable(item_id, qty))
    return True


def add_item(char, item: dict) -> bool:
    if item["type"] == "consumable":
        return add_consumable(char, item["item_id"], item.get("qty", 1))
    if len(char.inventory) >= INVENTORY_CAP:
        return False
    char.inventory.append(item)
    return True


def find_item(char, uid: str) -> dict | None:
    for item in char.inventory:
        if item["uid"] == uid:
            return item
    return None


def equip_item(char, uid: str) -> dict:
    item = find_item(char, uid)
    if not item or item["type"] != "equipment":
        raise ValueError("背包里没有这件装备")
    if item["req_level"] > char.level:
        raise ValueError(f"需要等级 {item['req_level']} 才能装备")
    slot = item["slot"]
    old = char.equipment.get(slot)
    char.inventory.remove(item)
    char.equipment[slot] = item
    if old:
        char.inventory.append(old)
    char.hp = min(char.hp, char.max_hp)
    char.mp = min(char.mp, char.max_mp)
    return {"equipped": item, "replaced": old}


def unequip(char, slot: str) -> dict:
    item = char.equipment.get(slot)
    if not item:
        raise ValueError("该部位没有装备")
    if len(char.inventory) >= INVENTORY_CAP:
        raise ValueError("背包已满")
    char.equipment[slot] = None
    char.inventory.append(item)
    char.hp = min(char.hp, char.max_hp)
    char.mp = min(char.mp, char.max_mp)
    return {"item": item}


def sell_item(char, uid: str) -> dict:
    item = find_item(char, uid)
    if not item:
        raise ValueError("背包里没有这件物品")
    price = max(1, int(item.get("price", 10) * 0.45)) * (item.get("qty", 1) if item["type"] == "consumable" else 1)
    char.inventory.remove(item)
    char.gold += price
    return {"gold": price, "name": item["name"]}


def use_consumable(char, item_id: str) -> dict:
    """战斗外使用消耗品。"""
    entry = None
    for item in char.inventory:
        if item["type"] == "consumable" and item["item_id"] == item_id:
            entry = item
            break
    if not entry:
        raise ValueError("没有这件道具")
    base = consumables()[item_id]
    result = {"name": base["name"], "hp": 0, "mp": 0, "cleansed": False}
    if base.get("full"):
        result["hp"] = char.heal(char.max_hp)
        result["mp"] = char.restore_mp(char.max_mp)
    if base.get("heal_hp"):
        result["hp"] = char.heal(base["heal_hp"])
    if base.get("heal_mp"):
        result["mp"] = char.restore_mp(base["heal_mp"])
    if base.get("cleanse"):
        result["cleansed"] = True
    entry["qty"] -= 1
    if entry["qty"] <= 0:
        char.inventory.remove(entry)
    return result


def shop_stock() -> list[dict]:
    """晨曦村商店：消耗品 + 一阶装备。"""
    stock = []
    for item_id, base in consumables().items():
        stock.append({
            "item_id": item_id, "name": base["name"], "emoji": base["emoji"],
            "desc": base["desc"], "price": base["price"], "type": "consumable",
        })
    for template in equipment_templates():
        if template["tier"] != 1:
            continue
        stock.append({
            "item_id": template["id"], "name": template["name"], "emoji": template["emoji"],
            "desc": " / ".join(f"{STAT_LABEL.get(k, k)}+{v}" for k, v in template["stats"].items()),
            "price": template["price"], "type": "equipment", "slot": template["slot"],
            "classes": template.get("classes"),
        })
    return stock


def buy(char, item_id: str) -> dict:
    stock = {s["item_id"]: s for s in shop_stock()}
    if item_id not in stock:
        raise ValueError("商店没有这件商品")
    entry = stock[item_id]
    if char.gold < entry["price"]:
        raise ValueError("金币不足")
    if entry["type"] == "equipment":
        allowed = entry.get("classes")
        if allowed and char.class_id not in allowed:
            raise ValueError("该装备不适合你的职业")
    if entry["type"] == "consumable":
        if not add_consumable(char, item_id, 1):
            raise ValueError("背包已满")
        char.gold -= entry["price"]
        return {"name": entry["name"], "gold": entry["price"]}
    if len(char.inventory) >= INVENTORY_CAP:
        raise ValueError("背包已满")
    item = make_item(item_id, "common", max(1, char.level))
    char.gold -= entry["price"]
    char.inventory.append(item)
    return {"name": item["name"], "gold": entry["price"], "item": item}
