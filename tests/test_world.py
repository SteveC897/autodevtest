from __future__ import annotations

import math
from dataclasses import replace

from vsproto.config import Config
from vsproto.world import Bullet, Enemy, World


def cfg(**kw) -> Config:
    return replace(Config(seed=1), **kw)


def run(world: World, seconds: float, move=(0.0, 0.0), fps: int = 60) -> None:
    dt = 1.0 / fps
    for _ in range(round(seconds * fps)):
        world.step(dt, move)
        if world.state != "running":
            break


def quiet(**kw) -> Config:
    """不刷怪、不开火的配置，用来隔离单个机制。"""
    base = dict(spawn_interval=1e9, weapon_interval=1e9)
    base.update(kw)
    return cfg(**base)


def test_player_starts_at_center() -> None:
    w = World(cfg())
    assert (w.player.x, w.player.y) == (1200.0, 1200.0)
    assert w.player.hp == 100.0
    assert w.state == "running"


def test_player_is_clamped_inside_arena() -> None:
    w = World(quiet(player_hp=1e9))
    run(w, 20.0, move=(-1.0, 0.0))
    assert math.isclose(w.player.x, w.cfg.player_radius)
    run(w, 20.0, move=(0.0, -1.0))
    assert math.isclose(w.player.y, w.cfg.player_radius)


def test_enemies_spawn_far_from_player() -> None:
    w = World(cfg(spawn_interval=0.5))
    run(w, 0.6)
    assert w.enemies, "0.6 秒内应该至少刷出一个敌人"
    for e in w.enemies:
        d = math.hypot(e.x - w.player.x, e.y - w.player.y)
        assert d >= w.cfg.spawn_min_dist * 0.75 - 2


def test_enemy_speed_is_constant() -> None:
    w = World(quiet())
    w.enemies.append(Enemy(w.player.x + 300, w.player.y, 30, 12))
    d0 = math.hypot(w.enemies[0].x - w.player.x, w.enemies[0].y - w.player.y)
    run(w, 1.0)
    d1 = math.hypot(w.enemies[0].x - w.player.x, w.enemies[0].y - w.player.y)
    assert 63.0 <= (d0 - d1) <= 67.0, f"1 秒应接近 65px，实际 {d0 - d1:.2f}"


def test_auto_fire_targets_nearest_enemy() -> None:
    w = World(cfg(weapon_interval=0.1, spawn_interval=1e9))
    near = Enemy(w.player.x + 100, w.player.y, 30, 12)
    far = Enemy(w.player.x + 300, w.player.y, 30, 12)
    w.enemies = [far, near]

    run(w, 0.11)
    assert w.shots == 1
    b = w.bullets[0]
    assert b.vx > 0 and abs(b.vy) < 1e-6, "应该朝右侧最近的敌人开火"

    run(w, 0.2)
    assert near.hp < 30.0 or near not in w.enemies


def test_bullet_kills_enemy_and_counts() -> None:
    w = World(quiet())
    w.enemies = [Enemy(w.player.x + 20, w.player.y, 15, 12)]
    w.bullets.append(Bullet(w.player.x, w.player.y, 560, 0, 1.0, 5))
    run(w, 0.1)
    assert w.kills == 1
    assert w.enemies == []


def test_contact_damage_respects_cooldown() -> None:
    w = World(quiet())
    w.enemies = [Enemy(w.player.x, w.player.y, 30, 12)]
    hp0 = w.player.hp

    w.step(1 / 60)
    assert math.isclose(w.player.hp, hp0 - 12.0)

    w.step(1 / 60)
    assert math.isclose(w.player.hp, hp0 - 12.0), "冷却期内不应再次扣血"

    run(w, 0.7)
    assert w.player.hp <= hp0 - 24.0


def test_death_ends_run_and_freezes_state() -> None:
    w = World(quiet(player_hp=10))
    w.enemies = [Enemy(w.player.x, w.player.y, 30, 12)]
    w.step(1 / 60)
    assert w.player.hp == 0.0
    assert w.state == "lost"

    before = w.snapshot()
    w.step(1 / 60)
    assert w.snapshot() == before, "结束后不应再推进"


def test_victory_at_duration_clears_enemies() -> None:
    w = World(cfg(duration=2.0, player_hp=1e9))
    run(w, 2.5)
    assert w.state == "won"
    assert w.enemies == []
    assert w.bullets == []
    assert math.isclose(w.time, 2.0)


def test_no_healing_ever() -> None:
    w = World(cfg(player_hp=50, spawn_interval=0.2, duration=60))
    hp = w.player.hp
    for _ in range(600):
        w.step(1 / 60)
        assert w.player.hp <= hp
        hp = w.player.hp


def test_same_seed_and_input_is_deterministic() -> None:
    a = World(cfg(seed=3))
    b = World(cfg(seed=3))
    for _ in range(600):
        a.step(1 / 60, (0.3, -1.0))
        b.step(1 / 60, (0.3, -1.0))
    assert a.snapshot() == b.snapshot()
