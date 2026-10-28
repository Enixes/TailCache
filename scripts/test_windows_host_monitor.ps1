param([Parameter(Mandatory=$true)][string]$OutputDirectory)
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Path $OutputDirectory -ErrorAction Stop | Out-Null
$taskSnapshot = Join-Path $OutputDirectory 'snapshot.json'
$taskHistory = Join-Path $OutputDirectory 'history.jsonl'
$taskStop = Join-Path $OutputDirectory 'stop'
$taskArguments = @('-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File',
    ('"' + (Join-Path $PSScriptRoot 'windows_host_monitor.ps1') + '"'),
    '-SnapshotFile', ('"' + $taskSnapshot + '"'), '-StopFile', ('"' + $taskStop + '"'),
    '-HistoryFile', ('"' + $taskHistory + '"'))
$taskProcess = Start-Process -FilePath "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe" `
    -ArgumentList $taskArguments -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $OutputDirectory 'stdout.log') `
    -RedirectStandardError (Join-Path $OutputDirectory 'stderr.log')
# Keep the native handle while the child runs so Windows PowerShell 5.1 can
# retrieve its exit status even after the short-lived child has disappeared.
$taskProcessHandle = $taskProcess.Handle
$taskLock = $null
try {
    $taskDeadline = [DateTimeOffset]::UtcNow.AddSeconds(15)
    while (-not (Test-Path -LiteralPath $taskSnapshot)) {
        if ($taskProcess.HasExited -or [DateTimeOffset]::UtcNow -gt $taskDeadline) { throw 'Observer did not start.' }
        Start-Sleep -Milliseconds 100
    }
    # Deliberately reproduce the reader that prohibited atomic replacement.
    $taskLock = [IO.FileStream]::new($taskSnapshot, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
    $taskLockedAt = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
    Start-Sleep -Milliseconds 3300
    if ($taskProcess.HasExited) { throw 'Observer died while snapshot was locked.' }
    $taskHistoryStream = [IO.FileStream]::new($taskHistory, [IO.FileMode]::Open, [IO.FileAccess]::Read,
        ([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))
    $taskHistoryReader = [IO.StreamReader]::new($taskHistoryStream)
    try { $taskText = $taskHistoryReader.ReadToEnd() } finally { $taskHistoryReader.Dispose() }
    $taskRecords = @($taskText.Split("`n") | Where-Object { $_.Trim() } | ForEach-Object { $_ | ConvertFrom-Json })
    $taskDuringLock = @($taskRecords | Where-Object { $_.timestampUnixMs -gt $taskLockedAt })
    if ($taskDuringLock.Count -lt 2) { throw 'Authoritative history stopped advancing during lock.' }
    if (@($taskDuringLock | Where-Object { $_.monitorVersion -ne 5 }).Count) { throw 'Wrong observer version.' }
    if ([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() - $taskRecords[-1].timestampUnixMs -gt 2500) { throw 'History became stale.' }
    $taskLock.Dispose()
    $taskLock = $null
    Start-Sleep -Milliseconds 1500
    $taskRecovered = Get-Content -LiteralPath $taskSnapshot -Raw | ConvertFrom-Json
    if ($taskRecovered.timestampUnixMs -le $taskDuringLock[-1].timestampUnixMs) { throw 'Snapshot did not recover after release.' }
    [IO.File]::WriteAllText($taskStop, 'test complete')
    if (-not $taskProcess.WaitForExit(5000) -or $taskProcess.ExitCode -ne 0) {
        throw "Observer failed to stop cleanly (exit=$($taskProcess.ExitCode))."
    }
    $taskResult = [ordered]@{pass=$true;historySamplesDuringSnapshotLock=$taskDuringLock.Count;
        observerVersion=5;historyRemainedFresh=$true;snapshotRecovered=$true;exitCode=$taskProcess.ExitCode}
    [IO.File]::WriteAllText((Join-Path $OutputDirectory 'result.json'), ($taskResult | ConvertTo-Json), [Text.UTF8Encoding]::new($false))
    $taskResult | ConvertTo-Json -Compress
} finally {
    if ($null -ne $taskLock) { $taskLock.Dispose() }
    [IO.File]::WriteAllText($taskStop, 'test complete')
    if (-not $taskProcess.HasExited -and -not $taskProcess.WaitForExit(5000)) {
        Stop-Process -Id $taskProcess.Id -Force
    }
}
