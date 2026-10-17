# DSH 自动开发流水线

> 目标：让 agent 在你睡觉时自己找活、自己规划、自己实现、自己验证、按风险决定能不能合并；你每天只花 15 分钟抽样和"改环境"。
>
> 参考案例：Matt Pocock × Lauren Tan（poteto）2026-10-02 的访谈（你给的 YouTube / B 站链接），以及 pstack。
>
> 本文只讲**怎么在 deepseek-harness 上做**，不讲通用的"AI 编程心得"。

---

## 0. 先给结论

**吞吐量不取决于模型有多自主，而取决于两件事：错误能不能被机器挡住，人是不是还在当信息搬运工。**

所以整条流水线只围绕三个投资方向：

| 投资 | 做法 | 对应 dsh 原语 |
|---|---|---|
| **环境**：让错误写不出来 | 类型 / lint / 架构约束 / 确定性脚本 | AGENTS.md + 插件 + 仓库工具链 |
| **验证**：让 agent 看得见结果 | 六段式验证技能 + 独立验证者 + 确定性闸门 | Skills（带 scripts）+ subagent |
| **外环**：让活自己找上门 | 定时扫描 → 缓冲 → 排序 → 无人值守执行 | schedule + headless + 插件 |

三条**不可协商**的硬规则：

1. **写代码的 agent 不能合并自己的代码。** 合并是工具（插件）的判定，不是模型的声明。这条对应 pstack 的 owner ≠ verifier。
2. **验收标准必须可执行。** 是命令、是断言、是"文件能打开且大小 > 0"，不是"功能正常"。写不出来就说明还没想清楚，打回 L1。
3. **同一个错误出现两次，改环境，不加提示词。** 顺序固定：架构 → 类型 → lint → 测试 → 文档。

**预期管理**：第一个月 30–80 个合并 PR（含大量 gardening），第三个月 150–400。2,500/月 是"代码库已经被改造成可验证"之后的结果，不是起点。pstack 作者本人也说过：光装 pstack 到不了她那个程度。

---

## 1. 案例拆解：2,500 个 PR 到底是什么

流传版本和实际做法的差距，基本决定了你会不会照着做然后失望。

| 流传说法 | 实际（访谈 + pstack 文档） |
|---|---|
| 一个月 2,500 个功能 PR | 大部分是她说的 **gardening**（代码库养护：清坏模式、补 lint、重命名、删死代码）。她本人主动降过温："显然不是 2,500 个功能" |
| 不审查就合并 | **合并前不逐个人工阻塞**，但每个 PR 要过：独立验证代理的干净结论 + CI；她**每天仍然看 PR**，只是事后抽样 |
| 一个人干出来的 | 十多个"幕僚长"（coordinator，自己不写码）+ 每个 PR 一个 owner agent + 每个 PR 一批 verifier |
| 装个 pstack 就行 | 本人明确否认。护城河是验证技能、lint/类型/架构、外部信息自动流入 |
| AI 自己检查自己 | 文档写得很清楚：**owner 自己说了不算**，合并许可以根代理汇总的验证结论为准；每推一次补丁重跑一轮验证；根代理每小时审计；操作者可以随时叫停 |

数字口径：2,500 是 2026-09-21 演讲标题；The Neuron 引用她 8 月结算为 2,462；访谈里她说"两千上下"。全部是本人自报，无第三方审计。

**真正可迁移的是这 6 个机制**（后面每一节都对应其中一个）：

| # | 机制 | 一句话 |
|---|---|---|
| 1 | 验证技能 | 给 agent 手和眼：能启动 app、能像用户一样操作、能取证 |
| 2 | 薄技能 + 厚 CLI | 判断留给模型，机械步骤写成脚本/CLI，所有 agent 共用同一套 |
| 3 | `/correct` 阶梯 | 同一个错出现两次，从最高层修：架构 → 类型 → lint → 测试 → 文档（最后） |
| 4 | 双环 | 外环收集信号（Slack/Issue/日志/CI），内环实现；人不再当中继 |
| 5 | 缓冲 | 扫描结果**先记录不修**，攒几天看模式，一次修根因 |
| 6 | 闸门 | owner ≠ verifier；补丁重推重验；审计；急停 |

**不能直接搬的**：pstack 是 Cursor 插件，依赖 Cursor 的 `/loop` 和云端 agent。技能本体是 MIT 的 Markdown，可以改写成 dsh skill，但执行系统必须用 dsh 的 goal / ralph / schedule / headless 重搭 —— 这正是第 2 节要讲的。

从 Matt Pocock 那边拿三样东西（他是需求侧，poteto 是执行侧）：

- **grilling**：用追问把"我想要个导出按钮"逼成"点击导出后 3 秒内下载一个能被 Excel 打开、且行数等于当前筛选结果的 CSV"。
- **一词一意**：给 agent 一套稳定词汇（spec / evidence / verdict / gardening / one-way door），它会把这个词带进推理，行为会跟着变。
- **不会说谎的测试**：函数全返回 null 仍然通过的测试，等于没有测试。

---

## 2. dsh 能给你什么，给不了什么

