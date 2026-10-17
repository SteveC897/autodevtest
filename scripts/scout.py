"""L0 侦察：扫本仓库，产出带证据的 backlog 条目。只记录，不修。

信号（与 policy.yml 的 scout.signals 对应）：
  todo    源码里的 TODO/FIXME/HACK
  flaky   连跑两次 pytest，结果不一致
  lock    uv 锁文件是否与 pyproject 一致
  layout  分层禁令：world.py 是否 import 了 pygame

用法：uv run python scripts/scout.py [--dry-run]
退出码：0 正常；1 扫描本身失败。
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKLOG = ROOT / "docs" / "agents" / "backlog"
TODAY = date.today().strftime("%Y%m%d")
KEYWORDS = ("TODO", "FIXME", "HACK")
SCAN_DIRS = ("src", "scripts", "tests")
MAX_TODO_ITEMS = 8


@dataclass
class Finding:
    fingerprint: str
    title: str
    source: str
    evidence: str
    impact: int
    effort: int
    confidence: float
    risk_tier: str
    blast: list[str]
    body: str


def run(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def existing_fingerprints() -> set[str]:
    found: set[str] = set()
    for path in BACKLOG.glob("*.md"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("fingerprint:"):
                found.add(line.split(":", 1)[1].strip())
    return found


def next_index() -> int:
    used = [int(m.group(1)) for p in BACKLOG.glob("*.md") for m in re.finditer(r"bl-\d{8}-(\d+)", p.read_text(encoding="utf-8"))]
    return max(used, default=0) + 1


def scan_todo() -> list[Finding]:
    out: list[Finding] = []
    for base in SCAN_DIRS:
        for path in sorted((ROOT / base).rglob("*.py")):
            if path.name == "scout.py":
                continue  # 扫描器自己的关键字表不算待办
            rel = path.relative_to(ROOT).as_posix()
            hits: list[tuple[int, str]] = []
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                for kw in KEYWORDS:
                    if kw in line:
                        hits.append((lineno, f"{kw} @ {rel}:{lineno}"))
                        break
            if not hits:
                continue
            out.append(
                Finding(
                    fingerprint=f"todo-{rel.replace('/', '-')}",
                    title=f"处理 {rel} 里的 {len(hits)} 处待办标记",
                    source="todo",
                    evidence="; ".join(h[1] for h in hits[:5]),
                    impact=2,
                    effort=1,
                    confidence=0.9,
                    risk_tier="T0",
                    blast=[rel],
                    body="\n".join(f"- `{rel}:{n}`" for n, _ in hits[:10]),
                )
            )
            if len(out) >= MAX_TODO_ITEMS:
                return out
    return out


def scan_flaky() -> list[Finding]:
    code1, out1 = run([sys.executable, "-m", "pytest", "-q"])
    code2, out2 = run([sys.executable, "-m", "pytest", "-q"])
    if (code1, out1.strip().splitlines()[-1:]) == (code2, out2.strip().splitlines()[-1:]):
        return []
    return [
        Finding(
            fingerprint="flaky-test-suite",
            title="测试套件结果不稳定：两次运行不一致",
            source="flaky",
            evidence=f"第一次 exit={code1}；第二次 exit={code2}",
            impact=4,
            effort=3,
            confidence=0.8,
            risk_tier="T1",
            blast=["tests/"],
            body=f"```\n{out1.strip()[-400:]}\n```\n\n```\n{out2.strip()[-400:]}\n```",
        )
    ]


def scan_lock() -> list[Finding]:
    code, out = run(["uv", "lock", "--check"])
    if code == 0:
        return []
    return [
        Finding(
            fingerprint="lock-out-of-sync",
            title="uv.lock 与 pyproject.toml 不一致",
            source="lock",
            evidence=f"`uv lock --check` exit={code}",
            impact=3,
            effort=1,
            confidence=1.0,
            risk_tier="T1",
            blast=["uv.lock"],
            body=f"```\n{out.strip()[-400:]}\n```",
        )
    ]


def scan_layout() -> list[Finding]:
    world = ROOT / "src" / "vsproto" / "world.py"
    if not world.exists():
        return []
    source = world.read_text(encoding="utf-8")
    if not re.search(r"(?m)^\s*(?:import|from)\s+pygame\b", source):
        return []
    return [
        Finding(
            fingerprint="layout-world-imports-pygame",
            title="world.py 依赖了 pygame，破坏纯逻辑分层",
            source="layout",
            evidence="`src/vsproto/world.py` 含 `import pygame`",
            impact=4,
            effort=2,
            confidence=1.0,
            risk_tier="T1",
            blast=["src/vsproto/world.py"],
            body="纯逻辑层必须能在无 pygame 环境里跑；绘制应留在 `render.py`。",
        )
    ]


def render(f: Finding, index: int) -> str:
    item_id = f"bl-{TODAY}-{index:03d}"
    return f"""---
id: {item_id}
title: {f.title}
source: {f.source}
evidence: {f.evidence}
fingerprint: {f.fingerprint}
impact: {f.impact}
effort: {f.effort}
confidence: {f.confidence}
risk_tier: {f.risk_tier}
blast_radius: [{", ".join(f.blast)}]
status: ready
created: {date.today().isoformat()}
---

## 现象

{f.title}

## 复现

{f.evidence}

## 细节

{f.body}
"""


def main() -> int:
    dry = "--dry-run" in sys.argv
    BACKLOG.mkdir(parents=True, exist_ok=True)

    candidates: list[Finding] = []
    for scanner in (scan_todo, scan_flaky, scan_lock, scan_layout):
        try:
            candidates.extend(scanner())
        except Exception as exc:  # 扫描失败不应该拖垮整轮
            print(f"WARN  {scanner.__name__} 失败：{exc}")

    seen = existing_fingerprints()
    index = next_index()
    created = 0

    for f in candidates:
        if f.fingerprint in seen:
            print(f"skip  {f.fingerprint}（已存在）")
            continue
        path = BACKLOG / f"{TODAY}-{index:03d}-{f.source}.md"
        print(f"{'+' if not dry else 'dry'}     {path.name}  <- {f.fingerprint}")
        if not dry:
            path.write_text(render(f, index), encoding="utf-8")
        seen.add(f.fingerprint)
        index += 1
        created += 1

    print(f"\n候选 {len(candidates)} 条，新增 {created} 条，已存在 {len(candidates) - created} 条")
    return 0


if __name__ == "__main__":
    sys.exit(main())
