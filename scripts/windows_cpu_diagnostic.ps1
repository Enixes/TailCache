param(
    [Parameter(Mandatory=$true)][string]$OutputFile,
    [Parameter(Mandatory=$true)][string]$SnapshotFile,
    [int]$Seconds = 85
)
# Diagnostic attribution only. This is never a primary latency measurement.
$ErrorActionPreference = 'Stop'
$taskUtf8 = [Text.UTF8Encoding]::new($false)
$taskLogical = [int](Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors
$taskCategory = [Diagnostics.PerformanceCounterCategory]::new('Process')
$taskPrevious = $taskCategory.ReadCategory()
$taskClock = [Diagnostics.Stopwatch]::StartNew()
while ($taskClock.Elapsed.TotalSeconds -lt $Seconds) {
    Start-Sleep -Seconds 1
    $taskCurrent = $taskCategory.ReadCategory()
    $taskCpu = $taskCurrent['% Processor Time']
    $taskOldCpu = $taskPrevious['% Processor Time']
    $taskProcesses = foreach ($taskName in $taskCpu.Keys) {
        if ($taskName -match '^(_Total|Idle|vmmem.*)$') { continue }
        if (-not $taskOldCpu.Contains($taskName)) { continue }
        if ($taskCurrent['ID Process'][$taskName].RawValue -ne $taskPrevious['ID Process'][$taskName].RawValue) { continue }
        $taskPercent = [double][Diagnostics.CounterSampleCalculator]::ComputeCounterValue(
            $taskOldCpu[$taskName].Sample, $taskCpu[$taskName].Sample) / $taskLogical
        if ($taskPercent -gt 0) {
            [pscustomobject]@{name=$taskName;processId=$taskCurrent['ID Process'][$taskName].RawValue;cpuPercent=$taskPercent}
        }
    }
    $taskHost = $null
    $taskSnapshotStream = $null
    $taskSnapshotReader = $null
    try {
        $taskSnapshotStream = [IO.FileStream]::new($SnapshotFile, [IO.FileMode]::Open,
            [IO.FileAccess]::Read, ([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))
        $taskSnapshotReader = [IO.StreamReader]::new($taskSnapshotStream)
        $taskHost = $taskSnapshotReader.ReadToEnd() | ConvertFrom-Json
    } catch { } finally {
        if ($null -ne $taskSnapshotReader) { $taskSnapshotReader.Dispose() }
        elseif ($null -ne $taskSnapshotStream) { $taskSnapshotStream.Dispose() }
    }
    $taskRow = [ordered]@{
        timestampUnixMs = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
        host = $taskHost
        topProcesses = @($taskProcesses | Sort-Object cpuPercent -Descending | Select-Object -First 10)
        note = 'Attribution is diagnostic; sampling itself adds Windows work. Guest/idle/total instances excluded.'
    }
    [IO.File]::AppendAllText($OutputFile, (($taskRow | ConvertTo-Json -Depth 5 -Compress) + "`n"), $taskUtf8)
    $taskPrevious = $taskCurrent
}
