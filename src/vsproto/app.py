"""窗口、输入、主循环。逻辑全在 World 里，这里只做搬运。"""

from __future__ import annotations

import pygame

from . import render
from .config import Config
from .world import World


def read_move() -> tuple[float, float]:
    keys = pygame.key.get_pressed()
    right = keys[pygame.K_RIGHT] or keys[pygame.K_d]
    left = keys[pygame.K_LEFT] or keys[pygame.K_a]
    down = keys[pygame.K_DOWN] or keys[pygame.K_s]
    up = keys[pygame.K_UP] or keys[pygame.K_w]
    return float(right) - float(left), float(down) - float(up)


def run(max_frames: int | None = None) -> int:
    cfg = Config()
    pygame.init()
    screen = pygame.display.set_mode((cfg.view_w, cfg.view_h))
    pygame.display.set_caption("Vampire Survivors · 超小原型")
    clock = pygame.time.Clock()
    fonts = render.load_fonts()
    world = World(cfg)

    running = True
    frames = 0
    while running:
        dt = min(clock.tick(60) / 1000.0, 0.05)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_r and world.state != "running":
                    world = World(cfg)

        if world.state == "running":
            world.step(dt, read_move())

        render.draw(screen, world, cfg, fonts)
        pygame.display.flip()

        frames += 1
        if max_frames is not None and frames >= max_frames:
            running = False

    pygame.quit()
    return 0


def main() -> int:
    return run()