这是全篇最重要的一节。方案里的每一个动作都必须落在下面这些真实能力上。

| dsh 原语 | 给你什么 | 真实边界（别踩） | 在本方案中的位置 |
|---|---|---|---|
| **AGENTS.md** | 分层指令：`~/.dsh/AGENTS.md` → `~/.agents/AGENTS.md` → 仓库根到 cwd 每一层；`AGENTS.local.md` 叠加；每次请求都在 | 默认 64KB 预算，**宽泛的先被丢**；不支持 `@import`、不解析 `.claude/rules`；外部编辑不会实时热更 | 仓库"宪法"：硬规则、风险分级、目录约定 |
| **Skills** | `.dsh/skills/<name>/SKILL.md` 或 `.agents/skills/`，可带 `scripts/` `references/`；热加载；渐进披露（目录只放一行描述） | 只扫一层（`<root>/<name>/SKILL.md`），name 必须 kebab-case，frontmatter 错一个字段整个 skill 静默消失 | 6 个核心技能：侦察/规格/实现/验证×2/回灌 |
| **插件** | npm 包 + `dsh.bundle.patch` + `cordis.patch.yml`；可注册工具、监听事件、拦截工具执行 | 要处理版本兼容；profile 级安装 | 硬闸门：`request_merge`、STOP 开关、证据校验 |
| **Goal** | 同会话自动续行，`maxGoalRounds` 轮，idle 才启动，会等子 agent 结束 | **没有独立评估器**（完成靠自述）；resume/fork 后默认关闭续行；不计 token/时间预算 | 第 1 阶段的夜间驱动 |
| **Ralph** | 每轮一个全新 agent，只传有界交接；workspace 是唯一长期记忆 | 前台阻塞；无验证器；普通子 agent 失败会终止整轮 | 长任务、防上下文腐化 |
| **Schedule** | cron/每日/每周/定时；**宿主重启后仍在**；到点会冷恢复会话 | 只能挂在 Web profile（需要 session controller），**headless 挂不了** | 夜间触发器、晨报、小时审计 |
| **Headless** | `dsh --profile headless "任务"`，一次性、不开端口、退出码、`--json` 事件流、`--session-id` 续接 | 一次一个任务，无交互后续；不读 GUI 凭据（用环境变量 / `.env`） | 外部编排器的执行单元 |
| **Worktree** | 从本地提交建隔离检出 + 新分支，切当前会话 cwd | 一个会话只能待在一个工作树；子 agent 继承 cwd；只负责创建，不负责清理合并 | 每任务一个隔离工作区 |
| **Subagent** | 独立上下文，可指定 cwd、可 fork 或 fresh | 返回的是**自述结果**，不可信；成本按份计 | 实现者、验证者、侦察兵 |
| **Agent Team** | Lead + 具名 teammate + 持久任务板（CAS、写域提示） | **共享 checkout**，无文件系统隔离；单进程 | 白天人盯着时的并行协作 |
| **Workflow** | JS 脚本扇出，pipeline/parallel，schema 校验 | 脚本内无文件/网络 | 批量侦察、批量验证 |
| **Auto review** | 每次工具调用前用模型判风险 | 是**权限审查**，不是代码评审；要开 Web 层；吃 token | 无人值守时的安全网（可选） |
| **权限预设** | 沙箱模式 + 审批策略捆绑；`danger-full-access` + `never` | `never` 是**确定性拒绝**，不是自动通过 —— 会 fail-closed 卡住 | 无人值守的权限底座 |

### dsh 缺的三块，必须自己补

1. **独立评估器。** goal 和 ralph 的"完成"都是 worker 自己说的，README 明说没有评估器。→ 用"验证者 ≠ 实现者"的进程隔离 + 确定性闸门补上（第 7 节）。
2. **PR 生命周期。** dsh 没有 PR / merge 概念。→ 插件工具 `request_merge` + `gh` CLI + **双 token**（builder 的 token 没有 merge 权限，merge 由编排器持有）（第 8 节）。
3. **外环连接器。** Slack/Linear/Sentry 没有现成插件。→ MCP client + `gh` + schedule 起一个只读侦察会话（第 4 节）。

---

## 3. 架构：六层五闸

```
外部信号                      ┌─────────── 人（每天 15 分钟）───────────┐
Issue/CI/日志/依赖/覆盖率 ──▶ │ 抽样 review · 只改环境 · 调 backlog 顺序 │
                              └──────────────────┬──────────────────────┘
                                                 │ 规则回灌
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌───▼──────┐   ┌──────────┐   ┌──────────┐
│ L0 Scout │──▶│ L1 缓冲  │──▶│ L2 Spec  │──▶│ L3 Build │──▶│ L4 Verify│──▶│ L5 Merge │
│ 只记录   │   │ backlog  │   │ G1 规格闸│   │ G2 证据闸│   │ G3 验证闸│   │ G4 合并闸│
└──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘   └────┬─────┘
      ▲                                                                          │
      └──────────── L6 Harden：事故 → 规则（架构 > 类型 > lint > 测试 > 文档）◀──┘
```

