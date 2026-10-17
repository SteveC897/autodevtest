"""spec 结构检查（G1 的一部分）。

只做确定性检查：字段齐不齐、范围有没有过宽、验收标准数量够不够。
"验收标准能不能执行"这类判断交给独立评审 agent，不用正则硬猜。

用法：
  uv run python scripts/spec_lint.py                     # 检查所有 spec
  uv run python scripts/spec_lint.py docs/agents/specs/sp-xxx.md
退出码：0 通过；1 有硬错误。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPECS = ROOT / "docs" / "agents" / "specs"

REQUIRED = ("id", "title", "risk_tier", "touches", "non_goals", "rollback")
RISK = {"T0", "T1", "T2", "T3"}
TOO_BROAD = {"src/**", "**", "*", "src/*"}
AC_BULLET = re.compile(r"^\s*-\s*\[[ xX]\]\s+(.+)$")
AC_TABLE = re.compile(r"^\|\s*(ac\d+)\s*\|", re.IGNORECASE)
EXECUTABLE_HINTS = ("`", "manual", "单测", "像素", "退出码", "截图", "命令")


def parse(path: Path) -> tuple[dict, list[str], str]:
    text = path.read_text(encoding="utf-8")
    body = text
    front: dict = {}
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            raw = text[3:end]
            body = text[end + 4 :]
            current: str | None = None
            for line in raw.splitlines():
                if not line.strip():
                    continue
                if line.startswith(("  - ", "- ")) and current:
                    front.setdefault(current, [])
                    if isinstance(front[current], list):
                        front[current].append(line.split("- ", 1)[1].strip())
                    continue
                if ":" in line:
                    key, _, value = line.partition(":")
                    key, value = key.strip(), value.strip()
                    current = key
                    if value:
                        front[key] = value
                    else:
                        front[key] = []
    return front, [], body


def lint(path: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    front, _, body = parse(path)

    for key in REQUIRED:
        if not front.get(key):
            errors.append(f"缺少字段 {key}")

    risk = str(front.get("risk_tier", ""))
    if risk and risk not in RISK:
        errors.append(f"risk_tier={risk!r} 不在 T0-T3")

    touches = front.get("touches") or []
    if not isinstance(touches, list) or not touches:
        errors.append("touches 必须是非空列表")
    else:
        for t in touches:
            if t in TOO_BROAD:
                errors.append(f"touches 过宽：{t}（应写到模块级，如 src/vsproto/render.py）")

    non_goals = front.get("non_goals") or []
    if not isinstance(non_goals, list) or len(non_goals) < 2:
        errors.append(f"non_goals 至少 2 条，当前 {len(non_goals) if isinstance(non_goals, list) else 0}")

    rollback = str(front.get("rollback", ""))
    if len(rollback) < 4:
        errors.append("rollback 太短或缺失")

    criteria = [m.group(1) for line in body.splitlines() if (m := AC_BULLET.match(line))]
    table_rows = [line for line in body.splitlines() if AC_TABLE.match(line)]
    total = len(criteria) + len(table_rows)
    if total < 3:
        errors.append(f"验收标准至少 3 条，当前 {total}")

    vague = [c for c in criteria if not any(h in c.lower() for h in EXECUTABLE_HINTS)]
    if vague:
        warnings.append(f"{len(vague)} 条验收标准看不出可执行依据（评审时重点看）")

    return errors, warnings


def main() -> int:
    args = [Path(a) for a in sys.argv[1:]]
    if args:
        targets = args
    else:
        targets = [p for p in sorted(SPECS.glob("*.md")) if not p.name.startswith("_")]

    if not targets:
        print("没有找到 spec（docs/agents/specs/*.md）")
        return 1

    failed = 0
    for path in targets:
        errors, warnings = lint(path)
        status = "FAIL" if errors else "PASS"
        print(f"{status}  {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
        for e in errors:
            print(f"        ✗ {e}")
        for w in warnings:
            print(f"        ! {w}")
        if errors:
            failed += 1

    print(f"\n{len(targets) - failed}/{len(targets)} 通过")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
