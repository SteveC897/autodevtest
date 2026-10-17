---
name: spec-writer
description: 把一条 backlog 写成可验收的 spec：问题、可执行验收标准、实现思路、不做什么、风险分级。
whenToUse: 当某条 backlog 状态为 ready，需要进入实现之前。
---

# spec-writer

## 铁律

1. **验收标准必须可执行。** 是命令、退出码、像素值、可观察断言。写不出来 → 回 `needs_info`。
2. **每条标准必须能在 base commit 上失败。** 不能失败的"验收标准"是在测别的东西。
3. **先复现，再写方案。** 没复现过的 bug，你写的方案一定是错的。
4. **不写实现细节。** 写到"改哪个模块、为什么在这里改"就够了。

## 步骤

1. 读 backlog 条目和它引用的证据，**亲手复现一次**。复现不了 → 标 `needs_info`。
2. 读 `docs/agents/policy.yml`，确定 `risk_tier` 和 `touches`。
3. 复制 `docs/agents/specs/_template.md` 到 `<id>.md` 并填写。
4. 自检（逐条打勾，不许跳）：
   - [ ] 每条验收标准都有对应命令/断言
   - [ ] 每条标准都在 base 上试过并失败（把失败输出贴进"当前行为"）
   - [ ] `touches` 覆盖所有预期路径，且没有 `src/**` 这种过宽写法
   - [ ] `non_goals` 至少 2 条
   - [ ] `rollback` 写清怎么撤
   - [ ] `risk_tier` 与路径规则一致（拿不准往高报）
5. 跑：

   ```powershell
   uv run python scripts/spec_lint.py docs/agents/specs/<id>.md
   ```

   必须退出码 0。
6. 输出给人看 5 行以内：解决什么、怎么验收、风险、大概改哪。

## 好标准的例子（本仓库）

```markdown
- [ ] `uv run pytest tests/test_world.py -k enemy_overlap` 退出码 0
- [ ] `uv run python scripts/verify.py` 的 `敌人重叠` 检查通过
- [ ] 两只敌人中心距 < 24px 时，渲染出的描边仍能区分（截图像素断言）
- [ ] 帧率无关：`world.step` 在 dt=1/30 与 1/120 下，10 秒后的相对位置差 < 2px
```

`verify` 字段取这几个值之一：`unit | headless | entry-smoke | manual`。

## 反模式

| 写法 | 为什么错 |
|---|---|
| "敌人重叠问题修好" | 不可判定 |
| "调用 `separate()` 且返回值正确" | 测实现细节，重构就坏 |
| "玩家不会遇到重叠" | 那是设计判断，不是验收 |
| `touches: [src/**]` | 等于没有范围，G2 无法校验 |
| `risk_tier: T0` 但动了渲染 | 风险定级过低，应至少 T1 |

## 完成标准

- [ ] `spec_lint.py` 通过
- [ ] 评审 agent 只看 spec 就能判断"做完了没有"
- [ ] 评审 agent 指出的"能骗过验收标准的假实现"已被堵上