| 层 | 输入 → 输出 | 谁执行 | 上下文策略 | 闸门 |
|---|---|---|---|---|
| L0 侦察 | 信号 → `backlog/<id>.md` | 定时 headless / 只读子 agent | 每次全新 | 无（只写不修） |
| L1 缓冲 | backlog → 排序后的 ready 队列 | 确定性脚本 + 每周 gardener | 无模型 | **G0** 就绪定义 |
| L2 规格 | ready 项 → `specs/<id>.md` | 同会话 planner | 读 backlog + 代码 | **G1** spec-lint + 计划评审 |
| L3 实现 | spec → 分支 + commits + `evidence.json` | 每任务一个 worktree 会话 | fresh（只给 spec） | **G2** 证据完整 |
| L4 验证 | 分支 → 结构化 verdict | 2–4 个独立验证者 | fresh（**不给实现者解释**） | **G3** 全绿 |
| L5 合并 | verdict → merged / draft | `request_merge` 工具 | 无模型 | **G4** 策略判定 |
| L6 回灌 | 事故 → 规则 | 周会话 + 人 | 读 incidents | 每周指标复核 |

**为什么是六层而不是一个"超级 agent"**：每一层都可以单独失败、单独重跑、单独审计。单个会话包办全部，失败了你看不出是哪一步错的，也没法重跑。

---

## 4. L0 + L1：自动找目标

### 4.1 信号源（先接 5 个就够）

| 信号 | 采集方式 | 产出 |
|---|---|---|
| 不稳定测试 | 同一测试连跑 3 次 | flaky 清单 |
| 覆盖率缺口 | 覆盖率报告 ∩ 最近 30 天改动 | 未覆盖的新代码 |
| TODO/FIXME/HACK | ripgrep + git blame 年龄 | 陈旧 TODO |
| 依赖问题 | `npm outdated` / audit / `cargo deny` | 升级与漏洞 |
| 文档漂移 | 把 README 里的命令真跑一遍 | 跑不通的命令 |
| 类型逃逸 | `any` / `ts-ignore` / `# type: ignore` 计数 | 类型债务 |
| 死代码 | knip / ts-prune / vulture | 可删清单 |
| 性能预算 | bundle size、p95、启动耗时 | 回归项 |
| 错误聚合 | Sentry MCP 或日志 Top N | 真实用户痛点 |
| Issue/PR 评论 | `gh` CLI | 外部需求 |
| 构建警告 | 编译器/lint 输出 | 噪音治理 |
| 重复实现 | 组件/工具函数重复 | 设计系统偏离 |

### 4.2 缓冲，不急着修

扫描结果**只写 backlog，不改代码**。这是 poteto 的"攒着看"：一天一条看不出来，攒一周经常发现"这 15 条其实是同一个根因"。

```
docs/agents/backlog/<fingerprint>.md
```

```yaml
---
id: bl-20261018-003
title: 导出 CSV 在空筛选结果时崩溃
source: sentry
evidence: https://sentry.io/.../events/abc  (12 次/7 天，全部 iOS 17)
fingerprint: export-csv-empty-filter
impact: 4        # 1-5
effort: 2        # 1-5
confidence: 0.9
risk_tier: T2    # T0-T3，见 §8
blast_radius: [src/export, src/filters]
status: ready    # ready | needs_info | blocked | done
created: 2026-10-18
---
## 现象
## 复现步骤
## 为什么现在做（或不做）
```

**排序是确定性的，不交给模型**：

```
priority = impact × confidence / effort
同分按 risk_tier 升序（先做低风险的）
```

脚本 `scout.ps1` 负责跑检查、去重（按 fingerprint）、写文件、排序；模型只负责**写现象描述和判断影响**。这又是"薄技能 + 厚脚本"。

### 4.3 G0：就绪定义（Definition of Ready）

一条 backlog 要进 L2，必须同时满足：

- [ ] 有可复现的证据（链接 / 命令 / 截图），不是"听说"
- [ ] 影响面能说清（哪些路径、哪些用户）
- [ ] 不依赖未决策的产品问题
- [ ] 预估 effort ≤ 3（大了就拆）

不满足就留在 `needs_info`，**不许"边做边想"**。无人值守最怕的就是这种任务——它会在半夜消耗两小时然后写一份你早上看不懂的报告。

---

## 5. L2：规划（把意图变成可验收的东西）

### 5.1 spec 模板

```yaml
---
id: sp-20261018-003
backlog: bl-20261018-003
risk_tier: T2
touches: [src/export/**, tests/export/**]
non_goals: [不做服务端导出, 不改 API]
rollback: revert PR 即可；无数据迁移
verify: [unit, e2e, manual-ui]
---
```

正文四段，缺一不可：

1. **问题与证据**：现在错在哪，怎么证明它错（复现命令/录屏）。
2. **验收标准**：每条都必须是**可执行**的。例：
   - `pnpm test tests/export/empty-filter.test.ts` 退出码 0
   - 空筛选结果下点击导出，3 秒内下载文件，文件头为 `id,title,...`，行数 = 0
   - 非空筛选下导出，行数 = 列表显示行数
3. **实现思路**（允许粗略）：改哪里、为什么在这里改、有没有更简单的办法。
4. **不做什么**：明确写出 non-goals，防止 agent 顺手重构。

