---
name: build-tdd
description: 按 spec 在隔离 worktree 里实现：先写失败测试，再实现，收集证据，提交；不合并。
whenToUse: 当 spec 通过 G1，需要真正写代码时。
---

# build-tdd

## 铁律

1. **一次一个 spec。** 不并行、不顺路、不"既然来了就……"。
2. **先红后绿。** 没看到测试在 base commit 上真的失败，不许写实现。
3. **不许作弊变绿。** 见 `AGENTS.md` §3。
4. **不合并。** 你的终点是：分支已推送 + evidence 完整。本机没有 `gh`，开 PR 留给人或以后补。

## 步骤

### 1. 开隔离工作区

```powershell
git fetch origin
git worktree add .agents/worktrees/<spec-id> -b <spec-id> origin/main
cd .agents/worktrees/<spec-id>
```

（会话内也可以用 `create_worktree`，但它只切当前会话；并行任务要各开各的会话。）

### 2. 读 spec，不读别的

只读：spec、`touches` 里的文件、相关测试、`AGENTS.md`。
不要读 backlog 其他条目、不要读别人的 journal。

### 3. 写失败测试

在 base commit（未改实现）上跑，**必须失败**，并留下红色证据：

```powershell
uv run pytest tests/test_world.py -k enemy_overlap 2>&1 | Tee-Object artifacts/red.txt
$code = $LASTEXITCODE
# $code 必须非 0；把命令、退出码、最后 30 行记进 evidence.json 的 red_evidence
```

失败原因必须是"功能缺失"，不是"测试写错了"。断言报错方向不对 → 修断言，重来。

### 4. 实现

最小改动让测试变绿。不提前抽象，不顺手重构。每绿一个单元就 commit：

```powershell
git add -A
git commit -m "fix(render): separate overlapping enemies [sp-20261018-002]"
```

### 5. 跑全量确定性检查

```powershell
uv run python -m compileall -q src
uv run pytest
uv run python scripts/spec_lint.py docs/agents/specs/<spec-id>.md
uv run python scripts/verify.py
```

四项全绿才算过。任何一项红 → 修到绿，不许 skip；修不动 → 按失败处理表停下。

### 6. 自检 diff

```powershell
git diff --stat origin/main...HEAD
git diff origin/main...HEAD --name-only
```

逐项对照：

- [ ] 只涉及 `touches` 内路径
- [ ] 没有改已有测试的断言（新测试除外）
- [ ] `world.py` 仍然没有 import pygame（分层禁令）
- [ ] 没有调试 print、注释掉的代码、`breakpoint()`
- [ ] 没有新增依赖（`pyproject.toml` 没动，或 spec 明确要求）
- [ ] 没有降低 `scripts/verify.py` 的检查严格度

### 7. 写 evidence.json

放在 `artifacts/evidence/<spec-id>.json`（`artifacts/` 已 gitignore）：

```json
{
  "spec": "sp-20261017-002",
  "commit": "<HEAD sha>",
  "base": "origin/main@<sha>",
  "builder_session": "<会话 id，不知道就写 unknown>",
  "commands": [
    { "cmd": "uv run pytest", "exit": 0, "tail": "12 passed" },
    { "cmd": "uv run python scripts/verify.py", "exit": 0, "tail": "20/20 通过" },
    { "cmd": "uv run python scripts/spec_lint.py docs/agents/specs/sp-...md", "exit": 0 }
  ],
  "red_evidence": { "cmd": "uv run pytest -k enemy_overlap", "exit": 1, "tail": "assert 12 == 0" },
  "artifacts": ["artifacts/red.txt", "artifacts/verify/<时间戳>/01-running-3s.png"],
  "diff_stat": { "files": 2, "added": 31, "removed": 4 },
  "touched": ["src/vsproto/render.py", "tests/test_world.py"],
  "notes": ""
}
```

`exit` 必须是真的退出码，`tail` 必须是真的输出片段。伪造证据比不交更严重。

### 8. 推送

```powershell
git push -u origin <spec-id>
```

本机没有 `gh`，不要假装开了 PR。在 journal 里写一行：`PR: 待创建（分支 <spec-id> 已推送）`。

### 9. 停

输出：分支名、commit、evidence 路径、还剩什么风险。然后结束。

## 失败处理

| 情况 | 做法 |
|---|---|
| 测试写不出失败 | spec 的验收标准有问题 → 停下，回 spec-writer |
| 实现超 `touches` | 停下，写 blocked，申请扩范围 |
| 依赖缺失/环境坏了 | 停下，写 blocked（这类要人修环境） |
| 同一错误修 2 次仍红 | 停下，写 blocked，别烧第 3 次 |
| `docs/agents/STOP` 出现 | 立即停，输出当前状态 |

## 完成标准

- [ ] 测试在 base 上红、现在绿（两份证据都有）
- [ ] compileall / pytest / spec_lint / verify 全绿
- [ ] evidence.json 完整且真实
- [ ] 分支已推送
- [ ] 没有合并
