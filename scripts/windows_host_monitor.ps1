param(
    [Parameter(Mandatory=$true)][string]$SnapshotFile,
    [Parameter(Mandatory=$true)][string]$StopFile,
    [Parameter(Mandatory=$true)][string]$HistoryFile
)
$ErrorActionPreference = 'Stop'
$taskDirectory = Split-Path -Parent $SnapshotFile
New-Item -ItemType Directory -Force -Path $taskDirectory | Out-Null
$taskLogicalProcessors = [int](Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class TailCachePowerScheme {
    [DllImport("powrprof.dll")] private static extern uint PowerGetActiveScheme(IntPtr key, out IntPtr guid);
    [DllImport("kernel32.dll")] private static extern IntPtr LocalFree(IntPtr value);
    public static string Read() {
        IntPtr pointer;
        if (PowerGetActiveScheme(IntPtr.Zero, out pointer) != 0 || pointer == IntPtr.Zero)
            throw new InvalidOperationException("Windows power scheme unavailable");
        try { return Marshal.PtrToStructure<Guid>(pointer).ToString(); }
        finally { LocalFree(pointer); }
    }
}
'@
$taskAvailable = [Diagnostics.PerformanceCounter]::new('Memory', 'Available MBytes', $true)
$taskCommit = [Diagnostics.PerformanceCounter]::new('Memory', '% Committed Bytes In Use', $true)
$taskPageReads = [Diagnostics.PerformanceCounter]::new('Memory', 'Page Reads/sec', $true)
$taskPagesOut = [Diagnostics.PerformanceCounter]::new('Memory', 'Pages Output/sec', $true)
$taskRootCategory = if ([Diagnostics.PerformanceCounterCategory]::Exists('Hyper-V Hypervisor Root Virtual Processor')) {
    'Hyper-V Hypervisor Root Virtual Processor'
} else { 'Processor' }
$taskRootCounter = if ($taskRootCategory -eq 'Processor') { '% Processor Time' } else { '% Total Run Time' }
$taskRootCpu = [Diagnostics.PerformanceCounter]::new($taskRootCategory, $taskRootCounter, '_Total', $true)
$taskPhysicalCpu = $null
if ([Diagnostics.PerformanceCounterCategory]::Exists('Hyper-V Hypervisor Logical Processor')) {
    $taskPhysicalCpu = [Diagnostics.PerformanceCounter]::new('Hyper-V Hypervisor Logical Processor', '% Total Run Time', '_Total', $true)
}
$taskProcessCategory = [Diagnostics.PerformanceCounterCategory]::new('Process')
$taskGuestInstances = @($taskProcessCategory.GetInstanceNames() | Where-Object { $_ -like 'vmmem*' })
if ($taskGuestInstances.Count -eq 0) { throw 'No WSL guest CPU counter found; start Ubuntu first.' }
$taskGuestCounters = @($taskGuestInstances | ForEach-Object {
    [Diagnostics.PerformanceCounter]::new('Process', '% Processor Time', $_, $true)
})
$taskFrequency = $null
$taskPerformance = $null
$taskLimitFlags = $null
if ([Diagnostics.PerformanceCounterCategory]::CounterExists('Actual Frequency', 'Processor Information')) {
    $taskFrequency = [Diagnostics.PerformanceCounter]::new('Processor Information', 'Actual Frequency', '_Total', $true)
    $taskPerformance = [Diagnostics.PerformanceCounter]::new('Processor Information', '% Processor Performance', '_Total', $true)
    $taskLimitFlags = [Diagnostics.PerformanceCounter]::new('Processor Information', 'Performance Limit Flags', '_Total', $true)
    $taskPerformance.NextValue() | Out-Null
}
$taskRootCpu.NextValue() | Out-Null
if ($null -ne $taskPhysicalCpu) { $taskPhysicalCpu.NextValue() | Out-Null }
$taskGuestCounters | ForEach-Object { $_.NextValue() | Out-Null }
$taskSampleClock = [Diagnostics.Stopwatch]::StartNew()
$taskLastClockMs = $taskSampleClock.Elapsed.TotalMilliseconds
Start-Sleep -Seconds 1
$taskUtf8 = [System.Text.UTF8Encoding]::new($false)
$taskTemporary = $SnapshotFile + '.next'
while (-not (Test-Path -LiteralPath $StopFile)) {
    # The root-partition counter is already host-only; do not subtract guest time.
    $taskOutsideGuest = [double]$taskRootCpu.NextValue()
    $taskCpuPercent = if ($null -ne $taskPhysicalCpu) { [double]$taskPhysicalCpu.NextValue() } else { -1.0 }
    $taskGuestPercent = ($taskGuestCounters | ForEach-Object { $_.NextValue() } | Measure-Object -Sum).Sum / $taskLogicalProcessors
    $taskClockMs = $taskSampleClock.Elapsed.TotalMilliseconds
    $taskIntervalMs = $taskClockMs - $taskLastClockMs
    $taskLastClockMs = $taskClockMs
    $taskRow = [ordered]@{
        timestampUnixMs = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
        monitorVersion = 5
        intervalMs = $taskIntervalMs
        availableMiB = [double]$taskAvailable.NextValue()
        commitPercent = [double]$taskCommit.NextValue()
        totalCpuPercent = $taskCpuPercent
        guestCpuPercent = [double]$taskGuestPercent
        outsideGuestCpuPercent = [double]$taskOutsideGuest
        outsideCpuCounter = $taskRootCategory + '(_Total) ' + $taskRootCounter
        actualFrequencyMHz = $(if ($null -ne $taskFrequency) { [double]$taskFrequency.NextValue() } else { -1.0 })
        processorPerformancePercent = $(if ($null -ne $taskPerformance) { [double]$taskPerformance.NextValue() } else { -1.0 })
        performanceLimitFlags = $(if ($null -ne $taskLimitFlags) { [double]$taskLimitFlags.NextValue() } else { -1.0 })
        powerScheme = [TailCachePowerScheme]::Read()
        pageReadsPerSecond = [double]$taskPageReads.NextValue()
        pagesOutputPerSecond = [double]$taskPagesOut.NextValue()
    }
    $taskJson = $taskRow | ConvertTo-Json -Compress
    # History is authoritative. A reader holding the optional snapshot must not
    # interrupt fresh samples. Other I/O failures still stop this observer.
    [System.IO.File]::AppendAllText($HistoryFile, ($taskJson + "`n"), $taskUtf8)
    [System.IO.File]::WriteAllText($taskTemporary, $taskJson, $taskUtf8)
    try {
        if (Test-Path -LiteralPath $SnapshotFile) {
            [System.IO.File]::Replace($taskTemporary, $SnapshotFile,
                [System.Management.Automation.Language.NullString]::Value)
        } else {
            [System.IO.File]::Move($taskTemporary, $SnapshotFile)
        }
    } catch {
        $taskPublishError = $_.Exception
        while ($null -ne $taskPublishError.InnerException) { $taskPublishError = $taskPublishError.InnerException }
        $taskNativeError = $taskPublishError.HResult -band 0xffff
        if ($taskPublishError -is [System.IO.IOException] -and $taskNativeError -in @(32, 33)) {
            Write-Warning 'Snapshot publication skipped because a reader holds it; authoritative history is current.'
        } else { throw }
    }
    Start-Sleep -Seconds 1
}
@($taskAvailable, $taskCommit, $taskPageReads, $taskPagesOut, $taskRootCpu, $taskPhysicalCpu,
    $taskFrequency, $taskPerformance, $taskLimitFlags) + $taskGuestCounters |
    Where-Object { $null -ne $_ } | ForEach-Object { $_.Dispose() }
