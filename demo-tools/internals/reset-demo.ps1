# Resets the RubberDuck demo folder: archives the last demo, empties demo/,
# creates a fresh git repo, and installs the pre-commit hook.
# Run it by double-clicking "Reset Demo.cmd".
$ErrorActionPreference = "Stop"

$internal = $PSScriptRoot
$tools   = Split-Path $internal -Parent
$project = Split-Path $tools -Parent
$demo    = Join-Path $project "demo"
$exe     = Join-Path $project ".venv\Scripts\rubberduck.exe"
$rootEnv = Join-Path $project ".env"
$notes   = Join-Path $tools "CURRENT_DEMO.md"
$archive = Join-Path $tools "past-demos"

function Invoke-Git {
    git @args
    if ($LASTEXITCODE -ne 0) { throw "git $args failed" }
}

if (-not (Test-Path $exe)) {
    throw "Can't find $exe. Do the one-time setup in DEMO_INSTRUCTIONS.md first (create .venv and run pip install -e .)."
}

# 1. Archive the previous demo (its program and presenter notes) so the next
#    one starts clean and the coding AI can avoid repeating a topic.
$programs = @()
if (Test-Path $demo) {
    $programs = @(Get-ChildItem -LiteralPath $demo -Filter *.py -File)
}
if ($programs.Count -gt 0 -or (Test-Path $notes)) {
    $name = if ($programs.Count -gt 0) { $programs[0].BaseName } else { "demo" }
    $target = Join-Path $archive ("{0}_{1}" -f (Get-Date -Format "yyyy-MM-dd_HHmm"), $name)
    New-Item -ItemType Directory -Path $target -Force | Out-Null
    foreach ($program in $programs) { Copy-Item -LiteralPath $program.FullName -Destination $target }
    if (Test-Path $notes) { Move-Item -LiteralPath $notes -Destination (Join-Path $target "NOTES.md") }
    Write-Host "Archived the previous demo to demo-tools\past-demos\$(Split-Path $target -Leaf)"
}

# 2. Empty the demo folder (or create it)
if (Test-Path $demo) {
    Get-ChildItem -LiteralPath $demo -Force | Remove-Item -Recurse -Force
} else {
    New-Item -ItemType Directory -Path $demo | Out-Null
}

# 3. Fresh git repo with an empty first commit
Set-Location $demo
Invoke-Git init -q
Invoke-Git config core.autocrlf false
if (-not (git config user.email)) {
    Invoke-Git config user.name "RubberDuck Demo"
    Invoke-Git config user.email "demo@example.com"
}
Invoke-Git commit -q --allow-empty -m "Start demo"
Copy-Item (Join-Path $internal "exclude") (Join-Path $demo ".git\info\exclude") -Force

# 4. Pre-commit hook (relative path, so it works wherever the project is cloned)
Copy-Item (Join-Path $internal "pre-commit") (Join-Path $demo ".git\hooks\pre-commit") -Force

# 5. API key: reuse a .env from the project root if there is one
if (Test-Path $rootEnv) { Copy-Item $rootEnv (Join-Path $demo ".env") -Force }

# 6. Confirm the slate is clean: no files besides the ignored .env, nothing staged
$leftover = @(git status --porcelain)
if ($leftover.Count -gt 0) { throw "demo/ is not clean after reset: $leftover" }

Write-Host ""
Write-Host "Demo folder is ready and empty: $demo" -ForegroundColor Green
if ($env:GEMINI_API_KEY -or $env:GOOGLE_API_KEY) {
    Write-Host "API key found (environment variable)."
} elseif (Test-Path $rootEnv) {
    Write-Host "API key found (.env in the project folder)."
} else {
    Write-Warning "No Gemini API key found. Commits will be blocked until you add one (see DEMO_INSTRUCTIONS.md, step 4)."
}
Write-Host "Next: paste demo-tools\GENERATE_DEMO_PROMPT.md into your coding AI."
