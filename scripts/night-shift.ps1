#requires -Version 5.1
<#
夜班编排器（骨架）

设计原则：循环由脚本拥有，模型只负责"填内容"。
  - 选任务：确定性（读 queue.md）
  - 实现：每个任务一个全新 headless 进程（上下文不漂移）
  - 验证：独立进程，不给实现者的解释
  - 合并：脚本判定，默认完全关闭（-AutoMergeTiers 才开）

用法：
  pwsh ./orchestrator/night-shift.ps1 -DryRun
  pwsh ./orchestrator/night-shift.ps1 -MaxTasks 3
  pwsh ./orchestrator/night-shift.ps1 -MaxTasks 3 -AutoMergeTiers T0,T1

前置：
  - dsh 在 PATH；headless profile 已初始化
  - API key 在环境变量、仓库 .env 或 $DSH_HOME/.env
  - gh 已登录；给 builder 的 token 不要带 merge 权限
#>
[CmdletBinding()]
param(
  [string]$Repo = (Get-Location).Path,
  [int]$MaxTasks = 5,
  [switch]$DryRun,
  [string]$DshProfile = 'headless',
  [string[]]$AutoMergeTiers = @()
)

$ErrorActionPreference = 'Stop'
Set-Location $Repo

$QueueFile  = 'docs/agents/queue.md'
$StopFile   = 'docs/agents/STOP'
$LogDir     = 'logs'
$ReportPath = "docs/agents/nightly/$(Get-Date -Format 'yyyy-MM-dd').md"

foreach ($d in @($LogDir, 'docs/agents/nightly', 'docs/agents/journal', 'artifacts/verdict')) {
  New-Item -ItemType Directory -Force $d | Out-Null
}

$result = [ordered]@{
  started    = (Get-Date)
  merged     = [System.Collections.Generic.List[object]]::new()
  needsHuman = [System.Collections.Generic.List[object]]::new()
  blocked    = [System.Collections.Generic.List[object]]::new()
  failed     = [System.Collections.Generic.List[object]]::new()
  skipped    = [System.Collections.Generic.List[string]]::new()
}

function Log($msg, $color = 'Cyan') { Write-Host "[night] $msg" -ForegroundColor $color }
function StopRequested { Test-Path $StopFile }

function Get-ReadySpecs {
  if (-not (Test-Path $QueueFile)) { throw "missing $QueueFile" }
  # 队列格式：每行 `- [ ] sp-20261018-003`（[x] 表示已完成，跳过）
  Get-Content $QueueFile | ForEach-Object {
    if ($_ -match '^\s*-\s*\[\s\]\s*(sp-[\w-]+)') { $Matches[1] }
  }
}

function Invoke-Dsh([string]$task, [string]$logPath) {
  if ($DryRun) {
    Log "(dry) dsh << $($task.Substring(0, [Math]::Min(50, $task.Length)))..."
    return 0
  }
  # --json 交给 app 解析；--profile 必须在它之前（启动器只认自己的 flag）
  & dsh --profile $DshProfile --json $task 2>&1 | Tee-Object -FilePath $logPath | Out-Host
  return $LASTEXITCODE
}

function Get-SpecMeta([string]$specId) {
  $p = "docs/agents/specs/$specId.md"
  if (-not (Test-Path $p)) { return $null }
  $raw = Get-Content $p -Raw
  $tier = if ($raw -match '(?m)^risk_tier:\s*(T[0-3])') { $Matches[1] } else { 'T3' }
  [pscustomobject]@{ Id = $specId; Path = $p; Tier = $tier }
}

function Enter-Worktree([string]$specId) {
  $wt = ".agents/worktrees/$specId"
  if ($DryRun) { return $wt }
  if (Test-Path $wt) { Log "worktree exists: $wt"; return $wt }
  & git worktree add $wt -b $specId origin/main 2>&1 | Out-Host
  if ($LASTEXITCODE -ne 0) { throw "worktree create failed: $specId" }
  return $wt
}

function Invoke-Verifiers([string]$specId, [int]$count) {
  $list = [System.Collections.Generic.List[object]]::new()
  $roles = @('verify-diff', 'verify-behavior', 'verify-diff')
  for ($i = 0; $i -lt $count; $i++) {
    $role = $roles[$i % $roles.Count]
    $out  = "artifacts/verdict/$specId/$role-$i.json"
    $task = @"
你是独立验证者。使用 skill $role。
只依据 docs/agents/specs/$specId.md 的验收标准和 git diff origin/main...HEAD。
不要读 PR 描述，不要读实现者的任何说明，不要修改任何源码。
把结构化结论写入 $out。
"@
    $code = Invoke-Dsh $task "logs/$specId-$role-$i.jsonl"
    if ($DryRun) { $list.Add([pscustomobject]@{ Role = $role; Pass = $true; File = $out }); continue }
    if ($code -ne 0) { $list.Add([pscustomobject]@{ Role = $role; Pass = $false; File = $out; Error = "exit $code" }); continue }
    if (-not (Test-Path $out)) { $list.Add([pscustomobject]@{ Role = $role; Pass = $false; File = $out; Error = 'no verdict' }); continue }
    try {
      $v = Get-Content $out -Raw | ConvertFrom-Json
      $list.Add([pscustomobject]@{ Role = $role; Pass = ($v.verdict -eq 'pass'); File = $out })
    } catch {
      $list.Add([pscustomobject]@{ Role = $role; Pass = $false; File = $out; Error = 'invalid json' })
    }
  }
  return $list
}

