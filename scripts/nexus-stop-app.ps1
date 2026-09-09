$workspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

$processes = Get-CimInstance Win32_Process | Where-Object {
    $commandLine = $_.CommandLine
    $commandLine -and
    $commandLine.IndexOf($workspaceRoot, [System.StringComparison]::OrdinalIgnoreCase) -ge 0 -and
    (
        $commandLine.IndexOf("nexus_backend.app:app", [System.StringComparison]::OrdinalIgnoreCase) -ge 0 -or
        $commandLine.IndexOf("vite", [System.StringComparison]::OrdinalIgnoreCase) -ge 0
    )
}

if (-not $processes) {
    Write-Host "[NeXus] No running backend or frontend process was found."
    exit 0
}

foreach ($process in $processes | Sort-Object ProcessId -Descending) {
    Write-Host "[NeXus] Stopping $($process.Name) (PID $($process.ProcessId))..."
    & taskkill.exe /PID $process.ProcessId /T /F 2>$null | Out-Null
}

Write-Host "[SUCCESS] NeXus backend and frontend were stopped."
