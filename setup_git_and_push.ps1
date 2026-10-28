# ==============================================================================
# Smart EV Charging Schedule Optimization
# Git Repository Initialization & GitHub Deployment Script
# ==============================================================================

param(
    [string]$GitHubUsername = "gsparsh580-coder",
    [string]$RepoName = "smart-ev-charging-optimization"
)

Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host "   SMART EV CHARGING SCHEDULE OPTIMIZATION: GITHUB DEPLOYMENT SETUP" -ForegroundColor Yellow
Write-Host "==========================================================================" -ForegroundColor Cyan

$TargetDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $TargetDir

Write-Host "`n[1/5] Checking Git Status in $TargetDir..." -ForegroundColor Green
if (-not (Test-Path ".git")) {
    Write-Host "      Initializing new standalone Git repository..." -ForegroundColor Yellow
    git init
} else {
    Write-Host "      Existing Git repository detected." -ForegroundColor Green
}

Write-Host "`n[2/5] Staging project files..." -ForegroundColor Green
git add .

Write-Host "`n[3/5] Creating commit..." -ForegroundColor Green
git commit -m "feat: Smart EV Charging Schedule Optimization (Synthetic + ESP32 Hardware, HiveMQ MQTT, Node-RED, Web Dashboard)"

Write-Host "`n[4/5] Setting main branch & remote origin..." -ForegroundColor Green
git branch -M main

$RemoteUrl = "https://github.com/$GitHubUsername/$RepoName.git"
$ExistingRemote = git remote get-url origin 2>$null

if ($null -eq $ExistingRemote -or $ExistingRemote -eq "") {
    Write-Host "      Adding remote origin: $RemoteUrl" -ForegroundColor Yellow
    git remote add origin $RemoteUrl
} else {
    Write-Host "      Updating remote origin to: $RemoteUrl" -ForegroundColor Yellow
    git remote set-url origin $RemoteUrl
}

Write-Host "`n[5/5] Ready to push to GitHub!" -ForegroundColor Green
Write-Host "--------------------------------------------------------------------------"
Write-Host "Repository URL: $RemoteUrl" -ForegroundColor Cyan
Write-Host "Live Dashboard: https://$GitHubUsername.github.io/$RepoName/" -ForegroundColor Magenta
Write-Host "==========================================================================`n"