$HasGh = [bool](Get-Command gh -ErrorAction SilentlyContinue)
if (-not $HasGh) {
  Log "gh CLI 未安装：跳过 PR 查找与自动合并（分支、证据、夜报照常产出）" 'Yellow'
}

# ---------------- 主循环 ----------------
$specs = @(Get-ReadySpecs | Select-Object -First $MaxTasks)
Log "ready specs: $($specs.Count); auto-merge tiers: [$($AutoMergeTiers -join ',')]"

foreach ($specId in $specs) {
  if (StopRequested) { Log "STOP file present; halting" 'Red'; break }

  $meta = Get-SpecMeta $specId
  if (-not $meta) { $result.skipped.Add($specId); Log "skip (no spec): $specId" 'Yellow'; continue }

  Log "=== $specId ($($meta.Tier)) ==="
  $wt = Enter-Worktree $specId

  Push-Location $wt
  New-Item -ItemType Directory -Force $LogDir, 'artifacts/evidence', "artifacts/verdict/$specId" | Out-Null
  try {
    # 1) 实现
    $buildTask = @"
按 docs/agents/specs/$specId.md 实现。使用 skill build-tdd。
只改 spec 中 touches 列出的路径。写完 evidence.json、推送分支，然后停止。
本机没有 gh，不要尝试创建 PR。不要合并。不要读 backlog 的其他条目。
"@
    $code = Invoke-Dsh $buildTask "logs/$specId-build.jsonl"
    if ($code -ne 0) {
      $result.blocked.Add([pscustomobject]@{ Spec = $specId; Reason = "build exit $code" })
      Log "blocked: $specId (build exit $code)" 'Yellow'
      continue
    }

    # 2) 验证（独立进程）
    $verdicts = Invoke-Verifiers $specId 2
    $allPass  = (@($verdicts | Where-Object { -not $_.Pass }).Count -eq 0)

    # 3) 找到 PR（没有 gh 就跳过）
    $pr = 0
    if (-not $DryRun -and $HasGh) {
      $prText = & gh pr list --head $specId --json number --jq '.[0].number' 2>$null
      if ($prText) { $pr = [int]$prText }
    }

    # 4) 合并判定
    $canMerge = $allPass -and ($meta.Tier -in $AutoMergeTiers) -and ($pr -gt 0)
    if ($canMerge) {
      Log "merging #$pr ($($meta.Tier))" 'Green'
      if (-not $DryRun) {
        & gh pr merge $pr --squash --delete-branch 2>&1 | Out-Host
        if ($LASTEXITCODE -eq 0) {
          $result.merged.Add([pscustomobject]@{ Spec = $specId; PR = $pr; Tier = $meta.Tier })
        } else {
          $result.failed.Add([pscustomobject]@{ Spec = $specId; Reason = 'merge failed' })
        }
      } else {
        $result.merged.Add([pscustomobject]@{ Spec = $specId; PR = 0; Tier = $meta.Tier })
      }
    }
    else {
      if (-not $DryRun -and $pr -gt 0) { & gh pr edit $pr --add-label 'needs-human' 2>&1 | Out-Null }
      $reason = if (-not $allPass) { 'verdict fail' }
                elseif ($meta.Tier -notin $AutoMergeTiers) { "tier $($meta.Tier) not allowed" }
                else { 'no pr' }
      $result.needsHuman.Add([pscustomobject]@{ Spec = $specId; PR = $pr; Reason = $reason })
      Log "needs human: $specId ($reason)" 'Yellow'
    }
  }
  catch {
    $result.failed.Add([pscustomobject]@{ Spec = $specId; Reason = $_.Exception.Message })
    Log "failed: $specId — $($_.Exception.Message)" 'Red'
  }
  finally { Pop-Location }
}

# ---------------- 夜报 ----------------
$dur = (Get-Date) - $result.started
$mergedLines = ($result.merged   | ForEach-Object { "- #$($_.PR)  $($_.Spec)  $($_.Tier)" }) -join "`n"
$humanLines  = ($result.needsHuman | ForEach-Object { "- $($_.Spec)  #$($_.PR)  $($_.Reason)" }) -join "`n"
$blockedLines= ($result.blocked  | ForEach-Object { "- $($_.Spec)  $($_.Reason)" }) -join "`n"
$failedLines = ($result.failed   | ForEach-Object { "- $($_.Spec)  $($_.Reason)" }) -join "`n"

$md = @"
# 夜报 $(Get-Date -Format 'yyyy-MM-dd')

- 合并：$($result.merged.Count)
- 待人工：$($result.needsHuman.Count)
- 阻塞：$($result.blocked.Count)
- 失败：$($result.failed.Count)
- 跳过：$($result.skipped.Count)
- 耗时：$([int]$dur.TotalMinutes) 分钟

## 合并
$mergedLines

## 待人工
$humanLines

## 阻塞
$blockedLines

## 失败
$failedLines

## 晨间建议
1. 抽最大 diff / T2 / 验证最薄的 3 个 PR
2. 把出现 >= 2 次的错误变成规则（skills/harden）
3. 更新 docs/agents/queue.md
"@

if ($DryRun) {
  Write-Host $md
} else {
  $md | Out-File $ReportPath -Encoding utf8
  Log "report: $ReportPath" 'Green'
}

if ($result.failed.Count -gt 0) { exit 1 } else { exit 0 }
