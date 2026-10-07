# ============================================================
#  AUST Attendance System - Setup Script (v2)
# ============================================================
#  Run: Right-click -> Run with PowerShell (as Admin recommended)
# ============================================================

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONUTF8 = "1"
$Host.UI.RawUI.WindowTitle = "AUST Setup"

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectDir

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  AUST Attendance System - Setup" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# -- 1. Install requirements --------------------------------
Write-Host "[1/5] Installing requirements..." -ForegroundColor Yellow
& python -m pip install -r requirements.txt --quiet --disable-pip-version-check 2>&1 | Out-Null
Write-Host "[OK] Requirements installed" -ForegroundColor Green
Write-Host ""

# -- 2. Initialize database --------------------------------
Write-Host "[2/5] Initializing database..." -ForegroundColor Yellow
& python main.py init
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Database init failed" -ForegroundColor Red
    pause; exit 1
}
Write-Host ""

# -- 3. Generate device token + assign hall ----------------
Write-Host "[3/5] Setting up device..." -ForegroundColor Yellow
& python setup_device.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Device setup failed" -ForegroundColor Red
    pause; exit 1
}
Write-Host ""

# -- 4. Open port 5000 in firewall -------------------------
Write-Host "[4/5] Configuring firewall..." -ForegroundColor Yellow
try {
    $ruleCheck = & netsh advfirewall firewall show rule name="AUST Attendance Server" 2>&1
    if ($ruleCheck -match "AUST Attendance Server") {
        Write-Host "[OK] Firewall rule exists" -ForegroundColor Green
    } else {
        $isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
        if ($isAdmin) {
            & netsh advfirewall firewall add rule name="AUST Attendance Server" dir=in action=allow protocol=TCP localport=5000 2>&1 | Out-Null
            Write-Host "[OK] Port 5000 opened" -ForegroundColor Green
        } else {
            Write-Host "[ACTION] Opening firewall (click Yes on UAC prompt)..." -ForegroundColor Yellow
            Start-Process powershell -Verb RunAs -Wait -ArgumentList @(
                '-NoProfile', '-Command',
                'netsh advfirewall firewall add rule name="AUST Attendance Server" dir=in action=allow protocol=TCP localport=5000'
            )
            Write-Host "[OK] Done - verify above says OK" -ForegroundColor Green
        }
    }
} catch {
    Write-Host "[WARN] Firewall: run this script as Admin" -ForegroundColor DarkYellow
}
Write-Host ""

# -- 5. Show computer IP -----------------------------------
Write-Host "[5/5] Network info:" -ForegroundColor Yellow
try {
    $wifiIP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {
        $_.InterfaceAlias -match "Wi-Fi|Ethernet" -and
        $_.IPAddress -notmatch "^(169|127|172|192\.168\.(1[5-9]|2\d|3\d))\."
    } | Select-Object -First 1).IPAddress
} catch { $wifiIP = $null }

if (-not $wifiIP) {
    $wifiIP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {
        $_.InterfaceAlias -notmatch "Loopback|VMware|VirtualBox|vEthernet" -and
        $_.IPAddress -notmatch "^(169|127)\."
    } | Select-Object -First 1).IPAddress
}

if ($wifiIP) {
    Write-Host ""
    Write-Host "  WiFi IP = $wifiIP" -ForegroundColor White -BackgroundColor DarkBlue
    Write-Host ""
    Write-Host "  Arduino SERVER_IP should be:" -ForegroundColor DarkYellow
    Write-Host ('  #define SERVER_IP "' + $wifiIP + '"') -ForegroundColor Gray
} else {
    Write-Host "  Run: ipconfig  to find your IP" -ForegroundColor DarkYellow
}
Write-Host ""

# -- Summary -----------------------------------------------
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Setup Complete!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Run:" -ForegroundColor White
Write-Host "    python main.py          (Server + GUI)" -ForegroundColor Gray
Write-Host "    python main.py server   (Server only)" -ForegroundColor Gray
Write-Host ""
Write-Host "  Token  : data\device_token.txt" -ForegroundColor Gray
Write-Host "  Arduino: arduino\scanner_hall\scanner_hall.ino" -ForegroundColor Gray
Write-Host ""
pause
