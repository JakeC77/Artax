# Build and push Docker image to Azure Container Registry (PowerShell)
#
# Usage:
#   .\build-and-push.ps1 -AcrName <ACR_NAME> -ImageName <IMAGE_NAME> [-Tag <TAG>]
#
# Example:
#   .\build-and-push.ps1 -AcrName myregistry.azurecr.io -ImageName geodesicworks-ai-app -Tag latest

param(
    [Parameter(Mandatory=$true)]
    [string]$AcrName,
    
    [Parameter(Mandatory=$true)]
    [string]$ImageName,
    
    [Parameter(Mandatory=$false)]
    [string]$Tag = "latest"
)

$ErrorActionPreference = "Stop"

$FullImageName = "${AcrName}/${ImageName}:${Tag}"
$LatestImageName = "${AcrName}/${ImageName}:latest"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Building Docker image for Azure Container App" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "ACR: $AcrName"
Write-Host "Image: $ImageName"
Write-Host "Tag: $Tag"
Write-Host "Full name: $FullImageName"
Write-Host ""

# Validate ACR name format
if ($AcrName -notmatch '\.azurecr\.io$') {
    Write-Host "WARNING: ACR name should end with .azurecr.io" -ForegroundColor Yellow
    Write-Host "Example: myregistry.azurecr.io" -ForegroundColor Yellow
    Write-Host ""
    $Continue = Read-Host "Continue anyway? (y/n)"
    if ($Continue -ne 'y') {
        exit 1
    }
}

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Build context: need to go up to project root to include geodesic package
Write-Host "Building Docker image..." -ForegroundColor Yellow
Write-Host "Tagging as: $FullImageName" -ForegroundColor Gray
Write-Host "Tagging as: $LatestImageName" -ForegroundColor Gray
Write-Host ""

docker build `
    -f Dockerfile `
    -t $FullImageName `
    -t $LatestImageName `
    ../

if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker build failed!" -ForegroundColor Red
    exit 1
}

# Verify the image was tagged correctly
Write-Host ""
Write-Host "Verifying image tags..." -ForegroundColor Yellow
$ImageCheck = docker images $FullImageName --format "{{.Repository}}:{{.Tag}}"
if ($ImageCheck -notmatch [regex]::Escape($AcrName)) {
    Write-Host "WARNING: Image may not be tagged correctly!" -ForegroundColor Yellow
    Write-Host "Expected tag containing: $AcrName" -ForegroundColor Yellow
    Write-Host "Found: $ImageCheck" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Listing all images with similar names:" -ForegroundColor Yellow
    docker images | Select-String -Pattern $ImageName
}

Write-Host ""
Write-Host "Build complete!" -ForegroundColor Green
Write-Host ""

# Extract registry name (without .azurecr.io)
$RegistryName = $AcrName -replace '\.azurecr\.io$', ''

# Login to ACR (if not already logged in)
Write-Host "Logging in to Azure Container Registry..." -ForegroundColor Yellow

# First, verify Azure CLI is logged in
$AccountCheck = az account show 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Not logged in to Azure CLI!" -ForegroundColor Red
    Write-Host "Please run: az login" -ForegroundColor Yellow
    exit 1
}

# Try to login to ACR
az acr login --name geodesicworks

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ACR login failed! Common solutions:" -ForegroundColor Red
    Write-Host "1. Enable admin user: az acr update --name $RegistryName --admin-enabled true" -ForegroundColor Yellow
    Write-Host "2. Then login with: docker login ${AcrName} -u <username> -p <password>" -ForegroundColor Yellow
    Write-Host "3. Or assign AcrPush role to your user account" -ForegroundColor Yellow
    Write-Host "4. See ACR_SETUP.md for detailed instructions" -ForegroundColor Yellow
    exit 1
}

Write-Host "Successfully logged in to ACR" -ForegroundColor Green

# Push image
Write-Host ""
Write-Host "Pushing image to ACR..." -ForegroundColor Yellow
Write-Host "Pushing: $FullImageName" -ForegroundColor Gray
docker push $FullImageName

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Push failed! Check that:" -ForegroundColor Red
    Write-Host "1. You're logged in to ACR: az acr login --name $RegistryName" -ForegroundColor Yellow
    Write-Host "2. The image tag is correct: $FullImageName" -ForegroundColor Yellow
    Write-Host "3. You have push permissions" -ForegroundColor Yellow
    exit 1
}

Write-Host "Pushing: $LatestImageName" -ForegroundColor Gray
docker push $LatestImageName

if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker push failed!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "Successfully pushed to ACR!" -ForegroundColor Green
Write-Host "Image: $FullImageName" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green



