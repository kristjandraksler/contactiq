param(
  [string]$ProjectRoot = "."
)

$ErrorActionPreference = "Stop"

$globals = Join-Path $ProjectRoot "apps\web\app\globals.css"
$additions = Join-Path $ProjectRoot "apps\web\app\auth-additions.css"

if ((Test-Path $globals) -and (Test-Path $additions)) {
  $content = Get-Content $globals -Raw

  if ($content -notmatch "\.sidebarLogout") {
    Add-Content -Path $globals -Value "`r`n`r`n/* Auth additions */`r`n"
    Get-Content $additions | Add-Content $globals
  }

  Remove-Item $additions -Force
}

Write-Host "Auth CSS additions installed." -ForegroundColor Green
