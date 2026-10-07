# Resets the RubberDuck demo folder: empties it, creates a fresh git repo,
# and installs the pre-commit hook. Run it by double-clicking "Reset Demo.cmd".
$ErrorActionPreference = "Stop"

$tools   = $PSScriptRoot
$project = Split-Path $tools -Parent
$demo    = Join-Path $project "demo"
$exe     = Join-Path $project ".venv\Scripts\rubberduck.exe"
$rootEnv = Join-Path $project ".env"

function Invoke-Git {
    git @args
    if ($LASTEXITCODE -ne 0) { throw "git $args failed" }
}

if (-not (Test-Path $exe)) {
    throw "Can't find $exe. Do the one-time setup in DEMO_INSTRUCTIONS.md first (create .venv and run pip install -e .)."
}

# 1. Empty the demo folder (or create it)
if (Test-Path $demo) {
    Get-ChildItem -LiteralPath $demo -Force | Remove-Item -Recurse -Force
} else {
    New-Item -ItemType Directory -Path $demo | Out-Null
}

# 2. Fresh git repo with an empty first commit
Set-Location $demo
Invoke-Git init -q
Invoke-Git config core.autocrlf false
if (-not (git config user.email)) {
    Invoke-Git config user.name "RubberDuck Demo"
    Invoke-Git config user.email "demo@example.com"
}
Invoke-Git commit -q --allow-empty -m "Start demo"
Copy-Item (Join-Path $tools "exclude") (Join-Path $demo ".git\info\exclude") -Force

# 3. Pre-commit hook (relative path, so it works wherever the project is cloned)
Copy-Item (Join-Path $tools "pre-commit") (Join-Path $demo ".git\hooks\pre-commit") -Force

# 4. API key: reuse a .env from the project root if there is one
if (Test-Path $rootEnv) { Copy-Item $rootEnv (Join-Path $demo ".env") -Force }

Write-Host ""
Write-Host "Demo folder is ready: $demo" -ForegroundColor Green
if ($env:GEMINI_API_KEY -or $env:GOOGLE_API_KEY) {
    Write-Host "API key found (environment variable)."
} elseif (Test-Path $rootEnv) {
    Write-Host "API key found (.env in the project folder)."
} else {
    Write-Warning "No Gemini API key found. Commits will be blocked until you add one (see DEMO_INSTRUCTIONS.md, step 4)."
}
Write-Host "Next: have the agent write its file in the demo folder, then in a terminal there run:"
Write-Host "  git add ."
Write-Host "  git commit -m ""Add gradebook"""
