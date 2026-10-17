---
name: harden
description: 把重复出现的错误变成"再也写不出来"的约束：按架构→类型→检查→测试→文档的阶梯修复，并证明能挡住历史错误。
whenToUse: 同一个错误出现 ≥2 次，或晨间抽样发现同类问题时。
---

# harden

> 核心原则：**失败一次可以放过，失败两次要改环境。**
>
> 往 `AGENTS.md` 里加一句提醒是最弱的一层，放在最后。

## 本仓库可用的杠杆（先认清工具）

| 层 | 本仓库有什么 |
|---|---|
| 架构 | 三层拆分（`world` / `render` / `app`）+ 唯一入口 `config.py` |
| 类型 | dataclass + 类型注解；**没有** mypy/pyright（加依赖要走 spec） |
| 检查 | `scripts/verify.py` 的检查项、`scripts/spec_lint.py`、`compileall` |
| 测试 | pytest（11 项） |
| 文档 | `AGENTS.md`、skill |

没有 linter。所以"加一条 lint 规则"在本仓库等于**加一条 `verify.py` 断言**。

## 阶梯（从上往下试，遇到第一个可行的就停）

### 1. 架构消除（最强）

让错误没有地方发生：

- 一类状态只有一个 owner，其他模块只能读（`World` 持有全部状态）
- 一件事只保留一种写法，删掉旧写法（agent 会照抄它看到的代码）
- 把"两个地方都要记得做"变成"一个函数内部保证"
- 用模块边界隔离：`render` 不许改状态，`world` 不许 import pygame

例：总有人把玩法逻辑写进 `app.py` → 让 `app.py` 只保留输入与循环，逻辑函数全部搬进 `World`。

### 2. 类型

让坏状态在写的时候就别扭：

- `Config` 用 frozen dataclass，防止运行中被改
- 状态用 `Literal["running", "won", "lost"]` 而不是裸 `str`
- 边界值集中定义（`config.py`），不要散落在函数里

需要静态检查器时，先在 spec 里申请 `pyright`，不要擅自加依赖。

### 3. 检查（本仓库的"lint"）

在 `scripts/verify.py` 加一条断言，并保证**它能抓到历史上真实发生过的错**：

```python
src = (ROOT / "src/vsproto/world.py").read_text(encoding="utf-8")
check("world.py 不依赖 pygame", "import pygame" not in src)
```

要求：错误信息直接说该怎么做（"把绘制移到 render.py"），不要只说"failed"。

### 4. 测试

- 加一条能复现历史 bug 的测试
- 删掉同义反复的测试（全返回 None 也能过的那种）
- 把"手动检查清单"变成自动断言

### 5. 文档 / AGENTS.md（最弱，最后）

只写需要**判断**的事。机械规则应该已经被上面四层挡住。

## 每条规则的验收：能挡住历史错误

拿真实发生过的那次提交复现：

```powershell
git worktree add .agents/worktrees/harden-check <出问题前的 sha>
cd .agents/worktrees/harden-check
# 把新规则/新测试放进去
uv run python scripts/verify.py   # 期望：这次检查变红
# 或
uv run pytest                     # 期望：失败原因就是当时的 bug
```

**挡不住 = 规则无效，删掉重写。** 不许"先加上，以后再说"。

## incident 记录

`docs/agents/incidents/YYYYMMDD-<短名>.md`：

```markdown
## 症状
## 根因
## 为什么验证没抓到
## 修复层级
架构 / 类型 / 检查 / 测试 / 文档（选一个，说明为什么不能更高）
## 规则验收
commit: <sha>
命令: uv run python scripts/verify.py
期望: 该检查 FAIL
实际: <粘贴输出>
## 同类风险
```

## 批量处理

一周的 incident 摆一起看：按根因聚类（经常 8 条事故是 2 个根因），一个根因只修一次，修在最高可行层级。

## 禁止

- 同一类错误加第二条检查（说明第一条没解决问题，先查为什么）
- 写"请注意……"式的文档规则充当修复
- 加规则但不验证能挡住历史错误
- 为了加规则改测试或生产代码行为

## 完成标准

- [ ] 规则能挡住历史 commit（有输出证据）
- [ ] 错误信息指向正确做法
- [ ] incident 已记录
- [ ] 同类风险已排查（grep 一遍）
