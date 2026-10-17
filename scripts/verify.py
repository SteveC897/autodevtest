"""无头验证：真的把游戏跑起来、渲染、截图、检查像素。

这不是单元测试。它回答的是"这个程序作为一个产品，看起来/跑起来对不对"：
  - 窗口尺寸对不对
  - 地板是不是暗色
  - 主角是不是浅红菱形（中心像素）
  - 敌人是不是白色圆形
  - 子弹是不是蓝色
  - 血条画出来没有
  - 180 秒到点会不会赢、会不会清场
  - 站着不动会不会死
  - 同 seed 是否可重放

用法：uv run python scripts/verify.py
退出码：0 全过；1 有失败。截图与 summary.json 在 artifacts/verify/<时间戳>/
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import replace
from datetime import datetime
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pygame  # noqa: E402

from vsproto import render  # noqa: E402
from vsproto.config import Config  # noqa: E402
from vsproto.world import World  # noqa: E402

OUT = ROOT / "artifacts" / "verify" / datetime.now().strftime("%Y%m%d-%H%M%S")
CHECKS: list[dict] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append({"name": name, "ok": bool(ok), "detail": detail})
    print(("PASS  " if ok else "FAIL  ") + name + (f"   [{detail}]" if detail else ""))


def sim(world: World, seconds: float, move: tuple[float, float] = (0.0, 0.0), fps: int = 60) -> None:
    dt = 1.0 / fps
    for _ in range(round(seconds * fps)):
        world.step(dt, move)
        if world.state != "running":
            break


def snap(world: World, cfg: Config, fonts, name: str) -> pygame.Surface:
    surface = pygame.Surface((cfg.view_w, cfg.view_h))
    render.draw(surface, world, cfg, fonts)
    pygame.image.save(surface, str(OUT / name))
    return surface


def screen_pos(world: World, cfg: Config, x: float, y: float) -> tuple[int, int]:
    cx, cy = render.camera(world, cfg)
    return int(x - cx), int(y - cy)


def rgb(surface: pygame.Surface, pos: tuple[int, int]) -> tuple[int, int, int]:
    return tuple(surface.get_at(pos)[:3])


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    pygame.init()
    fonts = render.load_fonts()
    started = time.perf_counter()

    # ---------- 1. 运行中画面 ----------
    cfg = Config()
    world = World(cfg)
    sim(world, 3.0)  # 站着不动，让敌人进入射程
    surface = snap(world, cfg, fonts, "01-running-3s.png")

    check("窗口尺寸 960x600", surface.get_size() == (cfg.view_w, cfg.view_h), str(surface.get_size()))
    check("开局 3 秒仍在运行", world.state == "running", world.state)
    check("敌人已生成", len(world.enemies) > 0, f"{len(world.enemies)} 个")
    check("已自动开火", world.shots > 0, f"{world.shots} 发")

    floor = rgb(surface, (8, 120))
    check("地板是暗色", sum(floor) < 130, str(floor))

    hp_px = rgb(surface, (30, 28))
    check("血条已绘制", hp_px == render.HP_FILL, str(hp_px))

    player_px = rgb(surface, (cfg.view_w // 2, cfg.view_h // 2))
    check("主角是浅红菱形", player_px == render.PLAYER_FILL, str(player_px))

    enemy_px = None
    for e in world.enemies:
        sx, sy = screen_pos(world, cfg, e.x, e.y)
        if 20 < sx < cfg.view_w - 20 and 60 < sy < cfg.view_h - 40:
            enemy_px = rgb(surface, (sx, sy))
            if enemy_px == render.ENEMY_FILL:
                break
    check("敌人是白色圆形", enemy_px == render.ENEMY_FILL, str(enemy_px))

    bullet_px = None
    px, py = screen_pos(world, cfg, world.player.x, world.player.y)
    for b in world.bullets:
        sx, sy = screen_pos(world, cfg, b.x, b.y)
        if 10 < sx < cfg.view_w - 10 and 10 < sy < cfg.view_h - 10:
            if abs(sx - px) + abs(sy - py) < 30:
                continue
            bullet_px = rgb(surface, (sx, sy))
            if bullet_px == render.BULLET:
                break
    check("子弹是蓝色", bullet_px == render.BULLET, str(bullet_px))

    # ---------- 2. 胜利 ----------
    cfg_win = replace(Config(), duration=6.0, contact_damage=0.0)
    world_win = World(cfg_win)
    sim(world_win, 6.5)
    snap(world_win, cfg_win, fonts, "02-victory.png")
    check("到点判胜", world_win.state == "won", world_win.state)
    check("胜利清空敌人", len(world_win.enemies) == 0, f"{len(world_win.enemies)}")
    check("计时停在 6.0", abs(world_win.time - cfg_win.duration) < 1e-9, f"{world_win.time}")
    check("胜利时血量未变", world_win.player.hp == cfg_win.player_hp, f"{world_win.player.hp}")

    # ---------- 3. 失败 ----------
    cfg_lose = Config()
    world_lose = World(cfg_lose)
    sim(world_lose, 60.0)
    snap(world_lose, cfg_lose, fonts, "03-defeat.png")
    check("站着不动会死", world_lose.state == "lost", f"hp={world_lose.player.hp} t={world_lose.time:.1f}")
    check("血量封底为 0", world_lose.player.hp == 0.0, str(world_lose.player.hp))

    # ---------- 4. 完整 180 秒 ----------
    cfg_full = replace(Config(), contact_damage=0.0)
    world_full = World(cfg_full)
    sim(world_full, 181.0)
    check(
        "完整 3 分钟能跑完并判胜",
        world_full.state == "won" and world_full.time == 180.0,
        f"t={world_full.time} kills={world_full.kills} state={world_full.state}",
    )
    check("满时长后仍有击杀记录", world_full.kills > 0, f"{world_full.kills}")

    # ---------- 5. 确定性 ----------
    a = World(Config(seed=11))
    b = World(Config(seed=11))
    for _ in range(900):
        a.step(1 / 60, (0.4, 0.6))
        b.step(1 / 60, (0.4, 0.6))
    check("同 seed 同输入可重放", a.snapshot() == b.snapshot(), str(a.snapshot()))

    # ---------- 6. 真实入口冒烟（跑 app.py 的主循环，而不是绕过它） ----------
    from vsproto.app import run as run_app

    code = run_app(max_frames=60)
    check("真实入口能跑 60 帧并正常退出", code == 0, f"exit={code}")

    elapsed = time.perf_counter() - started
    failed = [c for c in CHECKS if not c["ok"]]
    summary = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "duration_seconds": round(elapsed, 2),
        "passed": len(CHECKS) - len(failed),
        "failed": len(failed),
        "screenshots": sorted(p.name for p in OUT.glob("*.png")),
        "checks": CHECKS,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    print(f"{summary['passed']}/{len(CHECKS)} 通过，用时 {elapsed:.1f}s")
    print(f"证据目录：{OUT}")
    pygame.quit()
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
