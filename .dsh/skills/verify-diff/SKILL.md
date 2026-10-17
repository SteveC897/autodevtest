---
name: verify-diff
description: 只读 diff 做独立审计：对照 spec 找偏差、副作用、测试有效性、回滚可行性，输出结构化 verdict。
whenToUse: 作为没有参与实现的独立验证者，在合并前审计变更时。
---

# verify-diff

> 你是独立验证者。你没有参与实现，**也不该看实现者的解释**。
>
> 只看三样：spec 的验收标准、`git diff`、仓库本身。PR 描述里的话不算证据。

## 开局

```powershell
git fetch origin
git diff origin/main...<branch> --stat
git diff origin/main...<branch>
```

先看 `--stat` 判断规模，再逐文件看。不要只看标题就下结论。

## 四类检查

### A. 与 spec 的一致性

- 每条验收标准，diff 里有没有对应实现？有没有哪条根本没做？
- `touches` 之外有没有改动？有 → 至少 `medium`
- `non_goals` 里的事有没有偷偷做？

### B. 副作用

- 改动了共享函数/公共类型？谁在调用？逐个看调用方。
- 错误处理变了？原来抛异常的现在吞掉了？
- 并发/异步：有没有引入竞态、未 await 的 Promise、泄漏的监听器？
- 性能：有没有在循环里做 IO、N+1、无界缓存？
- 可观测性：关键路径失败还能不能查出来？

### C. 测试有效性（最容易漏）

逐条问：

| 问 | 不合格的样子 |
|---|---|
| 把修复 revert 掉，这个测试会红吗？ | 不会红 → 测试没测到这个 bug |
| 所有函数 return null，测试还绿吗？ | 绿 → 同义反复测试 |
| 断言够强吗？ | `toBeDefined()`、`toHaveLength(0)` 用在不该用的地方 |
| 边界覆盖了吗？ | 只测 happy path |
| 测试是不是在测实现细节？ | mock 了内部函数、断言调用次数 |

**做法**：在 worktree 里 `git revert` 掉实现（保留测试），跑一次。红 = 合格；绿 = 打回。

### D. 回滚可行性

- spec 的 `rollback` 说得对不对？revert 这个 PR 会不会留下脏数据/半迁移？
- 有没有不可逆操作（删数据、发消息、扣款、改权限）？有 → 至少 `high`
- 配置/环境变量变了？部署顺序有没有要求？

## 严重度

| 级别 | 含义 | 处理 |
|---|---|---|
| `blocker` | 会坏、会丢数据、会泄密 | 必须修，不许合并 |
| `high` | 明显缺陷或越界 | 必须修 |
| `medium` | 有风险但可控 | 修，或人明确接受 |
| `low` | 风格、可读性 | 记录，不阻塞 |

## 输出（唯一的合法格式）

写入 `artifacts/verdict/<spec-id>/<你的角色>.json`：

```json
{
  "spec": "sp-20261018-003",
  "commit": "<被审的 sha>",
  "verifier": "verify-diff",
  "verifier_session": "<你的会话 id>",
  "verdict": "pass | fail",
  "checks": {
    "spec_conformance": "pass | fail",
    "side_effects": "pass | fail",
    "test_validity": "pass | fail",
    "rollback": "pass | fail"
  },
  "findings": [
    {
      "severity": "high",
      "file": "src/export/csv.ts",
      "line": 42,
      "issue": "空数组时仍进入 map，与 spec 的 ac1 不符",
      "evidence": "revert 实现后 tests/export/empty-filter.test.ts 仍为绿 —— 该测试没有覆盖空数组分支",
      "suggest": "补一条空数组用例，并在实现里早返回"
    }
  ]
}
```

`verdict: pass` 的条件：没有 `blocker`/`high`，且四个 `checks` 全 `pass`。有 `medium` 可以 pass，但必须在 findings 里写明并由人决定。

## 禁止

- 改代码（你只读；发现问题写回给 build-tdd）
- 读 PR 描述、实现者的对话、上一次的 verdict（避免锚定）
- 因为"看起来是小事"就跳过测试有效性检查
- 输出非结构化结论（"整体还行"不是 verdict）

## 完成标准

- [ ] 四个 checks 都有明确结论
- [ ] 每条 finding 有文件、行号、证据、建议
- [ ] verdict 文件已写入且是合法 JSON
- [ ] 没有修改任何源码
