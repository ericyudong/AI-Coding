# Stop E-Claw services script

Write-Host "Stopping E-Claw backend on port 8000..."
try {
    $connections = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
    foreach ($conn in $connections) {
        $pid = $conn.OwningProcess
        if ($pid) {
            Write-Host "Killing process $pid"
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        }
    }
} catch {
    Write-Host "No process on port 8000 found"
}

Write-Host "Stopping E-Claw frontend on port 5173..."
try {
    $connections = Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue
    foreach ($conn in $connections) {
        $pid = $conn.OwningProcess
        if ($pid) {
            Write-Host "Killing process $pid"
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        }
    }
} catch {
    Write-Host "No process on port 5173 found"
}

Start-Sleep -Seconds 3

Write-Host "Starting E-Claw backend..."
$backendDir = Join-Path $PSScriptRoot "AI-Coding\e-claw\backend"
Set-Location $backendDir
Start-Process cmd -ArgumentList "/c run.bat" -WindowStyle Normal

Start-Sleep -Seconds 5

Write-Host "Starting E-Claw frontend..."
$frontendDir = Join-Path $PSScriptRoot "AI-Coding\e-claw\frontend"
Set-Location $frontendDir
Start-Process cmd -ArgumentList "/c npm run dev" -WindowStyle Normal

Write-Host "E-Claw services restarted!"