### 5.2 三条验收标准判据

- **能自动判定**：命令、断言、文件属性。做不到就降级成"人工检查清单"，并标 `manual`，这类不允许自动合并。
- **能证明之前是坏的**：每条标准在 base commit 上必须失败。失败不了，说明你测的不是这个 bug。
- **不测实现细节**：不写"调用了 formatCsv()"，写"输出符合 CSV 规范"。

### 5.3 G1：规格闸

1. `spec-lint`（脚本）：字段齐全？验收标准含命令？`touches` 与 `risk_tier` 匹配？non_goals 非空？
2. **独立计划评审**（fresh 子 agent，只读 spec + 相关代码）：这个方案会漏掉什么？有没有更小的做法？验收标准能不能被"假实现"骗过？
3. T3 风险 → 人工批准（在 PR 上留 `approved-by-human` 标签）。

评审不过 → 回 L1，不进入实现。

---

## 6. L3：实现

### 6.1 隔离

一个 spec = 一个 worktree = 一个分支 = 一个会话。

```powershell
# 方式一：会话内创建（dsh worktree 工具）
create_worktree({ name: "sp-20261018-003", from: "origin/main" })

# 方式二：编排器预建，子 agent 直接 cwd 进去（推荐并发时用）
git worktree add .agents/worktrees/sp-003 -b sp-003 origin/main
```

注意：`create_worktree` 改的是**当前会话**的 cwd，子 agent 继承。所以别在一个会话里切来切去跑并行——每个并行任务要独立会话（或独立子 agent + 指定 cwd）。

### 6.2 硬流程（写进 skill，不靠自觉）

1. 读 spec，不读 backlog 里的其他条目（防跑题）。
2. **先写失败测试**，跑一次，把红色输出存进 evidence。红色不真，后面全白做。
3. 实现，直到测试绿。
4. 跑全量确定性检查（lint / type / test / build）。
5. 自检 diff：有没有改 `touches` 之外的文件？有没有动测试断言？有没有 `--no-verify`？
6. 每完成一个可验证单元就 commit：`feat(export): handle empty filter result [sp-20261018-003]`。
7. 写 `evidence.json`。
8. **停**。不许自己合并。

### 6.3 禁止清单（AGENTS.md 里写死，插件再兜一层）

- 改 CI 配置、改 lint 规则、改 tsconfig 严格度
- 删测试、跳测试、把断言改松、加 `--no-verify`
- `git push --force`、直接推 main
- 执行 `gh pr merge`
- 改 spec 的验收标准（发现 spec 错了 → 停下改 spec，不是改标准凑绿）
- 跨 spec 顺手重构

### 6.4 evidence.json（合并的唯一凭据）

```json
{
  "spec": "sp-20261018-003",
  "commit": "a1b2c3d",
  "base": "origin/main@f9e8d7c",
  "builder_session": "session-...",
  "commands": [
    {"cmd": "pnpm test tests/export/empty-filter.test.ts", "exit": 0, "tail": "..."},
    {"cmd": "pnpm lint", "exit": 0},
    {"cmd": "pnpm build", "exit": 0}
  ],
  "red_evidence": {"cmd": "pnpm test ...", "exit": 1, "tail": "expected 0 rows, got TypeError"},
  "artifacts": ["artifacts/empty-filter-export.mp4", "artifacts/export-empty.csv"],
  "diff_stat": {"files": 4, "added": 62, "removed": 11},
  "touched": ["src/export/csv.ts", "tests/export/empty-filter.test.ts"],
  "notes": "顺手把空数组的 early return 提到了调用前"
}
```

**G2 证据闸**（脚本判定，不看模型自述）：命令全部 exit 0、`red_evidence` 存在、`touched ⊆ spec.touches`、diff 未超限、artifacts 真实存在、时间戳在 2 小时内。

---

## 7. L4：验证

### 7.1 三层，缺一不可

| 层 | 做什么 | 谁 | 判据 |
|---|---|---|---|
| 确定性 | lint/type/test/build/coverage/perf | 脚本 | 退出码 |
| 行为 | 真启动 app，真点，真取证 | 验证技能 + 验证 agent | 截图/视频 + 断言 |
| 对抗 | 找"看起来对但其实错" | 独立验证 agent | 结构化 verdict |

### 7.2 验证者的独立性（这是最重要的一条）

验证者必须是 **fresh 子 agent**，输入只有三样：

1. spec 里的验收标准（**不是**实现者的解释）
2. `git diff origin/main...HEAD`
3. 仓库访问权

**不给**：实现者的对话、实现者的说明、PR 描述。pstack 文档里那句"审计差异且不采信 PR 说明"就是这个意思——描述会让验证者被锚定。

验证者**只读**，发现问题写回，由 builder 修。修改后**整轮重跑**，不能只跑失败那条。

### 7.3 验证者分工（2 个起步，4 个封顶）

