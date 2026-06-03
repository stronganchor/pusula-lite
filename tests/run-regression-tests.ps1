$ErrorActionPreference = 'Stop'

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
Push-Location $repoRoot
try {
    php -l pusula-lite-api.php
    node --check assets\pusula-app.js
    node --test tests\regression\source-regressions.test.js
    git diff --check
} finally {
    Pop-Location
}
