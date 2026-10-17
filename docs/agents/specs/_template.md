---
id: sp-YYYYMMDD-NNN
backlog: bl-YYYYMMDD-NNN
title: <一句话>
risk_tier: T0 | T1 | T2 | T3
touches:
  - src/<模块>/**
  - tests/<模块>/**
non_goals:
  - <明确不做的事 1>
  - <明确不做的事 2>
rollback: revert 本 PR 即可；无数据迁移 / 有迁移，见下方回滚步骤
verify:
  - unit
  - e2e
  - manual-ui
owner: <人>
created: YYYY-MM-DD
---

# <标题>

## 1. 当前行为（证据）

```console
$ <复现命令>
<真实输出>
```

（附：截图路径 / issue 链接 / Sentry 链接）

## 2. 期望行为 / 验收标准

> 每条都必须可执行，且**在 base commit 上会失败**。不能自动判定的标 `manual`。

- [ ] `ac1` `<命令>` 退出码 0
- [ ] `ac2` <可观察断言，例如：空筛选下导出，文件行数为 0>
- [ ] `ac3` <…>
- [ ] `ac4` `manual` <人工检查项，例如：按钮位置未变>

## 3. 实现思路

<改哪个模块、为什么在这里改>

考虑过但放弃的方案：<…>，因为 <…>。

## 4. 不做什么

见 frontmatter `non_goals`。补充说明：<…>

## 5. 风险与回滚

| 项 | 说明 |
|---|---|
| 最坏情况 | <…> |
| 探测信号 | <上线后看什么指标/日志能发现坏了> |
| 回滚步骤 | <revert / feature flag / 数据修复> |
| 是否单向门 | 是 / 否（是 → T3，必须人工） |

## 6. 验证计划

| 层 | 做什么 | 谁 |
|---|---|---|
| 确定性 | lint / type / test / build | 脚本 |
| 行为 | 按 ac1–ac4 真操作 | verify-behavior |
| 对抗 | revert 实现看测试是否红 | verify-diff |
| 回归 | <相邻功能清单> | verify-diff |

## 7. 评审记录（G1）

| 项 | 结论 |
|---|---|
| spec-lint | pass / fail |
| 独立计划评审 | pass / fail + 意见 |
| 人工批准（仅 T3） | <name> @ <date> |
