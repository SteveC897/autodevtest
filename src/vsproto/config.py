"""全局参数。改这里 = 改手感，不用翻代码。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    # 场地与镜头
    arena_w: float = 2400.0
    arena_h: float = 2400.0
    view_w: int = 960
    view_h: int = 600
    duration: float = 180.0
    seed: int = 7

    # 主角
    player_radius: float = 14.0
    player_speed: float = 230.0
    player_hp: float = 100.0
    contact_damage: float = 12.0
    contact_cooldown: float = 0.6

    # 敌人
    enemy_radius: float = 12.0
    enemy_speed: float = 65.0
    enemy_hp: float = 30.0
    spawn_interval: float = 0.55
    spawn_min_dist: float = 520.0

    # 武器（强能魔杖式：自动打最近的）
    weapon_range: float = 420.0
    weapon_interval: float = 0.45
    bullet_speed: float = 560.0
    bullet_damage: float = 15.0
    bullet_radius: float = 5.0
    bullet_life: float = 1.2
