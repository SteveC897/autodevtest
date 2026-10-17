"""只负责画。所有状态来自 World，这里不修改任何游戏逻辑。"""

from __future__ import annotations

import math

import pygame

from .config import Config
from .world import World

# 颜色：验证脚本会直接比对这些常量
FLOOR = (20, 22, 26)
GRID = (28, 32, 38)
BORDER = (64, 70, 84)
PLAYER_FILL = (255, 107, 107)
PLAYER_EDGE = (255, 176, 176)
ENEMY_FILL = (245, 246, 250)
ENEMY_EDGE = (200, 204, 214)
BULLET = (77, 155, 255)
TEXT = (232, 236, 244)
TEXT_DIM = (150, 156, 170)
HP_BACK = (54, 24, 28)
HP_FILL = (232, 76, 76)
HP_EDGE = (90, 96, 110)
OVERLAY = (8, 9, 12)

CJK_FONT_CANDIDATES = (
    "microsoftyahei",
    "msyh",
    "simhei",
    "simsun",
    "notosanscjksc",
    "notosanssc",
    "arialunicode",
)


def label(cjk: bool, zh: str, en: str) -> str:
    return zh if cjk else en


def load_fonts() -> tuple[pygame.font.Font, pygame.font.Font, bool]:
    """返回 (小号, 大号, 是否支持中文)。找不到中文字体就退回英文文案。"""
    pygame.font.init()
    path = None
    for name in CJK_FONT_CANDIDATES:
        found = pygame.font.match_font(name)
        if found:
            path = found
            break
    if path:
        return pygame.font.Font(path, 20), pygame.font.Font(path, 54), True
    return pygame.font.Font(None, 22), pygame.font.Font(None, 56), False


def camera(world: World, cfg: Config) -> tuple[float, float]:
    cx = min(max(world.player.x - cfg.view_w / 2, 0.0), cfg.arena_w - cfg.view_w)
    cy = min(max(world.player.y - cfg.view_h / 2, 0.0), cfg.arena_h - cfg.view_h)
    return cx, cy


def draw(surface: pygame.Surface, world: World, cfg: Config, fonts) -> None:
    small, big, cjk = fonts
    cx, cy = camera(world, cfg)

    surface.fill(FLOOR)
    _grid(surface, cfg, cx, cy)

    border = (
        int(-cx),
        int(-cy),
        int(cfg.arena_w),
        int(cfg.arena_h),
    )
    pygame.draw.rect(surface, BORDER, border, 3)

    for b in world.bullets:
        pygame.draw.circle(surface, BULLET, (int(b.x - cx), int(b.y - cy)), int(b.r))

    for e in world.enemies:
        pos = (int(e.x - cx), int(e.y - cy))
        pygame.draw.circle(surface, ENEMY_FILL, pos, int(e.r))
        pygame.draw.circle(surface, ENEMY_EDGE, pos, int(e.r), 2)

    px, py = world.player.x - cx, world.player.y - cy
    r = cfg.player_radius
    diamond = [(px, py - r), (px + r, py), (px, py + r), (px - r, py)]
    pygame.draw.polygon(surface, PLAYER_FILL, diamond)
    pygame.draw.polygon(surface, PLAYER_EDGE, diamond, 2)

    _hud(surface, world, cfg, small, cjk)

    if world.state != "running":
        _overlay(surface, world, cfg, small, big, cjk)


def _grid(surface: pygame.Surface, cfg: Config, cx: float, cy: float) -> None:
    step = 80
    x = math.floor(cx / step) * step
    while x <= cx + cfg.view_w:
        sx = int(x - cx)
        pygame.draw.line(surface, GRID, (sx, 0), (sx, cfg.view_h - 1))
        x += step
    y = math.floor(cy / step) * step
    while y <= cy + cfg.view_h:
        sy = int(y - cy)
        pygame.draw.line(surface, GRID, (0, sy), (cfg.view_w - 1, sy))
        y += step


def _hud(
    surface: pygame.Surface,
    world: World,
    cfg: Config,
    small: pygame.font.Font,
    cjk: bool,
) -> None:
    pygame.draw.rect(surface, HP_BACK, (20, 20, 220, 16), border_radius=3)
    ratio = 0.0 if cfg.player_hp <= 0 else world.player.hp / cfg.player_hp
    width = int(220 * max(0.0, min(1.0, ratio)))
    if width > 0:
        pygame.draw.rect(surface, HP_FILL, (20, 20, width, 16), border_radius=3)
    pygame.draw.rect(surface, HP_EDGE, (20, 20, 220, 16), 1, border_radius=3)

    hp_text = small.render(f"HP {int(world.player.hp)}/{int(cfg.player_hp)}", True, TEXT)
    surface.blit(hp_text, (20, 42))

    minutes, seconds = divmod(int(math.ceil(world.remaining)), 60)
    timer = small.render(f"{minutes}:{seconds:02d}", True, TEXT)
    surface.blit(timer, (cfg.view_w // 2 - timer.get_width() // 2, 18))

    kills = small.render(label(cjk, f"击杀 {world.kills}", f"Kills {world.kills}"), True, TEXT)
    surface.blit(kills, (cfg.view_w - kills.get_width() - 20, 20))

    hint = small.render(
        label(cjk, "WASD/方向键移动 · 自动攻击 · ESC 退出", "WASD/Arrows move - auto attack - ESC quit"),
        True,
        TEXT_DIM,
    )
    surface.blit(hint, (cfg.view_w // 2 - hint.get_width() // 2, cfg.view_h - 28))


def _overlay(
    surface: pygame.Surface,
    world: World,
    cfg: Config,
    small: pygame.font.Font,
    big: pygame.font.Font,
    cjk: bool,
) -> None:
    veil = pygame.Surface((cfg.view_w, cfg.view_h), pygame.SRCALPHA)
    veil.fill((*OVERLAY, 200))
    surface.blit(veil, (0, 0))

    if world.state == "won":
        title = label(cjk, "胜  利", "VICTORY")
        color = (140, 230, 180)
    else:
        title = label(cjk, "你 死 了", "YOU DIED")
        color = (240, 110, 110)

    big_text = big.render(title, True, color)
    surface.blit(big_text, (cfg.view_w // 2 - big_text.get_width() // 2, cfg.view_h // 2 - 70))

    sub = small.render(
        label(cjk, f"击杀 {world.kills} · 用时 {world.time:.1f}s", f"Kills {world.kills} - {world.time:.1f}s"),
        True,
        TEXT,
    )
    surface.blit(sub, (cfg.view_w // 2 - sub.get_width() // 2, cfg.view_h // 2 + 4))

    hint = small.render(label(cjk, "R 重开 · ESC 退出", "R restart - ESC quit"), True, TEXT_DIM)
    surface.blit(hint, (cfg.view_w // 2 - hint.get_width() // 2, cfg.view_h // 2 + 44))
