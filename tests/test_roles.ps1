# E2E Role Tests — cURL / PowerShell Commands
# Run server first: python main.py
# Base URL
$BASE = "http://127.0.0.1:5000"

Write-Host "===== E2E ROLE TESTS =====" -ForegroundColor Cyan

# --- Login and get tokens ---
Write-Host "`n--- Logging in ---" -ForegroundColor Yellow

$adminBody = @{username="admin"; password="admin123"} | ConvertTo-Json
$adminResp = Invoke-RestMethod -Uri "$BASE/api/auth/login" -Method POST -Body $adminBody -ContentType "application/json"
$ADMIN = $adminResp.token
Write-Host "Admin token: $($ADMIN.Substring(0,10))..."

$secBody = @{username="secretary"; password="secretary123"} | ConvertTo-Json
$secResp = Invoke-RestMethod -Uri "$BASE/api/auth/login" -Method POST -Body $secBody -ContentType "application/json"
$SECRETARY = $secResp.token
Write-Host "Secretary token: $($SECRETARY.Substring(0,10))..."

$deanBody = @{username="dean"; password="dean123"} | ConvertTo-Json
$deanResp = Invoke-RestMethod -Uri "$BASE/api/auth/login" -Method POST -Body $deanBody -ContentType "application/json"
$DEAN = $deanResp.token
Write-Host "Dean token: $($DEAN.Substring(0,10))..."

$asstBody = @{username="dean_assistant"; password="assistant123"} | ConvertTo-Json
$asstResp = Invoke-RestMethod -Uri "$BASE/api/auth/login" -Method POST -Body $asstBody -ContentType "application/json"
$ASST = $asstResp.token
Write-Host "Dean Assistant token: $($ASST.Substring(0,10))..."

$headers = @{"X-Session-Token"=$ADMIN; "Content-Type"="application/json"}
$secHeaders = @{"X-Session-Token"=$SECRETARY; "Content-Type"="application/json"}
$deanHeaders = @{"X-Session-Token"=$DEAN; "Content-Type"="application/json"}
$asstHeaders = @{"X-Session-Token"=$ASST; "Content-Type"="application/json"}

# --- Test 1: Public endpoints ---
Write-Host "`n--- Test 1: Public endpoints (expect 200) ---" -ForegroundColor Yellow
try {
    $r = Invoke-WebRequest -Uri "$BASE/api/status" -Method GET
    Write-Host "  GET /api/status => $($r.StatusCode) OK" -ForegroundColor Green
} catch { Write-Host "  GET /api/status => FAIL $($_.Exception.Response.StatusCode)" -ForegroundColor Red }

try {
    $r = Invoke-WebRequest -Uri "$BASE/api/time/current" -Method GET
    Write-Host "  GET /api/time/current => $($r.StatusCode) OK" -ForegroundColor Green
} catch { Write-Host "  GET /api/time/current => FAIL" -ForegroundColor Red }

try {
    $r = Invoke-WebRequest -Uri "$BASE/api/auth/login" -Method POST -Body '{"username":"admin","password":"admin123"}' -ContentType "application/json"
    Write-Host "  POST /api/auth/login => $($r.StatusCode) OK" -ForegroundColor Green
} catch { Write-Host "  POST /api/auth/login => FAIL" -ForegroundColor Red }

# --- Test 2: No token = 401 ---
Write-Host "`n--- Test 2: No token (expect 401) ---" -ForegroundColor Yellow
try {
    $r = Invoke-WebRequest -Uri "$BASE/api/students" -Method GET
    Write-Host "  GET /api/students (no token) => $($r.StatusCode) UNEXPECTED" -ForegroundColor Red
} catch {
    $code = $_.Exception.Response.StatusCode.value__
    if ($code -eq 401) { Write-Host "  GET /api/students (no token) => 401 CORRECT" -ForegroundColor Green }
    else { Write-Host "  GET /api/students (no token) => $code" -ForegroundColor Red }
}

# --- Test 3: Secretary cannot justify ---
Write-Host "`n--- Test 3: Secretary justifies absence (expect 403) ---" -ForegroundColor Yellow
try {
    $body = '{"student_id":1,"from_date":"2026-01-01","to_date":"2026-01-05","reason":"test"}'
    $r = Invoke-WebRequest -Uri "$BASE/api/justifications" -Method POST -Headers $secHeaders -Body $body
    Write-Host "  POST /api/justifications (secretary) => $($r.StatusCode) UNEXPECTED" -ForegroundColor Red
} catch {
    $code = $_.Exception.Response.StatusCode.value__
    if ($code -eq 403) { Write-Host "  POST /api/justifications (secretary) => 403 CORRECT" -ForegroundColor Green }
    else { Write-Host "  POST /api/justifications (secretary) => $code" -ForegroundColor Red }
}

