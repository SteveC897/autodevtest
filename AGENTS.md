# AGENTS.md — vsproto

> 本文件每次请求都会加载。只放硬规则；流程细节在 `.dsh/skills/`。

## 0. 命令（照抄，别自己发明）

| 目的 | 命令 |
|---|---|
| 装依赖 | `uv sync` |
| 跑游戏 | `uv run vsproto` |
| 单元测试 | `uv run pytest` |
| 无头验证 | `uv run python scripts/verify.py` |
| 语法检查 | `uv run python -m compileall -q src` |
| 侦察（写 backlog） | `uv run python scripts/scout.py` |
| 规格检查（G1） | `uv run python scripts/spec_lint.py` |
| 技能自检 | `uv run python scripts/check_skills.py` |
| 夜班干跑 | `powershell -NoProfile -File scripts/night-shift.ps1 -DryRun` |

## 1. 这是什么

3 分钟一局的 Vampire Survivors 超小原型。它的用途是**验证"规格 → 实现 → 验证"这条流水线**，不是做成完整游戏。因此：范围小、可验证、不追求好玩。

| 阶段 | skill | 产出 |
|---|---|---|
| 发现 | `goal-scout` | `docs/agents/backlog/*.md` |
| 规划 | `spec-writer` | `docs/agents/specs/*.md` |
| 实现 | `build-tdd` | 分支 + `evidence.json` |
| 验证 | `verify-game` / `verify-diff` | 截图 + 结构化 verdict |
| 回灌 | `harden` | 检查项 / 测试 / 规则 |

一次只做一个 spec。方法论、通用模板与其他仓库的装法在 `docs/dsh/`。

## 2. 分层（改代码前必须知道）

| 文件 | 职责 | 禁令 |
|---|---|---|
| `src/vsproto/world.py` | 纯逻辑模拟 | **禁止 import pygame**；禁止读系统时钟；必须可确定性重放 |
| `src/vsproto/render.py` | 只负责画 | 禁止修改游戏状态 |
| `src/vsproto/app.py` | 窗口、输入、主循环 | 禁止放玩法逻辑 |
| `src/vsproto/config.py` | 所有数值参数 | 调手感只改这里 |
| `scripts/verify.py` | 无头验证 | 见 §3 |

破坏分层直接判定失败。

## 3. 硬规则

- **不合并 PR。** 分支 + draft PR 是你的终点。
- **不许作弊变绿**：不改测试断言、不删测试、不 skip、不把 `verify.py` 的检查放宽。
- **检查项只增不减**：可以加新检查；删掉或降低严格度需要 spec 说明 + 人批准。
- **不加依赖**：除 `pygame-ce`、`pytest` 外，引入任何包都需要先在 spec 里说明理由。
- **不做 spec 外的功能**：现阶段明确不做升级、回血、音效、存档、难度曲线。
- **不碰** `artifacts/`（生成物）和 `.venv/`。

## 4. 完成的定义

- [ ] `uv run pytest` 全绿
- [ ] `uv run python scripts/verify.py` 全过，且检查项数量没有减少
- [ ] 截图/JSON 证据在 `artifacts/verify/<时间戳>/` 里真实存在
- [ ] 改动范围与 spec 的 `touches` 一致
- [ ] 没有新增依赖

## 5. 卡住时

停止，不要重试超过 2 次。写 `docs/agents/journal/<日期>.md`：卡在哪、试过什么、需要人做什么决定。然后结束本轮。

## 6. 已知设计决定（改之前先读）

- **接触伤害有 0.6 秒冷却**：否则三个敌人贴脸会在 0.1 秒内秒杀，原型没法玩。
- **敌人在距主角 520px 外生成**：刚好在视野外，保证"从外面走进来"的观感。
- **敌人 30 血 / 子弹 15 伤害**：两发一只，击杀速度略慢于刷怪速度，所以站着不动必死。
- **胜负同帧时判负**：血归零优先于时间到点。
