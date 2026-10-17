---
name: verify-behavior
description: 启动应用、像真实用户一样操作、留下证据、干净退出；用行为验证验收标准而不是读代码猜。
whenToUse: 需要判断"这个改动在真实界面上到底对不对"时；每个 spec 的验证环节必用。
---

# verify-behavior

> 这是整套流程里最重要的技能。没有它，人永远是 agent 和真实世界之间的"肉体中转"。
>
> **只写这个技能不算交付——真跑通过一次才算。**

## 六段结构（缺一段就不合格）

### 1. 启动

- 命令：`<启动命令>`（照抄 `AGENTS.md` 第 0 节，不要自己发明）
- 就绪判断：不能只 `sleep 10`。用可观察条件：
  - HTTP 200：`curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/health`
  - 或端口监听 + 日志出现 `ready in`
- 超时：60 秒；超时 → 判失败，收集日志尾部，不要无限等

### 2. 健检（只读）

在操作前先回答："这个实例值得我操作吗？"

- 版本/commit 是否正确：界面上或 `/version` 显示 `<期望 sha 前 7 位>`
- 有没有挡路的弹窗/引导/登录墙
- 数据是否是可预期的种子数据

健检不过 → 先修环境或换数据，不要在脏环境上验证。

### 3. 操作

- 用**真实路径**：真实选择器、真实 URL、真实键盘操作。不要调内部函数，不要用测试专用后门。
- 每条验收标准对应一段操作，写成可重放的脚本。
- 失败时保存现场：截图 + DOM 快照 + 控制台日志 + 网络失败请求。

### 4. 证据

- 存到 `artifacts/verify/<spec-id>/`
- 每张截图/视频的文件名要能对上验收标准：`ac1-empty-export.png`
- 断言结果写成 JSON，别只写"看起来正常"：

```json
{
  "spec": "sp-20261018-003",
  "commit": "<sha>",
  "criteria": [
    { "id": "ac1", "pass": true,  "evidence": "artifacts/verify/sp-003/ac1-empty-export.png" },
    { "id": "ac2", "pass": false, "evidence": "...", "observed": "下载文件 0 字节" }
  ]
}
```

### 5. 清理

- 只关自己开的东西（自己启动的进程、自己创建的浏览器上下文、自己写的临时文件）
- **不要删证据**
- 不要 `taskkill /IM node.exe` 这种地图炮

### 6. 辅助脚本

把这个仓库的验证动作固化成 `scripts/verify.ps1`，所有 agent 共用：

```powershell
# scripts/verify.ps1 —— 骨架，按仓库填 3 处
param([string]$SpecId, [switch]$KeepOpen)

$ErrorActionPreference = 'Stop'
$out = "artifacts/verify/$SpecId"
New-Item -ItemType Directory -Force $out | Out-Null

# 1) 启动
$p = Start-Process -PassThru -FilePath "pnpm" -ArgumentList "dev"
try {
  # 2) 就绪
  $ok = $false
  foreach ($i in 1..60) {
    try {
      if ((Invoke-WebRequest "http://localhost:3000/health" -UseBasicParsing).StatusCode -eq 200) { $ok = $true; break }
    } catch { Start-Sleep -Seconds 1 }
  }
  if (-not $ok) { throw "app not ready in 60s" }

  # 3) 操作 —— 用 playwright CLI 或仓库已有 e2e helper
  #    pnpm exec playwright test tests/e2e/<场景>.spec.ts --project=chromium
  #    截图输出到 $out

  # 4) 证据 —— 上面那一步的截图 + JSON
}
finally {
  # 5) 清理：只关自己启的
  if (-not $KeepOpen) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
}
```

**脚本优先于临场发挥**：同一个检查每次用同样方式跑，结果才可比。这也是 poteto 说的"把机械部分从判断里拿掉"。

## 判断规则

| 情况 | 结论 |
|---|---|
| 应用起不来 | `blocked`（环境问题），不是"验证失败" |
| 健检不过 | 先修环境；修不了 → `blocked` |
| 某条标准无法自动判定 | 标 `manual`，交给人；该 PR 不允许自动合并 |
| 行为对但代码丑 | 通过（丑不归验证管，归 review 管） |
| 行为对但越界改动 | 不通过（归 verify-diff 管） |

## 禁止

- 只读代码就断言"行为正确"
- 用单元测试代替行为验证（单测过了但页面白屏，很常见）
- 验证失败后自己改代码（验证者只读）
- 删掉不通过的截图

## 完成标准

- [ ] `scripts/verify.ps1` 能从零跑通
- [ ] 每条验收标准都有 pass/fail + 证据路径
- [ ] 证据文件真实存在且能打开
- [ ] 进程已清理，证据未删