| 角色 | 看什么 | 输出 |
|---|---|---|
| 行为验证 | 验收标准逐条过，真操作 | 每条：pass/fail + 证据路径 |
| 差异审计 | diff 本身：副作用、越界、错误处理 | 问题清单 + 严重度 |
| 测试有效性 | 测试会不会说谎 | 见下 |
| 回归/边界 | 相邻功能、异常输入 | 反例 |

### 7.4 测试有效性四问（廉价反作弊）

1. **回滚检验**：把修复 revert 掉，新测试必须失败。不失败 = 测试没测到这个 bug。
2. **空实现检验**：所有函数 return null，测试还全绿？那测试是同义反复（Matt 的说法），删掉重写。
3. **断言强度**：`expect(x).toBeDefined()` 不算断言。
4. **边界覆盖**：空、单元素、超大、并发、异常输入，各有一条。

### 7.5 G3：验证闸

- 确定性检查全绿（最近一次提交，不是历史某次）
- 行为验证：验收标准 100% pass
- 差异审计：无 high 级问题
- 至少 2 个验证者的 verdict，且 `verifier.session ≠ builder.session`
- 分支已 rebase 到最新 main，且 rebase 后重跑通过

任何一条不满足 → 回 L3。**不允许"这条先忽略"**。

---

## 8. L5：合并

### 8.1 风险分级（写进 AGENTS.md，工具强制执行）

| 级别 | 典型改动 | 合并方式 |
|---|---|---|
| **T0** | 文档、注释、typo、纯测试、补丁级依赖 | CI 绿即自动合并 |
| **T1** | 内部重构、无行为变化、有测试覆盖 | 2 验证者 + CI 绿 → 自动合并 |
| **T2** | 用户可见行为、UI、API 兼容范围内 | 同上 + 次日必抽样；有条件上 canary |
| **T3** | 数据库迁移、鉴权、支付、删除数据、发布配置、密钥 | **只给人**。agent 最高只到 draft PR + ready 标签 |

判定规则：`risk = max(spec.risk_tier, 路径规则, diff 规模规则)`。碰到 `.github/workflows/**`、`migrations/**`、`infra/**`、`**/auth/**` 直接升 T3。

### 8.2 `request_merge` 工具（插件实现）

模型调用它，它做 7 项校验，全过才真正合并：

1. `docs/agents/STOP` 不存在（急停）
2. `evidence.json` 完整且新鲜（< 2h）
3. verdict ≥ 2 且验证者 ≠ 实现者
4. `touched ⊆ spec.touches`，diff ≤ 上限（建议 400 行 / 12 文件）
5. 未触 T3 路径（除非带人工批准 token）
6. `gh pr checks` 全绿
7. rebase 到最新 main 后 CI 仍绿

返回 `merged` / `needs_human(原因)` / `blocked`。**模型永远拿不到"直接 merge"的能力**：

- builder 用的 GitHub token 没有 merge 权限（硬边界，不靠提示词）
- merge 由编排器用另一个 token 执行
- 插件在 `pre-execute` 拦 `gh pr merge` 之类命令（软边界，防手滑）

### 8.3 合并队列

- 同一时间只允许一个合并（串行），避免互相 rebase 打架
- 合并方式 squash，commit message 带 spec id
- 合并后 5 分钟跑一次 smoke，失败自动 revert（T1/T2）
- 每晚最多合并 N 个（防止一次事故污染整个夜晚），默认 N = 20

### 8.4 第一周不要夜间合并

顺序是：**先 draft PR（人合并）→ 再 T0/T1 夜间自动合并 → 最后才 T2**。poteto 也说了第一天她怕"半夜出 SEV"。信任是靠数据挣的，不是靠配置。

---

## 9. L6：回灌（真正拉开差距的一层）

### 9.1 晨间 15 分钟（固定动作）

1. 读夜报 `docs/agents/nightly/2026-10-18.md`（脚本生成，含：合并数、失败数、阻塞原因分布、成本）
2. 抽 3 个 PR：**最大 diff 的、T2 的、验证结论最薄的**
3. 看 3 个阻塞项：是环境问题还是任务问题？
4. **只做一件事**：把出现 ≥ 2 次的错误变成一条规则
5. 调 backlog 前 3 条

不要在这一步写代码。你写代码的时间应该拿去改环境。

### 9.2 阶梯（从高到低试，文档永远最后）

1. **架构消除**：一类状态只有一个 owner；一件事只留一种写法；删掉 agent 会照抄的旧实现。
2. **类型**：让坏状态编译不过（判别联合、branded type、穷尽检查）。
3. **lint / CI**：类型管不住的，加规则；错误信息要直接写"改用 X"。
4. **测试**：行为测试兜底；把同义反复的测试删掉。
5. **AGENTS.md**：只留给真正需要判断的事——因为它最弱，模型跳过时什么都不会坏。

### 9.3 每条新规则的验收

**必须能挡住一个真实发生过的错**：拿事故 commit 复现，规则生效（lint 报错 / 类型报错 / 测试失败），记录在 incident 里。挡不住的规则是噪音，删掉。

### 9.4 每周 1 小时：模式评审

- 把本周所有 incident 摆一起，找共同根因
- 一个根因只修一次
- 更新指标，决定下周信任等级（升还是降）

---

## 10. 时间轴：一天怎么跑

