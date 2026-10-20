"""叙事模块：章节目标、进区旁白、Boss 对话与结局。

剧情数据全部放在 backend/data/story.json，本模块只负责「按进度挑出该说的话」，
不持有任何状态——进度从 world 里的 bosses / finished 推导，因此读档、存档、
重开都不需要额外字段，也不会出现剧情与进度对不上的情况。
"""
from __future__ import annotations

from ..data_loader import area_def, story_data


def chapters() -> list[dict]:
    return story_data()["chapters"]


def chapter_for(area_id: str) -> dict | None:
    for chapter in chapters():
        if chapter["area"] == area_id:
            return chapter
    return None


def progress(world: dict) -> int:
    """已击败的守关者数量，等价于已通关的章节数。"""
    return len(world.get("bosses", []))


def objective(world: dict) -> dict:
    """当前目标：永远指向「下一个没打过的守关者」。

    晨曦村没有守关者，所以开局单独指向第一章；之后按「第一个未击败的 Boss」
    推导，避免章节序号与已通关数量之间的偏移。
    """
    all_chapters = chapters()
    total = len(all_chapters)
    finished = bool(world.get("finished"))
    cleared = set(world.get("bosses", []))

    if finished:
        index = total - 1
    elif not cleared:
        index = 0
    else:
        index = total - 1
        for i, chapter in enumerate(all_chapters):
            area = area_def(chapter["area"])
            if area.get("boss") and chapter["area"] not in cleared:
                index = i
                break

    chapter = all_chapters[index]
    area = area_def(chapter["area"])
    return {
        "index": index + 1,
        "total": total,
        "kicker": chapter["kicker"],
        "title": chapter["title"],
        "goal": "十域已无守关者。第十把椅子在虚空里等你。" if finished else chapter["goal"],
        "area": area["id"],
        "area_name": area["name"],
        "boss_id": area.get("boss"),
        "cleared": len(cleared),
        "finished": finished,
    }


def entry(area_id: str) -> dict | None:
    """首次踏入某区域时播放的旁白。"""
    chapter = chapter_for(area_id)
    if not chapter or not chapter.get("enter"):
        return None
    return {
        "kind": "enter",
        "kicker": chapter["kicker"],
        "title": chapter["title"],
        "lines": chapter["enter"],
    }


def boss_lines(area_id: str, phase: str) -> list[dict]:
    chapter = chapter_for(area_id)
    if not chapter:
        return []
    return chapter.get(phase) or []


def prologue() -> dict:
    data = story_data()["prologue"]
    return {
        "kind": "prologue",
        "kicker": data["kicker"],
        "title": data["title"],
        "lines": data["lines"],
    }


def ending() -> dict:
    data = story_data()["ending"]
    return {
        "kind": "ending",
        "kicker": data["kicker"],
        "title": data["title"],
        "lines": data["lines"],
        "epilogue": data.get("epilogue", ""),
    }


def summary(world: dict, char, playtime: int) -> dict:
    """结局页上的统计。"""
    return {
        "level": char.level,
        "kills": getattr(char, "kills", 0),
        "gold": char.gold,
        "playtime": playtime,
        "bosses": progress(world),
        "steps": int(world.get("steps", 0)),
    }
