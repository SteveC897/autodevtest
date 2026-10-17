"""校验 .dsh/skills 下的 SKILL.md 是否会被 dsh 正确加载。

dsh 的规则很硬：frontmatter 错一个字段，整个 skill 会**静默消失**。
所以这里做确定性检查，而不是靠"应该没问题"。

用法：uv run python scripts/check_skills.py
退出码：0 全部合法；1 有非法或缺失。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / ".dsh" / "skills"
REQUIRED = ("name", "description", "whenToUse")
KEBAB = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    data: dict[str, str] = {}
    for line in text[3:end].splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        data[key.strip()] = value.strip().strip("\"'")
    return data


def main() -> int:
    if not SKILLS.is_dir():
        print(f"FAIL  {SKILLS} 不存在")
        return 1

    problems: list[str] = []
    found: list[str] = []

    for skill_md in sorted(SKILLS.glob("*/SKILL.md")):
        folder = skill_md.parent.name
        found.append(folder)
        meta = parse_frontmatter(skill_md.read_text(encoding="utf-8"))

        if not meta:
            problems.append(f"{folder}: 缺少 --- frontmatter ---")
            continue

        for key in REQUIRED:
            if not meta.get(key):
                problems.append(f"{folder}: 缺少字段 {key}")

        name = meta.get("name", "")
        if name and name != folder:
            problems.append(f"{folder}: name={name!r} 必须与目录名一致")
        if name and not KEBAB.match(name):
            problems.append(f"{folder}: name 必须是 kebab-case")

        if len(meta.get("description", "")) < 10:
            problems.append(f"{folder}: description 太短（模型靠它决定要不要用）")

    if not found:
        problems.append("没有找到任何 skill")

    for name in found:
        print(f"  found  {name}")

    if problems:
        print()
        for p in problems:
            print(f"FAIL  {p}")
        return 1

    print(f"\nOK  {len(found)} 个 skill 全部合法")
    return 0


if __name__ == "__main__":
    sys.exit(main())