### 10.1 推荐节奏

| 时间 | 谁 | 做什么 |
|---|---|---|
| 09:00 | 人 | 15 分钟晨间流程（§9.1） |
| 09:30 | planner 会话 | 把 backlog top 3 写成 spec，跑 G1 |
| 10:00–18:00 | builder + verifier | 白天任务，人可随时介入 |
| 18:30 | 人 | 确认今晚队列（哪些 spec 允许跑） |
| 22:30 | schedule | 触发夜班：只跑 `status: ready` 且 `risk ≤ T2` 的 spec |
| 23:00–06:00 | builder → verifier → merge | 逐任务串行或 2 路并行 |
| 06:30 | schedule | 生成夜报 + 更新 backlog 状态 |
| 07:00 | 人 | 晨间流程 |

### 10.2 两种夜间驱动方式（这是最容易做错的地方）

**方式 A：会话内驱动（第 1–2 周）**

一个常驻 `dsh web` + 一个夜班会话，用 schedule 触发 + goal 自动续行：

```
schedule_create({
  title: "夜班启动",
  cron: { expression: "30 22 * * 1-5", time_zone: "Asia/Shanghai" },
  prompt: "读 docs/agents/queue.md 的 ready 列表。逐个 spec 执行 L3→L5。每个任务结束写 docs/agents/journal/<id>.md。全部结束后生成夜报。遇到 blocked 立即记录并跳到下一个。"
})
```

- 优点：简单，上下文连续，人能随时接管
- 缺点：一个会话串行；长会话会压缩，指令会"变稀"；没有硬预算
- 适合：验证流程、先把链路跑通

**方式 B：会话外驱动（第 3 周起，目标形态）**

外部编排器（PowerShell 或 Node）当"决定论的大脑"，每个任务一个全新 headless 进程：

```powershell
foreach ($spec in Get-ReadySpecs -Max 6) {
  $log = "logs/$($spec.id).jsonl"
  dsh --profile headless --json "按 docs/agents/specs/$($spec.id).md 实现，留下 evidence.json；不要合并" |
    Tee-Object $log
  if ($LASTEXITCODE -ne 0) { Set-Status $spec blocked; continue }

  $verdicts = Invoke-Verifiers $spec      # N 个独立 headless 会话
  if (-not (All-Pass $verdicts)) { Set-Status $spec needs_fix; continue }

  if (Test-MergePolicy $spec $verdicts) { Merge-PR $spec } else { Draft-PR $spec }
}
```

- 优点：每任务全新上下文（不漂移）、可并发（每任务一个 worktree）、崩溃可续、成本可封顶、审计完整、模型只"填内容"
- 缺点：要写编排器；跨任务没有共享记忆（所以一切必须落盘）
- 这对应 poteto 的"把机械部分交给 CLI，判断留给模型"

**建议**：A 跑通 → B 上线 → B 稳定后再加并发。不要一上来就 B+并发 8。

### 10.3 跨任务的"记忆"

无状态编排的最大风险是"第二天什么都不记得"。所以三样东西必须落盘：

- `docs/agents/journal/<id>.md`：这次做了什么、卡在哪、留给下一个人什么
- `docs/agents/backlog/*.md`：待办和状态
- `docs/agents/incidents/*.md`：事故与规则

**磁盘是唯一的长期记忆**，会话不是。

---

## 11. 具体配置（Windows / dsh 0.2.x）

### 11.1 目录放进目标仓库

```
<repo>/
  AGENTS.md                     # 宪法（根）
  .dsh/skills/                  # rank 100，项目级 skill
    goal-scout/SKILL.md
    spec-writer/SKILL.md
    build-tdd/SKILL.md
    verify-game/SKILL.md        # 换成你产品的验证技能
    verify-diff/SKILL.md
    harden/SKILL.md
  docs/agents/                  # 不用 .agents/：那里留给 worktree，避免撞车
    policy.yml                  # 风险分级、路径保护、预算
    queue.md                    # 今晚跑什么
    backlog/  specs/  journal/  incidents/  nightly/  templates/
  scripts/                      # 厚脚本：scout / spec_lint / verify / night-shift
  packages/*/AGENTS.md          # 子目录追加约束（monorepo）
```

`AGENTS.md` 的加载顺序是"从宽到窄"，最具体的最后加载、优先级最高，且预算不足时**宽泛的先被丢**。所以：根 AGENTS.md 只放全局硬规则，模块特有的规则放模块目录。

### 11.2 插件清单（web profile）

```yaml
# $DSH_HOME/profiles/web/cordis.patch.yml（示意，按需增删）
- insert:
    - id: optional-ralph          # 长任务、防上下文腐化
      name: cordis:group
      group: true
      config:
        - id: tool-ralph
          name: '@deepseek-ai/dsh-tool-ralph'
          config: { subagentProvider: spawn, maxRounds: 64 }

    - id: tool-worktree           # 每任务隔离
      name: '@deepseek-ai/dsh-experimental-tool-worktree'

    - id: auto-review             # 可选：无人值守安全网
      name: '@deepseek-ai/dsh-experimental-auto-review'
```

