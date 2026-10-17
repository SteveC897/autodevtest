# DSH 自动开发流水线 · 本仓库安装说明

配套主文档：[DSH自动开发流水线.md](DSH自动开发流水线.md)

这里的文件分两类：**已经装进本仓库生效的**，和**留作模板、供别的仓库用的**。

## 一、已经生效的

| 位置 | 作用 |
|---|---|
| `AGENTS.md`（仓库根） | 宪法：分层禁令、完成定义、已知设计决定。每次请求自动加载 |
| `.dsh/skills/goal-scout/` | 找活：扫仓库 → 写 backlog，只记录不修 |
| `.dsh/skills/spec-writer/` | 把 backlog 写成可验收的 spec |
| `.dsh/skills/build-tdd/` | 先红后绿、收证据、不合并 |
| `.dsh/skills/verify-game/` | 本仓库的验证技能：无头跑、截图、像素断言 |
| `.dsh/skills/verify-diff/` | 独立审计 diff，输出结构化 verdict |
| `.dsh/skills/harden/` | 事故 → 规则，按阶梯修复 |
| `docs/agents/policy.yml` | 风险分级、路径保护、预算 |
| `docs/agents/specs/_template.md` | spec 模板 |
| `docs/agents/templates/night-report.md` | 夜报模板 |
| `docs/agents/queue.md` | 今晚跑什么（只放通过 G1 的 spec） |
| `scripts/scout.py` | 侦察：todo / flaky / lock / layout |
| `scripts/spec_lint.py` | G1 结构检查 |
| `scripts/check_skills.py` | 校验所有 SKILL.md 的 frontmatter（错了 dsh 会静默丢） |
| `scripts/verify.py` | 无头验证，19+ 项检查 |
| `scripts/night-shift.ps1` | 夜班编排（默认干跑、默认不合并） |

`verify-behavior` 没有装进 `.dsh/`：它是通用的"真操作界面"模板（Playwright/桌面 app），
本仓库用 `verify-game` 替代。需要时从 `docs/dsh/skills/` 取。

## 二、命令

```powershell
uv sync                                  # 装依赖
uv run vsproto                           # 跑游戏
uv run python scripts/scout.py           # 侦察，写 backlog
uv run python scripts/spec_lint.py       # 检查所有 spec
uv run python scripts/check_skills.py    # 检查 skill 是否会被加载
uv run pytest                            # 单元测试
uv run python scripts/verify.py          # 无头验证 + 截图
pwsh scripts/night-shift.ps1 -DryRun     # 夜班干跑（没有 pwsh 7 就用 powershell -File）
```

## 三、目录约定

```
AGENTS.md                    宪法（自动加载）
.dsh/skills/<name>/SKILL.md  项目级技能（rank 100，优先级最高）
docs/dsh/                    这套方法论与通用模板
docs/agents/
  policy.yml                 风险与预算
  queue.md                   今晚队列
  specs/                     规格（G1 入口）
  backlog/                   待办（只记录）
  journal/                   每次交付记录
  incidents/                 事故与规则
  nightly/                   夜报
  templates/                 模板
scripts/                     确定性脚本（"厚脚本"）
artifacts/                   证据（gitignored）
```

## 四、搬到另一个仓库

1. 复制 `docs/dsh/AGENTS.template.md` → 目标仓库 `AGENTS.md`，填掉第 0 节的命令。
2. 复制本仓库 `.dsh/skills/` 里除 `verify-game` 外的五个技能；`verify-game` 要按目标产品重写（或改用 `docs/dsh/skills/verify-behavior`）。
3. 复制 `docs/agents/` 的骨架（policy / queue / specs / templates）。
4. 复制 `scripts/scout.py`、`spec_lint.py`、`check_skills.py`，把里面的命令换掉。
5. 写目标仓库自己的 `verify.py`——**这一步不能省**，没有它后面全是空的。

## 五、已知限制

| 限制 | 影响 | 现状 |
|---|---|---|
| 本机没有 `gh` CLI | 不能自动开 PR / 合并 | 编排器跳过 PR 步骤，合并留给人 |
| 只有 Windows PowerShell 5.1（无 `pwsh` 7） | 脚本必须兼容 5.1 | `night-shift.ps1` 已按 5.1 写，并用 `powershell -File` 调用 |
| 没有 linter / 类型检查器 | "lint 层"的约束只能用 `verify.py` 断言代替 | 加依赖需走 spec |
| `schedule` 只在 Web profile 可用 | 定时任务需要常驻 `dsh web` | 用 `scripts/night-shift.ps1` 走外部计划任务 |
| 像素断言绑定 `render.py` 的颜色常量 | 改配色会让验证失败 | 故意的：改配色就该同步改验证 |
| `uv run` 首次会建 `.venv` | 冷启动慢几秒 | 正常 |