# --- Test 4: Dean can justify ---
Write-Host "`n--- Test 4: Dean justifies absence (expect 200) ---" -ForegroundColor Yellow
try {
    $body = '{"student_id":1,"from_date":"2026-01-01","to_date":"2026-01-05","reason":"test"}'
    $r = Invoke-WebRequest -Uri "$BASE/api/justifications" -Method POST -Headers $deanHeaders -Body $body
    Write-Host "  POST /api/justifications (dean) => $($r.StatusCode) OK" -ForegroundColor Green
} catch {
    $code = $_.Exception.Response.StatusCode.value__
    Write-Host "  POST /api/justifications (dean) => $code" -ForegroundColor Yellow
}

# --- Test 5: Admin sees all ---
Write-Host "`n--- Test 5: Admin full access ---" -ForegroundColor Yellow
try {
    $r = Invoke-WebRequest -Uri "$BASE/api/students" -Method GET -Headers $headers
    Write-Host "  GET /api/students (admin) => $($r.StatusCode) OK" -ForegroundColor Green
} catch { Write-Host "  GET /api/students (admin) => FAIL" -ForegroundColor Red }

try {
    $r = Invoke-WebRequest -Uri "$BASE/api/auth/accounts" -Method GET -Headers $headers
    Write-Host "  GET /api/auth/accounts (admin) => $($r.StatusCode) OK" -ForegroundColor Green
} catch { Write-Host "  GET /api/auth/accounts (admin) => FAIL" -ForegroundColor Red }

try {
    $r = Invoke-WebRequest -Uri "$BASE/api/dashboard/stats" -Method GET -Headers $headers
    Write-Host "  GET /api/dashboard/stats (admin) => $($r.StatusCode) OK" -ForegroundColor Green
} catch { Write-Host "  GET /api/dashboard/stats (admin) => FAIL" -ForegroundColor Red }

# --- Test 6: Seed demo ---
Write-Host "`n--- Test 6: Seed demo (admin only) ---" -ForegroundColor Yellow
try {
    $r = Invoke-WebRequest -Uri "$BASE/api/admin/seed-demo" -Method POST -Headers $headers -Body '{}'
    Write-Host "  POST /api/admin/seed-demo (admin) => $($r.StatusCode) OK" -ForegroundColor Green
} catch {
    $code = $_.Exception.Response.StatusCode.value__
    Write-Host "  POST /api/admin/seed-demo (admin) => $code" -ForegroundColor Yellow
}

try {
    $r = Invoke-WebRequest -Uri "$BASE/api/admin/seed-demo" -Method POST -Headers $secHeaders -Body '{}'
    Write-Host "  POST /api/admin/seed-demo (secretary) => UNEXPECTED" -ForegroundColor Red
} catch {
    $code = $_.Exception.Response.StatusCode.value__
    if ($code -eq 403) { Write-Host "  POST /api/admin/seed-demo (secretary) => 403 CORRECT" -ForegroundColor Green }
    else { Write-Host "  POST /api/admin/seed-demo (secretary) => $code" -ForegroundColor Red }
}

# --- Test 7: Dean assistant ---
Write-Host "`n--- Test 7: Dean Assistant access ---" -ForegroundColor Yellow
try {
    $r = Invoke-WebRequest -Uri "$BASE/api/students" -Method GET -Headers $asstHeaders
    Write-Host "  GET /api/students (dean_asst) => $($r.StatusCode) OK" -ForegroundColor Green
} catch { Write-Host "  GET /api/students (dean_asst) => FAIL" -ForegroundColor Red }

try {
    $r = Invoke-WebRequest -Uri "$BASE/api/holidays" -Method GET -Headers $asstHeaders
    Write-Host "  GET /api/holidays (dean_asst) => $($r.StatusCode) OK" -ForegroundColor Green
} catch { Write-Host "  GET /api/holidays (dean_asst) => FAIL" -ForegroundColor Red }

Write-Host "`n===== E2E TESTS COMPLETE =====" -ForegroundColor Cyan