安装用 `dsh plugin --profile web add <包名>`，或用 GUI 的插件页。

### 11.3 权限：为什么不是 `ask`

| 策略 | 行为 | 适不适合无人值守 |
|---|---|---|
| `ask` | 每个敏感操作等人 | ❌ 半夜没人，会一直挂着 |
| `never` | **确定性拒绝**，不弹窗 | ✅ 但要配合 `danger-full-access` 或明确的沙箱，否则会 fail-closed 卡住 |

正确组合：`sandbox = danger-full-access`（或受限的 workspace-write）+ `approval = never`，**安全交给插件闸门和 token 权限**，而不是交给审批提示。

当前会话就是 `never` + `danger-full-access`：不会弹窗，但也意味着 agent 真能删库。所以 §8.2 的硬边界（无 merge 权限的 token、STOP 文件、protected paths）不是可选项。

### 11.4 急停

```powershell
New-Item docs/agents/STOP -ItemType File   # 所有 agent 下一步就该停
Remove-Item docs/agents/STOP               # 恢复
```

三个地方都要检查它：AGENTS.md（模型自觉）、`request_merge`（硬闸）、编排器（启动前）。

### 11.5 预算

| 项 | 建议初值 | 超了怎么办 |
|---|---|---|
| 单任务墙钟 | 45 分钟 | 停，写 blocked |
| 单任务 token | 记录基线，超 3× 告警 | 降级为 draft |
| 单 PR diff | 400 行 / 12 文件 | 拆 spec |
| 每夜合并数 | 20 | 停，等晨间 |
| 每夜并发 | 2 | 靠编排器信号量 |
| 验证者数 | 2（T2 时 3） | 按风险调 |

### 11.6 headless 的凭据

headless 不读 GUI 保存的凭据，按顺序用：启动环境变量 → `<cwd>/.env` → `$DSH_HOME/.env`。夜间任务请确认 API key 在这三处之一，否则会在 23:00 静默失败。

---

## 12. 信任阶梯

| 等级 | agent 能做什么 | 人做什么 | 升级条件 | 降级触发 |
|---|---|---|---|---|
| **L0 只读** | 扫描、写 backlog | 看报告 | 连续 5 天 backlog 有可用项 | — |
| **L1 提案** | 写 spec，不写码 | 审 spec | spec 一次通过率 > 70% | 连续 3 份不可用 |
| **L2 写码** | 写码 + 开 draft PR | 合并 | 连续 20 个 PR 无返工 | 返工率 > 20% |
| **L3 低风险自动合并** | T0/T1 自动合并 | 次日抽样 | 4 周 revert < 2% | 一次 revert 即回 L2 观察一周 |
| **L4 并行 + T2** | 2 路并行，T2 自动 | 抽样 3 个/天 | escaped defect < 1/周 | 一次 SEV 回 L3 |
| **L5 夜间全流程** | 无人值守全链路 | 15 分钟晨间 | L4 稳定 4 周 | 任何 T3 误触即回 L3 |

**升级靠数据，降级靠事件。** 降级不需要讨论，触发即执行。

---

## 13. 30 天落地路线

| 周 | 目标 | 产出 | 验收 | 别做什么 |
|---|---|---|---|---|
| **W1** | 把"验证"做出来 | 1 个 app 的验证技能 + 真跑过 3 次 | 能一条命令启动、操作、截图、退出 | 别碰自动合并 |
| **W2** | 侦察 + 规格 | scout 脚本、20 条 backlog、5 份 spec | 3 份 spec 一次过 G1 | 别让 agent 写码 |
| **W3** | 写码不合并 | worktree + evidence + 3 个真实 PR | 人合并 10 个 PR，返工 ≤ 2 | 别开夜间 |
| **W4** | 夜间低风险 | 编排器 + 夜报 + T0/T1 自动合并 | 一夜 5 个 T1 合并，0 revert | 别碰 T2/T3 |
| **M2** | 并行 + 回灌 | 2 路并行、incident 流程、lint 规则 ×5 | 每周 30+ PR，revert < 2% | 别扩 T3 |
| **M3** | 放大 | 4 路并行、T2 自动、晨间 15 分钟稳定 | 每周 80–150 PR | 别停掉晨间抽样 |

**W1 是最重要的一周。** 没有验证技能，后面全部不成立——这是 poteto 反复强调的那一句。

---

## 14. 指标

| 指标 | 定义 | 目标 | 用来决定 |
|---|---|---|---|
| merged / week | 合并 PR 数（分 T0–T3） | 逐月上升 | 吞吐 |
| revert rate | revert 数 / 合并数 | < 2% | 能否升级 |
| escaped defect | 上线后发现的问题 / 周 | < 1 | 能否升级 |
| CI 一次通过率 | 首次推送即绿 | > 85% | 环境质量 |
| 验证捕获率 | 验证者拦下的真问题 / 总真问题 | 记录并上升 | 验证是否有效 |
| 人工分钟 / PR | 抽样 + 介入时间 | < 3 min | ROI |
| 成本 / 合并 PR | token + 机器时间 | 记录 | 预算 |
| backlog 年龄 | ready 项的中位年龄 | < 14 天 | 缓冲是否健康 |
| blocked 率 | 夜间任务阻塞占比 | < 20% | 规格质量 |

