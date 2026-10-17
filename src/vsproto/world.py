"""纯逻辑模拟。

刻意不 import pygame、不读系统时钟：给定 seed 和输入序列，结果完全可重放。
渲染和输入都在别的层，所以这一层可以在无头环境里跑几千帧。
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from .config import Config


@dataclass
class Player:
    x: float
    y: float
    hp: float


@dataclass
class Enemy:
    x: float
    y: float
    hp: float
    r: float


@dataclass
class Bullet:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    r: float


class World:
    """一局游戏的全部状态。"""

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.rng = random.Random(cfg.seed)
        self.time = 0.0
        self.state = "running"  # running | won | lost
        self.player = Player(cfg.arena_w / 2, cfg.arena_h / 2, cfg.player_hp)
        self.enemies: list[Enemy] = []
        self.bullets: list[Bullet] = []
        self.kills = 0
        self.shots = 0
        self.damage_taken = 0.0
        self._spawn_timer = 0.0
        self._fire_timer = 0.0
        self._contact_cd = 0.0

    # ---------------- 对外 ----------------

    @property
    def remaining(self) -> float:
        return max(0.0, self.cfg.duration - self.time)

    def nearest_enemy(self, max_dist: float | None = None) -> Enemy | None:
        best: Enemy | None = None
        best_d2 = float("inf")
        for e in self.enemies:
            d2 = (e.x - self.player.x) ** 2 + (e.y - self.player.y) ** 2
            if d2 < best_d2:
                best, best_d2 = e, d2
        if best is None:
            return None
        if max_dist is not None and best_d2 > max_dist * max_dist:
            return None
        return best

    def snapshot(self) -> tuple:
        """用于确定性测试：任何状态变化都应该反映在这里。"""
        return (
            round(self.time, 6),
            self.state,
            round(self.player.x, 6),
            round(self.player.y, 6),
            round(self.player.hp, 6),
            len(self.enemies),
            len(self.bullets),
            self.kills,
        )

    def step(self, dt: float, move: tuple[float, float] = (0.0, 0.0)) -> None:
        if self.state != "running" or dt <= 0:
            return
        self.time += dt
        self._move_player(dt, move)
        self._spawn(dt)
        self._move_enemies(dt)
        self._contact(dt)
        self._fire(dt)
        self._move_bullets(dt)
        self._check_end()

    # ---------------- 内部 ----------------

    def _move_player(self, dt: float, move: tuple[float, float]) -> None:
        mx, my = move
        length = math.hypot(mx, my)
        if length > 0:
            mx, my = mx / length, my / length
            self.player.x += mx * self.cfg.player_speed * dt
            self.player.y += my * self.cfg.player_speed * dt
        r = self.cfg.player_radius
        self.player.x = min(max(self.player.x, r), self.cfg.arena_w - r)
        self.player.y = min(max(self.player.y, r), self.cfg.arena_h - r)

    def _spawn(self, dt: float) -> None:
        self._spawn_timer += dt
        while self._spawn_timer >= self.cfg.spawn_interval:
            self._spawn_timer -= self.cfg.spawn_interval
            self._spawn_one()

    def _spawn_one(self) -> None:
        cfg = self.cfg
        x = y = 0.0
        for _ in range(24):
            angle = self.rng.uniform(0.0, math.tau)
            dist = cfg.spawn_min_dist * self.rng.uniform(1.0, 1.15)
            x = self.player.x + math.cos(angle) * dist
            y = self.player.y + math.sin(angle) * dist
            x = min(max(x, cfg.enemy_radius), cfg.arena_w - cfg.enemy_radius)
            y = min(max(y, cfg.enemy_radius), cfg.arena_h - cfg.enemy_radius)
            if math.hypot(x - self.player.x, y - self.player.y) >= cfg.spawn_min_dist * 0.75:
                break
        self.enemies.append(Enemy(x, y, cfg.enemy_hp, cfg.enemy_radius))

    def _move_enemies(self, dt: float) -> None:
        speed = self.cfg.enemy_speed
        for e in self.enemies:
            dx, dy = self.player.x - e.x, self.player.y - e.y
            d = math.hypot(dx, dy)
            if d > 1e-9:
                e.x += dx / d * speed * dt
                e.y += dy / d * speed * dt

    def _contact(self, dt: float) -> None:
        cfg = self.cfg
        if self._contact_cd > 0:
            self._contact_cd = max(0.0, self._contact_cd - dt)
            return
        pr = cfg.player_radius
        for e in self.enemies:
            if math.hypot(e.x - self.player.x, e.y - self.player.y) <= e.r + pr:
                self.player.hp = max(0.0, self.player.hp - cfg.contact_damage)
                self.damage_taken += cfg.contact_damage
                self._contact_cd = cfg.contact_cooldown
                return

    def _fire(self, dt: float) -> None:
        cfg = self.cfg
        self._fire_timer += dt
        while self._fire_timer >= cfg.weapon_interval:
            self._fire_timer -= cfg.weapon_interval
            target = self.nearest_enemy(cfg.weapon_range)
            if target is None:
                continue
            dx, dy = target.x - self.player.x, target.y - self.player.y
            d = math.hypot(dx, dy) or 1.0
            self.bullets.append(
                Bullet(
                    self.player.x,
                    self.player.y,
                    dx / d * cfg.bullet_speed,
                    dy / d * cfg.bullet_speed,
                    cfg.bullet_life,
                    cfg.bullet_radius,
                )
            )
            self.shots += 1

    def _move_bullets(self, dt: float) -> None:
        cfg = self.cfg
        alive: list[Bullet] = []
        for b in self.bullets:
            b.x += b.vx * dt
            b.y += b.vy * dt
            b.life -= dt
            if b.life <= 0:
                continue
            if not (0.0 <= b.x <= cfg.arena_w and 0.0 <= b.y <= cfg.arena_h):
                continue
            hit: Enemy | None = None
            for e in self.enemies:
                if math.hypot(e.x - b.x, e.y - b.y) <= e.r + b.r:
                    hit = e
                    break
            if hit is None:
                alive.append(b)
                continue
            hit.hp -= cfg.bullet_damage

        self.bullets = alive
        dead = [e for e in self.enemies if e.hp <= 0]
        if dead:
            self.kills += len(dead)
            self.enemies = [e for e in self.enemies if e.hp > 0]

    def _check_end(self) -> None:
        if self.player.hp <= 0:
            self.player.hp = 0.0
            self.state = "lost"
            self.bullets.clear()
            return
        if self.time >= self.cfg.duration:
            self.time = self.cfg.duration
            self.state = "won"
            self.enemies.clear()
            self.bullets.clear()