只看两个数会骗你：PR 数和 revert 率要一起看。只涨 PR 不降 revert，说明你在制造债务。

---

## 15. 失败模式（含 dsh 特有坑）

| # | 症状 | 原因 | 对策 |
|---|---|---|---|
| 1 | 半夜全卡住，早上没有任何输出 | `approval=never` 把需要审批的调用确定性拒绝了 | 用 danger-full-access + 插件闸门；把需要审批的操作从流程里去掉 |
| 2 | agent 说"完成了"，但功能是坏的 | goal/ralph 的完成是**自述**，dsh 没有评估器 | 验证者进程隔离 + 确定性闸门；永远不信自述 |
| 3 | 长会话后 agent 开始胡说 | 上下文压缩，早期约束变稀 | 关键约束放 AGENTS.md（每次请求都在）；长任务用 ralph/headless 换新上下文 |
| 4 | skill 加了但模型不用 | frontmatter 错一个字段 → 整个 skill 静默消失；或描述太抽象 | 用 `dsh` 会话里确认 skill 出现在目录；描述写"什么时候用" |
| 5 | 并行任务互相踩文件 | agent-team 共享 checkout；worktree 只切当前会话 | 每任务独立会话 + 独立 worktree；用 `touches` 做写域不相交 |
| 6 | 定时任务没触发 | schedule 只能挂 Web profile；headless 挂不了；进程没起 | 常驻 `dsh web`，或用外部 Task Scheduler 调 headless |
| 7 | resume 之后不自动继续了 | goal 在 resume/fork 后默认关闭续行，这是安全设计 | 明确 `update_goal action=resume` 重新授权 |
| 8 | 早上发现 agent 改了 CI 配置 | 模型有 shell 权限 | protected paths + 双 token + pre-execute 拦截 |
| 9 | 成本爆炸 | 验证者数量 × 任务数 × 重试 | 并发上限、每夜合并上限、token 告警 |
| 10 | 验证者放过了明显 bug | 给了它实现者的解释（被锚定） | 只给验收标准 + diff；多验证者不同角度 |
| 11 | backlog 越积越多没人做 | 只扫不排序，或 ready 定义太松 | 每周 gardener 聚类；G0 严格 |
| 12 | 规则越加越多但错误照旧 | 往 AGENTS.md 里堆提醒（最弱的一层） | 阶梯：架构 > 类型 > lint > 测试 > 文档；每条规则要能挡住历史错误 |

---

## 16. 今晚就能做的三件事

1. **给一个 app 写验证技能，并且真跑一次。** 启动命令、就绪判断、三个真实操作、截图存哪、怎么清理。跑不通就不算交付物。
2. **翻你和 agent 的对话记录，找被纠正 ≥ 2 次的地方**，挑一条做成 lint 规则或类型约束。这是投入产出比最高的动作。
3. **建 backlog，让侦察跑一晚，只记录不修。** 明早看那堆条目——你会第一次看清"重复的根因"长什么样。

三件事做完，你已经有了 L0 + L1 的一半。剩下的都是工程，不是魔法。

**配套的 starter kit 在 [`docs/dsh/`](README.md)**：仓库宪法模板、可直接复制的 SKILL.md、spec/夜报/策略模板、夜班编排脚本、合并闸门插件骨架。按 `docs/dsh/README.md` 的安装步骤复制进目标仓库即可；本仓库本身就是第一个装好的样本。

---

## 17. 资料与事实核对

**视频**
- YouTube：<https://www.youtube.com/watch?v=MN9dGgmLyso>
- B 站转载：<https://www.bilibili.com/video/BV1AjH66gETc>
- 访谈时间：2026-10-02（Matt Pocock 直播），约 67 分钟

**二手整理（本文事实主要来源）**
- 日文逐章摘要（11 章）：<https://zenn.dev/yukkie1114/articles/poteto-pstack-2500-prs>
- 中文事实核查 + 闸门表：<https://tenten.co/learning/pstack-verification-agent-merge/>

**数字口径**
- 2,500：2026-09-21 演讲标题；2,462：The Neuron 引 8 月结算；"两千上下"：访谈原话。均为本人自报。
- pstack 0.15.9（2026-10-05）：26 个工作流技能、24 条原则、23 份剧本、2 个子代理。其他平台移植版数量不同。
- 成本对照：同一项目不用 pstack 约 30 分钟，用约 1 小时，多抓到 3 个 agent 自己编的结论（The Neuron 引 Rob O'Shaughnessy）。

**dsh 事实来源**
- 本机安装：`@deepseek-ai/dsh@0.2.1-rc.2`
- 依据的包文档：`dsh-skill-filesystem`、`dsh-agent-instructions`、`dsh-goal-round-driver`、`dsh-tool-ralph`、`dsh-schedule`、`dsh-headless`、`dsh-experimental-worktree`、`dsh-experimental-agent-team`、`dsh-user-approval`、`dsh-permission-presets`、`dsh-experimental-auto-review`
- 文中所有"限制"均来自这些包的 README，不是推测
